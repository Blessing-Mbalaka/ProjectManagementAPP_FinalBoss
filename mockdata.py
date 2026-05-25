import os
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_manage.settings")

import django

django.setup()

from adminpanel.models import CostCentre, CostCentrePayment, Expenditure, ResearchCentre
from django.utils import timezone
from manager.models import Book, Chapter, Conference, Paper
from projects.models import Assignment, Project, Task, TeamMember
from users.models import CustomUser


PASSWORD = "DemoPass123!"


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def set_user(username, role, centre=None, first_name="", last_name="", email=None, staff=False):
    user, _ = CustomUser.objects.update_or_create(
        username=username,
        defaults={
            "email": email or f"{username}@demo.local",
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "research_centre": centre,
            "is_active": True,
            "is_staff": staff or role == "admin",
        },
    )
    user.set_password(PASSWORD)
    user.save()
    if role in {"admin", "manager", "staff", "centrehead", "financialadmin"}:
        TeamMember.objects.update_or_create(
            user=user,
            defaults={
                "full_name": user.get_full_name() or user.username,
                "role": user.get_role_display(),
            },
        )
    return user


def reset_cost_centre_money(cost_centre):
    cost_centre.payments.all().delete()
    cost_centre.expenditures.all().delete()
    cost_centre.total_received = Decimal("0.00")
    cost_centre.total_spent = Decimal("0.00")
    cost_centre.save(update_fields=["total_received", "total_spent"])


def create_payment(cost_centre, amount, description):
    CostCentrePayment.objects.create(
        cost_centre=cost_centre,
        amount=money(amount),
        description=description,
    )


def create_expenditure(cost_centre, key, amount, category, days_ago=20, oracle_delta=0):
    expense_id = f"DEMO-{cost_centre.code}-{key}"
    Expenditure.objects.update_or_create(
        expense_id=expense_id,
        defaults={
            "cost_centre": cost_centre,
            "date_from": date.today() - timedelta(days=days_ago + 30),
            "date_to": date.today() - timedelta(days=days_ago),
            "month": (date.today() - timedelta(days=days_ago)).strftime("%Y-%m"),
            "name": f"Demo {category} {key}",
            "category": category,
            "amount": money(amount),
            "opening_balance": money(0),
            "oracle_balance": money(amount + oracle_delta) if oracle_delta else money(amount),
        },
    )


def create_project(company, centre, manager, staff_users, index, risk):
    status = {
        "high": "in-progress",
        "medium": "in-progress",
        "low": "planning",
        "complete": "completed",
    }.get(risk, "in-progress")
    due_date = {
        "high": date.today() - timedelta(days=12 + index),
        "medium": date.today() + timedelta(days=14 + index),
        "low": date.today() + timedelta(days=45 + index),
        "complete": date.today() - timedelta(days=20),
    }.get(risk, date.today() + timedelta(days=30))

    project, _ = Project.objects.update_or_create(
        name=f"{company['short']} Delivery Project",
        defaults={
            "description": f"Demo client delivery project for {company['company_name']}.",
            "project_type": company["project_type"],
            "status": status,
            "created_by": manager,
            "assigned_user": manager,
            "research_centre": centre,
            "due_date": due_date,
        },
    )

    for staff in staff_users[:2]:
        member = TeamMember.objects.get(user=staff)
        Assignment.objects.update_or_create(
            project=project,
            team_member=member,
            defaults={"responsibility": f"Delivery support for {company['short']}"},
        )

    tasks = [
        ("Contract setup", "done", "Architecture", "High", -35),
        ("Client discovery", "done" if risk != "high" else "review", "UX/UI", "Medium", -18),
        ("Delivery build", "in_progress" if risk != "complete" else "done", "Backend", "High", 5),
        ("Quality review", "review" if risk == "medium" else "todo", "Testing", "Medium", 18),
        ("Close-out report", "todo" if risk != "complete" else "done", "Deployment", "Low", 30),
    ]
    for task_index, (title, task_status, task_type, priority, offset) in enumerate(tasks, start=1):
        assignee = staff_users[task_index % len(staff_users)]
        task, _ = Task.objects.update_or_create(
            project=project,
            title=f"{company['short']}: {title}",
            defaults={
                "status": task_status,
                "task_type": task_type,
                "priority": priority,
                "due_date": date.today() + timedelta(days=offset),
                "created_by": manager,
                "assigned_to": assignee,
            },
        )
        if risk == "high":
            Task.objects.filter(id=task.id).update(created_at=timezone.now() - timedelta(days=75))

    return project


