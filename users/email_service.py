import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string


logger = logging.getLogger(__name__)


def send_html_email_safely(*, subject, recipient, text_body, html_template, context):
    """Send a multipart email without allowing delivery errors to break a request."""
    recipient = (recipient or "").strip()
    try:
        validate_email(recipient)
    except ValidationError:
        logger.warning("Email skipped because recipient address is invalid: %r", recipient)
        return False

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(render_to_string(html_template, context), "text/html")
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Email delivery failed for recipient %s", recipient)
        return False
