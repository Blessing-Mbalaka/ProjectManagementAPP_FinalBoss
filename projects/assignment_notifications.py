from django.urls import reverse

from adminpanel.models import Notification
from users.email_service import send_html_email_safely


def notify_project_assignment(*, request, project, recipient, responsibility=""):
    """Create an in-app assignment notice and attempt its companion email."""
    responsibility = (responsibility or "").strip()
    notification = Notification.objects.create(
        title=f"Assigned to project: {project.name}",
        body=(
            f"You were assigned to {project.name}. Responsibility: {responsibility}"
            if responsibility
            else f"You were assigned to {project.name}."
        ),
        priority="high",
        audience="specific",
        created_by=request.user,
    )
    notification.recipients.add(recipient)

    kanban_name = "manager_kanban" if recipient.role == "manager" else "staff_kanban"
    kanban_url = request.build_absolute_uri(reverse(kanban_name))
    assigner_name = request.user.get_full_name() or request.user.username
    context = {
        "recipient": recipient,
        "project": project,
        "responsibility": responsibility,
        "assigner_name": assigner_name,
        "kanban_url": kanban_url,
    }
    text_body = (
        f"Hello {recipient.get_full_name() or recipient.username},\n\n"
        f"{assigner_name} assigned you to the project '{project.name}'.\n"
        f"Responsibility: {responsibility or 'View the project Kanban for details.'}\n\n"
        f"Open your Kanban: {kanban_url}"
    )
    return send_html_email_safely(
        subject=f"Project assignment: {project.name}",
        recipient=recipient.email,
        text_body=text_body,
        html_template="emails/project_assignment.html",
        context=context,
    )
