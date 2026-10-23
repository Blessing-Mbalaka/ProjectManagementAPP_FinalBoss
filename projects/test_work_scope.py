from django.contrib.auth import get_user_model
from django.test import TestCase

from adminpanel.models import ResearchCentre
from projects.models import Assignment, Project, Task, TeamMember
from projects.work_scope import (
    assigned_projects_for,
    can_update_task,
    inspectable_users_for,
    workable_tasks_for,
)


User = get_user_model()


class WorkScopeTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Primary Centre")
        self.other_centre = ResearchCentre.objects.create(name="Other Centre")
        self.owner = User.objects.create_user(username="owner", role="manager", research_centre=self.centre)
        self.direct = User.objects.create_user(username="direct", role="staff", research_centre=self.centre)
        self.member = User.objects.create_user(username="member", role="staff", research_centre=self.centre)
        self.admin = User.objects.create_user(username="assigned-admin", role="admin")
        self.unrelated = User.objects.create_user(username="unrelated", role="staff", research_centre=self.centre)
        self.other_centre_staff = User.objects.create_user(
            username="other-centre", role="staff", research_centre=self.other_centre
        )
        self.centre_head = User.objects.create_user(
            username="centre-head", role="centrehead", research_centre=self.centre
        )

        self.project = Project.objects.create(
            name="Shared project",
            created_by=self.owner,
            assigned_user=self.direct,
            research_centre=self.centre,
        )
        self.admin_project = Project.objects.create(
            name="Admin project",
            created_by=self.owner,
            assigned_user=self.admin,
            research_centre=self.centre,
        )
        self.member_record = TeamMember.objects.create(user=self.member, full_name="Member", role="Staff")
        Assignment.objects.create(project=self.project, team_member=self.member_record, responsibility="Analysis")

        self.project_task = Task.objects.create(project=self.project, title="Project pool task", created_by=self.owner)
        self.admin_task = Task.objects.create(project=self.admin_project, title="Admin pool task", created_by=self.owner)
        self.direct_task = Task.objects.create(title="Direct task", assigned_to=self.member, created_by=self.owner)
        self.unrelated_task = Task.objects.create(title="Unrelated", assigned_to=self.unrelated, created_by=self.owner)

    def test_direct_project_assignee_does_not_inherit_other_peoples_tasks(self):
        self.assertIn(self.project, assigned_projects_for(self.direct))
        self.assertNotIn(self.project_task, workable_tasks_for(self.direct))
        self.assertFalse(can_update_task(self.direct, self.project_task))

    def test_team_member_and_direct_task_assignee_receive_only_authorized_work(self):
        visible = set(workable_tasks_for(self.member))
        self.assertEqual(visible, {self.direct_task})
        self.assertNotIn(self.unrelated_task, visible)

    def test_admin_can_have_assigned_projects_without_institutional_scope_leaking_other_tasks(self):
        self.assertEqual(list(assigned_projects_for(self.admin)), [self.admin_project])
        self.assertEqual(list(workable_tasks_for(self.admin)), [self.admin_task])
        self.assertFalse(can_update_task(self.admin, self.unrelated_task))

    def test_centre_head_can_only_inspect_users_in_their_centre(self):
        visible = set(inspectable_users_for(self.centre_head))
        self.assertIn(self.direct, visible)
        self.assertNotIn(self.other_centre_staff, visible)
        self.assertNotIn(self.admin, visible)

    def test_admin_can_inspect_active_users_including_another_admin(self):
        visible = set(inspectable_users_for(self.admin))
        self.assertIn(self.admin, visible)
        self.assertIn(self.direct, visible)
