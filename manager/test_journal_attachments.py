from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from adminpanel.models import ResearchCentre
from manager.models import Paper


class JournalAttachmentTests(TestCase):
    def setUp(self):
        centre=ResearchCentre.objects.create(name='Journal Centre')
        self.user=get_user_model().objects.create_user(username='journal-manager',role='manager',research_centre=centre)
        self.client.force_login(self.user)

    def paper(self,title,kind,manuscript=''):
        return Paper.objects.create(title=title,internal_external=kind,paper_type='journal',version='1',status='draft',created_by=self.user,manuscript=manuscript)

    def test_internal_and_external_papers_render_without_manuscripts(self):
        self.paper('Imported internal paper','internal')
        self.paper('Imported external paper','external')
        response=self.client.get(reverse('manager_journal'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Imported internal paper')
        self.assertContains(response,'Imported external paper')
        self.assertContains(response,'No manuscript uploaded',count=2)

    def test_uploaded_manuscript_keeps_view_link(self):
        self.paper('Uploaded paper','internal','manuscripts/example.pdf')
        response=self.client.get(reverse('manager_journal'))
        self.assertContains(response,'manuscripts/example.pdf')
        self.assertNotContains(response,'No manuscript uploaded')
