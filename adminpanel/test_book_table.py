import json
import re
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from manager.models import Book, Chapter

@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AdminBookTableTests(TestCase):
    def test_nullable_and_script_like_book_data_is_valid_safe_json(self):
        admin = get_user_model().objects.create_user('book-table-admin', role='admin')
        book = Book.objects.create(title='A book </script> with "quotes"', created_by=admin, lead_author='Editor', description=None, total_chapters=0)
        Chapter.objects.create(book=book, chapter_number=1, title='First chapter', author='Contributor', editor=None)
        self.client.force_login(admin)
        response = self.client.get(reverse('admin_book'))
        self.assertEqual(response.status_code, 200)
        match = re.search(r'<script id="booksData" type="application/json">(.*?)</script>', response.content.decode(), re.S)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data[0]['title'], book.title)
        self.assertEqual(data[0]['chapters']['list'][0]['title'], 'First chapter')
        self.assertNotIn('</script>', match.group(1))
        self.assertContains(response, 'id="tableBookSelect"')
