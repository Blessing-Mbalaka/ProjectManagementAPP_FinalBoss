"""Database-backed chapter, book discussion and private dashboard work."""
import json
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from projects.scope import scope_books_for_user, scope_chapters_for_user
from projects.work_scope import assigned_projects_for
from users.roles import has_role, can_manage_publications
from .models import Book, Chapter, BookComment, DashboardTask


def can_edit_chapters(user):
    return has_role(user, 'admin', 'centrehead', 'overseer', 'manager')


def can_discuss_book(user, book):
    return can_manage_publications(user) or user.role == 'dean' or (
        user.role == 'financialadmin' and book.project_id and assigned_projects_for(user).filter(pk=book.project_id).exists()
    )


def accessible_books(user):
    books = scope_books_for_user(Book.objects.all(), user)
    if can_manage_publications(user) or user.role == 'dean':
        return books
    if user.role == 'financialadmin':
        return books.filter(project__in=assigned_projects_for(user))
    return books.none()


def chapter_authors(user):
    users = get_user_model().objects.filter(is_active=True).exclude(role__in=['student', 'it'])
    return users if has_role(user, 'admin') else users.filter(research_centre_id=user.research_centre_id) if user.research_centre_id else users.none()


class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ['chapter_number', 'title', 'author', 'assigned_author', 'editor', 'status']

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_author'].queryset = chapter_authors(user)
        self.fields['author'].required = False
        self.fields['chapter_number'].min_value = 1

    def clean(self):
        data = super().clean()
        if (data.get('chapter_number') or 0) < 1:
            self.add_error('chapter_number', 'Choose a positive chapter number.')
        author = data.get('assigned_author')
        name = (data.get('author') or '').strip()
        if not author and name:
            author = self.fields['assigned_author'].queryset.filter(username__iexact=name).first()
        if author:
            data['assigned_author'] = author
            data['author'] = author.get_full_name() or author.username
        elif not name:
            self.add_error('author', 'Enter an author name or select a system author.')
        else:
            data['author'] = name
        return data


def chapter_rows(book, user):
    return [{'id': c.pk, 'book_id': book.pk, 'number': c.chapter_number,
             'chapter_number': c.chapter_number, 'title': c.title, 'author': c.author,
             'assigned_author_id': c.assigned_author_id,
             'assigned_author': c.assigned_author.get_full_name() or c.assigned_author.username if c.assigned_author_id else c.author,
             'editor': c.editor or '', 'status': c.status,
             'lastUpdated': c.last_updated.isoformat(), 'last_updated': c.last_updated.isoformat()}
            for c in scope_chapters_for_user(book.chapters.all(), user).select_related('assigned_author').order_by('chapter_number', 'pk')]


def update_chapter_progress(book):
    chapters = book.chapters.all()
    book.completed_chapters = chapters.filter(status='Completed').count()
    book.total_chapters = max(book.total_chapters, chapters.count(), chapters.aggregate(n=Max('chapter_number'))['n'] or 1)
    book.save(update_fields=['completed_chapters', 'total_chapters'])


def chapter_response(book, user, **extra):
    return JsonResponse({'success': True, 'chapters': chapter_rows(book, user),
                         'completed_chapters': book.completed_chapters, 'total_chapters': book.total_chapters,
                         'can_edit': can_edit_chapters(user), **extra})


@login_required
@require_http_methods(['GET'])
def get_chapters(request, book_id):
    book = get_object_or_404(accessible_books(request.user), pk=book_id)
    return chapter_response(book, request.user)


