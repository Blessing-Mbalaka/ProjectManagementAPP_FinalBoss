from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from adminpanel.models import CostCentre, EngagementLog, ResearchCentre
from projects.models import Project, TeamMember
from users.models import CustomUser


class Command(BaseCommand):
    help = "Seed demo engagement CRM history so repeated client approaches can be tested."

    def handle(self, *args, **options):
        today = timezone.localdate()

        centres = {
            "Education Futures Centre": ResearchCentre.objects.update_or_create(
                name="Education Futures Centre",
                defaults={"description": "Seeded engagement demo centre."},
            )[0],
            "Digital Society Centre": ResearchCentre.objects.update_or_create(
                name="Digital Society Centre",
                defaults={"description": "Seeded engagement demo centre."},
            )[0],
        }

        managers = {}
        for centre_name, centre in centres.items():
            slug = centre_name.split()[0].lower()
            manager, _ = CustomUser.objects.update_or_create(
                username=f"engage_{slug}_manager",
                defaults={
                    "email": f"engage_{slug}_manager@example.com",
                    "first_name": centre_name.split()[0],
                    "last_name": "Manager",
                    "role": "manager",
                    "research_centre": centre,
                    "is_active": True,
                },
            )
            manager.set_password("DemoPass123!")
            manager.save()
            TeamMember.objects.update_or_create(
                user=manager,
                defaults={
                    "full_name": manager.get_full_name() or manager.username,
                    "role": manager.get_role_display(),
                },
            )
            managers[centre_name] = manager

        shared_client = "Acme Health Consortium"
        shared_company = "Acme Health Consortium Pty Ltd"

        seeded_pairs = [
            {
                "centre": centres["Education Futures Centre"],
                "manager": managers["Education Futures Centre"],
                "cost_code": "ENG-EDU-001",
                "cost_name": "ACME Education Programme",
                "project_name": "ACME Engagement Discovery",
                "subject": "Dean outreach briefing",
                "entry_type": "meeting_minutes",
                "days_ago": 45,
                "notes": "Met with the client leadership team and captured their priorities around programme evaluation and workforce capability tracking.",
                "proposal": "Proposed an evaluation framework, baseline survey, and quarterly insight pack delivered by Education Futures Centre.",
            },
            {
                "centre": centres["Digital Society Centre"],
                "manager": managers["Digital Society Centre"],
                "cost_code": "ENG-DIG-001",
                "cost_name": "ACME Digital Transformation Study",
                "project_name": "ACME Follow-up Innovation Proposal",
                "subject": "Follow-up solution workshop",
                "entry_type": "discussion",
                "days_ago": 12,
                "notes": "Second approach focused on digital delivery readiness, platform integration needs, and executive sponsorship concerns.",
                "proposal": "Proposed a digital maturity assessment plus implementation roadmap from Digital Society Centre.",
            },
        ]

        for item in seeded_pairs:
            cost_centre, _ = CostCentre.objects.update_or_create(
                code=item["cost_code"],
                defaults={
                    "name": item["cost_name"],
                    "client_name": shared_client,
                    "company_name": shared_company,
                    "contact_person_name": "Jordan Ndlovu",
                    "contact_person_role": "Programme Director",
                    "contact_email": "jordan.ndlovu@example.com",
                    "research_centre": item["centre"],
                    "crm_notes": "Seeded engagement client for CRM history testing.",
                },
            )
            project, _ = Project.objects.update_or_create(
                name=item["project_name"],
                defaults={
                    "description": f"Seeded project for {shared_client} engagement history testing.",
                    "project_type": "software",
                    "status": "in-progress",
                    "created_by": item["manager"],
                    "assigned_user": item["manager"],
                    "research_centre": item["centre"],
                    "due_date": today + timedelta(days=25),
                },
            )
            EngagementLog.objects.update_or_create(
                project=project,
                cost_centre=cost_centre,
                subject=item["subject"],
                defaults={
                    "research_centre": item["centre"],
                    "entered_by": item["manager"],
                    "entry_type": item["entry_type"],
                    "engagement_date": today - timedelta(days=item["days_ago"]),
                    "notes": item["notes"],
                    "proposal_summary": item["proposal"],
                },
            )

        current_centre = centres["Education Futures Centre"]
        current_manager = managers["Education Futures Centre"]
        current_cost_centre, _ = CostCentre.objects.update_or_create(
            code="ENG-EDU-002",
            defaults={
                "name": "ACME Capability Sprint",
                "client_name": shared_client,
                "company_name": shared_company,
                "contact_person_name": "Jordan Ndlovu",
                "contact_person_role": "Programme Director",
                "contact_email": "jordan.ndlovu@example.com",
                "research_centre": current_centre,
                "crm_notes": "Current active seeded record for the same client.",
            },
        )
        current_project, _ = Project.objects.update_or_create(
            name="ACME Current Delivery Continuation",
            defaults={
                "description": "Latest seeded engagement project to show previous approach history in CRM.",
                "project_type": "software",
                "status": "planning",
                "created_by": current_manager,
                "assigned_user": current_manager,
                "research_centre": current_centre,
                "due_date": today + timedelta(days=40),
            },
        )
        EngagementLog.objects.update_or_create(
            project=current_project,
            cost_centre=current_cost_centre,
            subject="Current scoping call",
            defaults={
                "research_centre": current_centre,
                "entered_by": current_manager,
                "entry_type": "comment",
                "engagement_date": today - timedelta(days=2),
                "notes": "Client requested a combined view of prior proposals before confirming the preferred centre for delivery.",
                "proposal_summary": "Proposed a short scoping sprint that consolidates both earlier approaches into one delivery option.",
            },
        )

        shared_logs = EngagementLog.objects.filter(cost_centre__client_name=shared_client).select_related(
            "research_centre", "project"
        )
        self.stdout.write(self.style.SUCCESS("Seeded engagement test data."))
        self.stdout.write(f"Shared client: {shared_client}")
        self.stdout.write(f"Projects seeded: {shared_logs.values('project').distinct().count()}")
        self.stdout.write(f"Engagement logs seeded: {shared_logs.count()}")
        self.stdout.write(
            "Centres represented: "
            + ", ".join(sorted({log.research_centre.name for log in shared_logs if log.research_centre}))
        )
