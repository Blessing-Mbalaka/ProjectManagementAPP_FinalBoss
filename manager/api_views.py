"""API views for managing Paper and Conference contributors"""
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from manager.models import Paper, Conference, PaperStatusHistory
from users.models import CustomUser


@login_required
@require_http_methods(["POST"])
def assign_reviewer(request):
    """Add a reviewer to a paper"""
    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
        reviewer_id = data.get('reviewer_id')
        
        paper = get_object_or_404(Paper, id=paper_id)
        reviewer = get_object_or_404(CustomUser, id=reviewer_id)
        
        # Add reviewer
        paper.assigned_reviewers.add(reviewer)
        
        return JsonResponse({
            'success': True,
            'message': f'{reviewer.get_full_name() or reviewer.username} assigned as reviewer',
            'reviewer': {
                'id': reviewer.id,
                'name': reviewer.get_full_name() or reviewer.username,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remove_reviewer(request):
    """Remove a reviewer from a paper"""
    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
        reviewer_id = data.get('reviewer_id')
        
        paper = get_object_or_404(Paper, id=paper_id)
        reviewer = get_object_or_404(CustomUser, id=reviewer_id)
        
        # Remove reviewer
        paper.assigned_reviewers.remove(reviewer)
        
        return JsonResponse({
            'success': True,
            'message': f'{reviewer.get_full_name() or reviewer.username} removed as reviewer'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def add_coauthor(request):
    """Add a co-author to a paper"""
    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
        coauthor_id = data.get('coauthor_id')
        
        paper = get_object_or_404(Paper, id=paper_id)
        coauthor = get_object_or_404(CustomUser, id=coauthor_id)
        
        # Add coauthor
        paper.co_authors_users.add(coauthor)
        
        return JsonResponse({
            'success': True,
            'message': f'{coauthor.get_full_name() or coauthor.username} added as co-author',
            'coauthor': {
                'id': coauthor.id,
                'name': coauthor.get_full_name() or coauthor.username,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remove_coauthor(request):
    """Remove a co-author from a paper"""
    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
        coauthor_id = data.get('coauthor_id')
        
        paper = get_object_or_404(Paper, id=paper_id)
        coauthor = get_object_or_404(CustomUser, id=coauthor_id)
        
        # Remove coauthor
        paper.co_authors_users.remove(coauthor)
        
        return JsonResponse({
            'success': True,
            'message': f'{coauthor.get_full_name() or coauthor.username} removed as co-author'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def set_lead_author(request):
    """Set the lead author of a paper"""
    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
        author_id = data.get('author_id')
        
        paper = get_object_or_404(Paper, id=paper_id)
        author = get_object_or_404(CustomUser, id=author_id)
        
        # Set lead author
        paper.lead_author_user = author
        paper.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{author.get_full_name() or author.username} set as lead author',
            'author': {
                'id': author.id,
                'name': author.get_full_name() or author.username,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def assign_conference_reviewer(request):
    """Add a reviewer to a conference"""
    try:
        data = json.loads(request.body)
        conference_id = data.get('conference_id')
        reviewer_id = data.get('reviewer_id')
        
        conference = get_object_or_404(Conference, id=conference_id)
        reviewer = get_object_or_404(CustomUser, id=reviewer_id)
        
        # Add reviewer
        conference.assigned_reviewers.add(reviewer)
        
        return JsonResponse({
            'success': True,
            'message': f'{reviewer.get_full_name() or reviewer.username} assigned as reviewer',
            'reviewer': {
                'id': reviewer.id,
                'name': reviewer.get_full_name() or reviewer.username,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remove_conference_reviewer(request):
    """Remove a reviewer from a conference"""
    try:
        data = json.loads(request.body)
        conference_id = data.get('conference_id')
        reviewer_id = data.get('reviewer_id')
        
        conference = get_object_or_404(Conference, id=conference_id)
        reviewer = get_object_or_404(CustomUser, id=reviewer_id)
        
        # Remove reviewer
        conference.assigned_reviewers.remove(reviewer)
        
        return JsonResponse({
            'success': True,
            'message': f'{reviewer.get_full_name() or reviewer.username} removed as reviewer'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["GET"])
def get_paper_contributors(request, paper_id):
    """Get all contributors for a paper (authors, reviewers, creator)"""
    try:
        paper = get_object_or_404(Paper, id=paper_id)
        contributors = paper.get_all_contributors()
        
        return JsonResponse({
            'success': True,
            'contributors': [
                {
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'role': user.role,
                    'email': user.email,
                }
                for user in contributors
            ],
            'lead_author': {
                'id': paper.lead_author_user.id,
                'name': paper.lead_author_user.get_full_name() or paper.lead_author_user.username,
            } if paper.lead_author_user else None,
            'co_authors': [
                {
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                }
                for user in paper.co_authors_users.all()
            ],
            'reviewers': [
                {
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                }
                for user in paper.assigned_reviewers.all()
            ]
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["GET"])
def get_available_users(request):
    """Get list of available users for assignment (for dropdowns/modals)"""
    try:
        # Get all active users except the requesting user
        users = CustomUser.objects.filter(is_active=True).exclude(
            id=request.user.id
        ).order_by('first_name', 'last_name')
        
        return JsonResponse({
            'success': True,
            'users': [
                {
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'role': user.role,
                    'email': user.email,
                }
                for user in users
            ]
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