def _save_chapter(request, book_id=None, chapter_id=None):
    if not can_edit_chapters(request.user):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)
    with transaction.atomic():
        # Keep FOR UPDATE on the outer query; PostgreSQL cannot lock DISTINCT results.
        visible_ids = scope_books_for_user(Book.objects.all(), request.user).values('pk')
        scoped = Book.objects.select_for_update().filter(pk__in=visible_ids)
        if chapter_id:
            chapter = get_object_or_404(Chapter, pk=chapter_id, book_id__in=visible_ids)
            book = get_object_or_404(scoped, pk=chapter.book_id)
            chapter = get_object_or_404(book.chapters, pk=chapter_id)
        else:
            book = get_object_or_404(scoped, pk=book_id)
            chapter = Chapter(book=book)
        data = {**payload, 'assigned_author': payload.get('assigned_author_id') or ''}
        form = ChapterForm(data, instance=chapter, user=request.user)
        if form.is_valid():
            if book.chapters.filter(chapter_number=form.cleaned_data['chapter_number']).exclude(pk=chapter.pk).exists():
                form.add_error('chapter_number', 'This book already has that chapter number.')
            else:
                chapter = form.save()
                update_chapter_progress(book)
                return chapter_response(book, request.user, id=chapter.pk)
        return JsonResponse({'success': False, 'error': ' '.join(message for errors in form.errors.values() for message in errors), 'errors': form.errors}, status=400)


@login_required
@require_POST
def add_chapter(request, book_id):
    return _save_chapter(request, book_id=book_id)


@login_required
@require_POST
def edit_chapter(request, chapter_id):
    return _save_chapter(request, chapter_id=chapter_id)


@login_required
@require_POST
def delete_chapter(request, chapter_id):
    if not can_edit_chapters(request.user):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    with transaction.atomic():
        # Keep FOR UPDATE on the outer query; PostgreSQL cannot lock DISTINCT results.
        visible_ids = scope_books_for_user(Book.objects.all(), request.user).values('pk')
        scoped = Book.objects.select_for_update().filter(pk__in=visible_ids)
        chapter = get_object_or_404(Chapter, pk=chapter_id, book_id__in=visible_ids)
        book = get_object_or_404(scoped, pk=chapter.book_id)
        chapter = get_object_or_404(book.chapters, pk=chapter_id)
        chapter.delete()
        update_chapter_progress(book)
        return chapter_response(book, request.user)


@login_required
@require_http_methods(['GET', 'POST'])
def book_comments(request, book_id):
    book = get_object_or_404(accessible_books(request.user), pk=book_id)
    if not can_discuss_book(request.user, book):
        return JsonResponse({'success': False, 'error': 'This book discussion is not available to your account.'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            if not text or len(text) > 10000:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({'success': False, 'error': 'Enter a comment of 1 to 10000 characters.'}, status=400)
        BookComment.objects.create(book=book, user=request.user, text=text)
    return JsonResponse({'success': True, 'comments': [
        {'id': item.pk, 'text': item.text, 'author': item.user.get_full_name() or item.user.username,
         'user_id': item.user_id, 'created_at': item.created_at.isoformat()}
        for item in book.comments.select_related('user').all()]})


@login_required
@require_http_methods(['GET', 'POST'])
def dashboard_tasks(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if 'import_tasks' in data:
                rows = data['import_tasks']
                if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
                    raise ValueError
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get('text'), str) or not 1 <= len(row['text'].strip()) <= 255 or not isinstance(row.get('completed', False), bool):
                        raise ValueError
                with transaction.atomic():
                    get_user_model().objects.select_for_update().get(pk=request.user.pk)
                    for row in rows:
                        if not DashboardTask.objects.filter(user=request.user, work_date=timezone.localdate(), title=row['text'].strip()).exists():
                            DashboardTask.objects.create(user=request.user, title=row['text'].strip(), completed=row.get('completed', False))
            else:
                title = data.get('title', '').strip()
                if not title or len(title) > 255:
                    raise ValueError
                DashboardTask.objects.create(user=request.user, title=title)
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({'success': False, 'error': 'Enter valid task titles of 1 to 255 characters (at most 100 imported tasks).'}, status=400)
    tasks = DashboardTask.objects.filter(user=request.user, work_date=timezone.localdate())
    return JsonResponse({'success': True, 'tasks': [{'id': t.pk, 'title': t.title, 'completed': t.completed} for t in tasks]})


@login_required
@require_POST
def dashboard_task_update(request, task_id):
    task = get_object_or_404(DashboardTask, pk=task_id, user=request.user)
    try:
        data = json.loads(request.body)
        action = data.get('action')
        if action not in {'complete', 'reopen', 'delete'}:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Choose complete, reopen or delete.'}, status=400)
    if action == 'delete':
        task.delete()
    else:
        task.completed = action == 'complete'
        task.save(update_fields=['completed'])
    return JsonResponse({'success': True})