def create_book(title, creator, status, due_offset, chapters_done):
    book, _ = Book.objects.update_or_create(
        title=title,
        defaults={
            "description": f"Demo book output for {creator.research_centre.name if creator.research_centre else 'UJ'}.",
            "status": status,
            "due_date": date.today() + timedelta(days=due_offset),
            "lead_author": creator.get_full_name() or creator.username,
            "publisher": "UJ Demo Press",
            "total_chapters": 6,
            "completed_chapters": chapters_done,
            "created_by": creator,
        },
    )
    for chapter_no in range(1, 7):
        Chapter.objects.update_or_create(
            book=book,
            chapter_number=chapter_no,
            defaults={
                "title": f"{title} - Chapter {chapter_no}",
                "author": creator.get_full_name() or creator.username,
                "editor": "Demo Editor",
                "status": "Completed" if chapter_no <= chapters_done else "In Progress",
            },
        )
    return book


def create_paper(title, creator, status, internal_external, stale=False):
    paper, _ = Paper.objects.update_or_create(
        title=title,
        defaults={
            "paper_type": "journal",
            "internal_external": internal_external,
            "lead_author": creator.get_full_name() or creator.username,
            "lead_author_user": creator,
            "co_authors": "Demo Coauthor",
            "status": status,
            "version": "1.0",
            "abstract": f"Demo abstract for {title}.",
            "target_journal": "Journal of Demo Research",
            "submission_date": date.today() - timedelta(days=25) if internal_external == "external" else None,
            "created_by": creator,
        },
    )
    if stale:
        Paper.objects.filter(id=paper.id).update(updated_at=timezone.now() - timedelta(days=90))
    return paper


def create_conference(title, creator, status, stale=False):
    conference, _ = Conference.objects.update_or_create(
        title=title,
        defaults={
            "internal_external": "external" if status in {"submitted", "accepted", "presenting"} else "internal",
            "conference_name": "Demo Applied Research Conference",
            "location": "Johannesburg",
            "lead_author": creator.get_full_name() or creator.username,
            "lead_author_user": creator,
            "co_authors": "Demo Coauthor",
            "status": status,
            "abstract": f"Demo conference abstract for {title}.",
            "submission_date": date.today() - timedelta(days=30),
            "conference_date": date.today() + timedelta(days=60),
            "created_by": creator,
        },
    )
    if stale:
        Conference.objects.filter(id=conference.id).update(updated_at=timezone.now() - timedelta(days=95))
    return conference


