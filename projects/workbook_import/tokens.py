from django.core import signing

from .validation import WorkbookImportPreview


TOKEN_SALT = "projects.workbook-import.v1"


class PreviewTokenError(ValueError):
    pass


def sign_preview(preview: WorkbookImportPreview, *, actor_id: int) -> str:
    return signing.dumps(
        {"actor_id": actor_id, "preview": preview.to_dict()},
        salt=TOKEN_SALT,
        compress=True,
    )


def unsign_preview(token: str, *, actor_id: int, max_age=1800) -> WorkbookImportPreview:
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
    except (signing.BadSignature, signing.SignatureExpired) as exc:
        raise PreviewTokenError("The workbook preview is invalid or has expired.") from exc
    if payload.get("actor_id") != actor_id:
        raise PermissionError("This workbook preview belongs to another user.")
    preview = WorkbookImportPreview.from_dict(payload["preview"])
    if preview.actor_id != actor_id:
        raise PermissionError("This workbook preview belongs to another user.")
    return preview
