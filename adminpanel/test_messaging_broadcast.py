import json

from django.test import TestCase
from django.urls import reverse

from adminpanel.models import ResearchCentre
from projects.models import Assignment, ChatMessage, Project, Task, TeamMember
from users.models import CustomUser


class NewBroadcastMessagingTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Broadcast Centre')
        self.manager = CustomUser.objects.create_user(
            username='broadcast-manager', password='pass', role='manager', research_centre=self.centre
        )
        self.author = CustomUser.objects.create_user(
            username='broadcast-author', password='pass', role='staff', research_centre=self.centre
        )
        self.task_member = CustomUser.objects.create_user(
            username='broadcast-task-member', password='pass', role='staff', research_centre=self.centre
        )
        self.outsider = CustomUser.objects.create_user(
            username='broadcast-outsider', password='pass', role='staff', research_centre=self.centre
        )
        self.project = Project.objects.create(
            name='Team Broadcast Project',
            created_by=self.manager,
            assigned_user=self.manager,
            research_centre=self.centre,
        )
        author_member, _ = TeamMember.objects.get_or_create(
            user=self.author,
            defaults={'full_name': self.author.username, 'role': 'Author'},
        )
        Assignment.objects.create(
            project=self.project,
            team_member=author_member,
            responsibility='Author',
        )
        Task.objects.create(
            project=self.project,
            title='Project task',
            assigned_to=self.task_member,
            created_by=self.manager,
        )

    def post_broadcast(self, user, payload):
        self.client.force_login(user)
        return self.client.post(
            reverse('api_new_broadcast_message'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_project_broadcast_reaches_only_involved_active_members(self):
        response = self.post_broadcast(self.manager, {
            'audience': 'project',
            'project_id': self.project.id,
            'message': 'Project team update',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recipient_count'], 2)
        self.assertSetEqual(
            set(ChatMessage.objects.values_list('recipient__username', flat=True)),
            {self.author.username, self.task_member.username},
        )
        self.assertFalse(ChatMessage.objects.filter(recipient=self.outsider).exists())

    def test_team_member_can_broadcast_only_to_a_project_they_belong_to(self):
        allowed = self.post_broadcast(self.author, {
            'audience': 'project',
            'project_id': self.project.id,
            'message': 'Author update',
        })
        self.assertEqual(allowed.status_code, 200)

        other_project = Project.objects.create(name='Private Project', created_by=self.outsider)
        denied = self.post_broadcast(self.author, {
            'audience': 'project',
            'project_id': other_project.id,
            'message': 'Should not send',
        })
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(ChatMessage.objects.filter(message='Should not send').exists())

    def test_new_people_broadcast_does_not_require_an_existing_message(self):
        response = self.post_broadcast(self.manager, {
            'audience': 'people',
            'recipient_ids': [self.author.id, self.task_member.id],
            'message': 'Fresh broadcast',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recipient_count'], 2)
        self.assertEqual(ChatMessage.objects.filter(message='Fresh broadcast').count(), 2)

    def test_recipient_options_include_only_projects_in_sender_scope(self):
        Project.objects.create(name='Unrelated Project', created_by=self.outsider)
        self.client.force_login(self.author)

        response = self.client.get(reverse('api_recipients_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['name'] for item in response.json()['projects']], ['Team Broadcast Project'])

    def test_messages_page_has_independent_new_broadcast_workflow(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('communique_section', args=['messages']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Broadcast')
        self.assertContains(response, 'Everyone involved in a project')
        self.assertContains(response, reverse('api_new_broadcast_message'))