def main():
    today = date.today()

    print("Starting mock data load...")
    print("Creating research centres...")
    centres = {
        "Education Futures Centre": ResearchCentre.objects.update_or_create(
            name="Education Futures Centre",
            defaults={"description": "Demo centre focused on education research and evaluation."},
        )[0],
        "Health Innovation Centre": ResearchCentre.objects.update_or_create(
            name="Health Innovation Centre",
            defaults={"description": "Demo centre focused on public health and clinical innovation."},
        )[0],
        "Digital Society Centre": ResearchCentre.objects.update_or_create(
            name="Digital Society Centre",
            defaults={"description": "Demo centre focused on digital systems and social impact."},
        )[0],
    }

    print("Creating demo users and team members...")
    users = {
        "dean": set_user("demo_dean", "dean", None, "Demo", "Dean", staff=True),
        "admin_all": set_user("demo_admin", "admin", None, "Demo", "Admin", staff=True),
    }

    centre_users = {}
    for idx, (centre_name, centre) in enumerate(centres.items(), start=1):
        slug = centre_name.split()[0].lower()
        centre_users[centre_name] = {
            "admin": set_user(f"demo_{slug}_admin", "admin", centre, slug.title(), "Admin", staff=True),
            "centrehead": set_user(f"demo_{slug}_head", "centrehead", centre, slug.title(), "Head"),
            "financial": set_user(f"demo_{slug}_finance", "financialadmin", centre, slug.title(), "Finance"),
            "manager": set_user(f"demo_{slug}_manager", "manager", centre, slug.title(), "Manager"),
            "staff": [
                set_user(f"demo_{slug}_staff_1", "staff", centre, slug.title(), "Staff One"),
                set_user(f"demo_{slug}_staff_2", "staff", centre, slug.title(), "Staff Two"),
                set_user(f"demo_{slug}_staff_3", "staff", centre, slug.title(), "Staff Three"),
            ],
            "students": [
                set_user(f"demo_{slug}_student_1", "student", centre, slug.title(), "Student One"),
                set_user(f"demo_{slug}_student_2", "student", centre, slug.title(), "Student Two"),
            ],
        }

    companies = [
        {"code": "DEMO001", "short": "EduSpark", "company_name": "EduSpark Learning Pty Ltd", "centre": "Education Futures Centre", "risk": "high", "moa": 1250000, "received": [250000], "spent": [175000, 92000], "oracle_delta": 10000, "project_type": "software", "industry": "Education Technology"},
        {"code": "DEMO002", "short": "BrightSchools", "company_name": "BrightSchools Foundation", "centre": "Education Futures Centre", "risk": "medium", "moa": 820000, "received": [410000], "spent": [120000], "oracle_delta": 0, "project_type": "paper", "industry": "Non-profit Education"},
        {"code": "DEMO003", "short": "CurricuLab", "company_name": "CurricuLab Analytics CC", "centre": "Education Futures Centre", "risk": "low", "moa": 640000, "received": [320000, 160000], "spent": [110000], "oracle_delta": 0, "project_type": "software", "industry": "Analytics"},
        {"code": "DEMO004", "short": "MediBridge", "company_name": "MediBridge Health Group", "centre": "Health Innovation Centre", "risk": "high", "moa": 2100000, "received": [], "spent": [265000], "oracle_delta": 25000, "project_type": "software", "industry": "Healthcare"},
        {"code": "DEMO005", "short": "CarePath", "company_name": "CarePath Clinics Pty Ltd", "centre": "Health Innovation Centre", "risk": "medium", "moa": 980000, "received": [490000], "spent": [180000], "oracle_delta": 0, "project_type": "book", "industry": "Clinical Services"},
        {"code": "DEMO006", "short": "BioTrack", "company_name": "BioTrack Diagnostics SA", "centre": "Health Innovation Centre", "risk": "low", "moa": 1520000, "received": [760000, 380000], "spent": [250000, 140000], "oracle_delta": 0, "project_type": "paper", "industry": "Diagnostics"},
        {"code": "DEMO007", "short": "CivicData", "company_name": "CivicData Systems Pty Ltd", "centre": "Digital Society Centre", "risk": "high", "moa": 1340000, "received": [250000], "spent": [315000], "oracle_delta": 15000, "project_type": "software", "industry": "Civic Technology"},
        {"code": "DEMO008", "short": "GovTechLab", "company_name": "GovTechLab South Africa", "centre": "Digital Society Centre", "risk": "medium", "moa": 1160000, "received": [580000], "spent": [205000], "oracle_delta": 0, "project_type": "software", "industry": "Government Technology"},
        {"code": "DEMO009", "short": "InclusionAI", "company_name": "InclusionAI Research NPC", "centre": "Digital Society Centre", "risk": "low", "moa": 740000, "received": [370000], "spent": [90000], "oracle_delta": 0, "project_type": "paper", "industry": "Responsible AI"},
        {"code": "DEMO010", "short": "UrbanSense", "company_name": "UrbanSense Mobility Pty Ltd", "centre": "Digital Society Centre", "risk": "complete", "moa": 690000, "received": [690000], "spent": [420000], "oracle_delta": 0, "project_type": "software", "industry": "Smart Mobility"},
    ]

    print("Creating companies, cost centres, finance records, projects, tasks, and assignments...")
    cost_centres = []
    for index, company in enumerate(companies, start=1):
        print(f"  [{index}/{len(companies)}] Loading {company['company_name']} ({company['risk']} risk)")
        centre = centres[company["centre"]]
        risk = company["risk"]
        due_dates = {
            "high": [today - timedelta(days=30), today - timedelta(days=10), None, today + timedelta(days=20)],
            "medium": [today - timedelta(days=5), today + timedelta(days=15), None, today + timedelta(days=60)],
            "low": [today + timedelta(days=20), today + timedelta(days=45), today + timedelta(days=80), today + timedelta(days=120)],
            "complete": [today - timedelta(days=120), today - timedelta(days=90), today - timedelta(days=60), today - timedelta(days=30)],
        }[risk]
        cost_centre, _ = CostCentre.objects.update_or_create(
            code=company["code"],
            defaults={
                "name": f"{company['short']} Cost Centre",
                "client_name": company["short"],
                "company_name": company["company_name"],
                "company_registration_number": f"20{index:02d}/12345{index}/07",
                "vat_number": f"4{index:09d}",
                "industry": company["industry"],
                "company_website": f"https://www.{company['short'].lower()}.example",
                "company_email": f"hello@{company['short'].lower()}.example",
                "company_phone": f"+27 11 555 {1000 + index}",
                "company_address": f"{index} Demo Avenue, Johannesburg, 2001",
                "contact_person_name": f"{company['short']} Contact",
                "contact_person_role": "Client Sponsor",
                "contact_email": f"sponsor@{company['short'].lower()}.example",
                "contact_phone": f"+27 82 555 {2000 + index}",
                "crm_notes": f"Demo {risk} risk company. Seeded for CRM and alert testing.",
                "research_centre": centre,
                "moa_amount": money(company["moa"]),
                "phase_1_due_date": due_dates[0],
                "phase_2_due_date": due_dates[1],
                "phase_3_due_date": due_dates[2],
                "phase_4_due_date": due_dates[3],
            },
        )
        reset_cost_centre_money(cost_centre)
        for payment_index, payment_amount in enumerate(company["received"], start=1):
            create_payment(cost_centre, payment_amount, f"Demo tranche {payment_index}")
        for spend_index, spend_amount in enumerate(company["spent"], start=1):
            create_expenditure(
                cost_centre,
                f"{spend_index}",
                spend_amount,
                "Invoices" if spend_index % 2 else "Salary",
                oracle_delta=company["oracle_delta"] if spend_index == 1 else 0,
            )
        cost_centres.append(cost_centre)

        centre_team = centre_users[company["centre"]]
        create_project(company, centre, centre_team["manager"], centre_team["staff"], index, risk)

    print("Creating demo books and chapters...")
    creators = []
    for centre_name, team in centre_users.items():
        creators.append(team["manager"])
        creators.extend(team["staff"][:1])

    book_specs = [
        ("Digital Learning Evidence Handbook", creators[0], "writing", -15, 2),
        ("Public Health Innovation Cases", creators[2], "review", 25, 4),
        ("Responsible AI for Cities", creators[4], "production", 60, 5),
        ("Education Evaluation Methods", creators[1], "published", -90, 6),
        ("Community Health Data Practice", creators[3], "submission", 10, 3),
        ("Smart Mobility Research Guide", creators[5], "writing", 90, 1),
    ]
    for spec in book_specs:
        print(f"  Book: {spec[0]}")
        create_book(*spec)

    print("Creating demo papers...")
    paper_specs = [
        ("Early Warning Indicators in School Data", creators[0], "draft", "internal", True),
        ("Clinic Queue Prediction Models", creators[2], "under-review", "external", True),
        ("Civic Platform Trust Measures", creators[4], "submitted", "external", False),
        ("AI Inclusion Metrics for Public Services", creators[5], "accepted", "external", False),
        ("Teacher Development Analytics", creators[1], "circulation", "internal", False),
        ("Diagnostics Access Dashboard", creators[3], "ready-submission", "internal", True),
        ("Urban Mobility Simulation Results", creators[5], "published", "external", False),
        ("Patient Pathway Design Notes", creators[2], "returned-feedback", "internal", False),
    ]
    for spec in paper_specs:
        print(f"  Paper: {spec[0]}")
        create_paper(*spec)

    print("Creating demo conferences...")
    conference_specs = [
        ("Education Data Partnerships Demo", creators[0], "draft", True),
        ("Health Service Dashboards Demo", creators[2], "submitted", True),
        ("Civic Data Governance Demo", creators[4], "accepted", False),
        ("Mobility Sensor Ethics Demo", creators[5], "presenting", False),
        ("Clinical AI Evaluation Demo", creators[3], "in-progress", True),
        ("Learning Platform Implementation Demo", creators[1], "presented", False),
    ]
    for spec in conference_specs:
        print(f"  Conference: {spec[0]}")
        create_conference(*spec)

    print("Mock data loaded.")
    print(f"Password for all demo users: {PASSWORD}")
    print("Key demo logins:")
    for username in [
        "demo_dean",
        "demo_admin",
        "demo_education_admin",
        "demo_education_manager",
        "demo_health_finance",
        "demo_digital_head",
    ]:
        print(f"  {username}")
    print(f"Companies/cost centres: {len(cost_centres)}")
    print("CRM alert mix: high, medium, low, missing phase dates, overdue phase dates, payment gaps, stale publications, and Oracle mismatches.")


if __name__ == "__main__":
    main()
