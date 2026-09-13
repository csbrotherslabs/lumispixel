import os

from django.core.exceptions import ValidationError

from .models import SupportTicketAttachment

MAX_SUPPORT_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_SUPPORT_ATTACHMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".pdf", ".txt", ".log", ".csv", ".doc", ".docx",
}


def validate_support_attachment(upload):
    if not upload:
        return
    if upload.size > MAX_SUPPORT_ATTACHMENT_BYTES:
        raise ValidationError("Attachments must be 10 MB or smaller.")
    extension = os.path.splitext(upload.name)[1].lower()
    if extension not in ALLOWED_SUPPORT_ATTACHMENT_EXTENSIONS:
        raise ValidationError("Unsupported attachment type. Use an image, PDF, text/log, CSV, Word document, or WebP file.")


def create_support_attachment(*, ticket, upload, comment=None, user=None, employee=None, is_internal=False):
    validate_support_attachment(upload)
    return SupportTicketAttachment.objects.create(
        ticket=ticket,
        comment=comment,
        file=upload,
        original_name=os.path.basename(upload.name)[:255],
        content_type=getattr(upload, "content_type", "") or "",
        size_bytes=upload.size,
        uploaded_by_user=user,
        uploaded_by_employee=employee,
        is_internal=is_internal,
    )
