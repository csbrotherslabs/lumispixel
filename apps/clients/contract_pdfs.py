"""Private signed-contract PDF generation from immutable acceptance evidence."""
import hashlib
import secrets
import textwrap

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from .models import Contract, SignedContractDocument


def build_signed_snapshot(contract, signature):
    """Capture every PDF input while the signed contract and its relations are locked."""
    booking = contract.booking
    studio = contract.photographer
    return {
        "business_name": studio.business_name or studio.display_name or studio.user.full_name or studio.user.email,
        "contract_id": contract.pk,
        "contract_version": signature.contract_version,
        "title": contract.title,
        "content": contract.rendered_content,
        "client_name": str(contract.client),
        "client_email": contract.client.email,
        "booking_id": booking.pk,
        "booking_service": booking.session_type,
        "booking_starts_at": booking.starts_at.isoformat(),
        "booking_location": booking.location,
        "signer_name": signature.signer_name,
        "signature_value": signature.signature_value,
        "signature_type": signature.signature_type,
        "signed_at": signature.signed_at.isoformat(),
        "signed_content_hash": signature.content_hash,
    }


def render_signed_contract_pdf(snapshot):
    """Render a dependency-free PDF using only the stored signed snapshot."""
    lines = [snapshot["business_name"], snapshot["title"], "",
             f'Contract: {snapshot["contract_id"]} | Version {snapshot["contract_version"]}',
             f'Client: {snapshot["client_name"]} ({snapshot["client_email"]})',
             f'Booking: {snapshot["booking_id"]} | {snapshot["booking_service"]}',
             f'Scheduled: {snapshot["booking_starts_at"]}',
             f'Location: {snapshot["booking_location"] or "Not provided"}', ""]
    for source_line in snapshot["content"].splitlines() or [""]:
        lines.extend(textwrap.wrap(source_line, width=92, replace_whitespace=False) or [""])
    lines.extend(["", f'Signed by: {snapshot["signer_name"]}',
                  f'Typed signature: {snapshot["signature_value"]}',
                  f'Signed at: {snapshot["signed_at"]}',
                  f'Signed content SHA-256: {snapshot["signed_content_hash"]}'])

    def pdf_text(value):
        encoded = value.encode("cp1252", "replace").decode("latin-1")
        return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[index:index + 48] for index in range(0, len(lines), 48)] or [[]]
    objects = [b"", b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    page_ids = []
    font_object_id = 3 + len(pages) * 2
    for page_lines in pages:
        page_id = len(objects)
        content_id = page_id + 1
        page_ids.append(page_id)
        commands = ["BT", "/F1 11 Tf", "14 TL", "54 738 Td"]
        for line in page_lines:
            commands.extend([f"({pdf_text(str(line))}) Tj", "T*"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects[2] = f'<< /Type /Pages /Count {len(page_ids)} /Kids [{" ".join(f"{pid} 0 R" for pid in page_ids)}] >>'.encode()
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects[1:], 1):
        offsets.append(len(pdf)); pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def generate_signed_contract_pdf(contract_id):
    """Create or retry a copy without ever overwriting a successfully generated file."""
    contract = Contract.objects.select_related("signature").get(pk=contract_id, status=Contract.Status.SIGNED)
    signature = contract.signature
    document, _ = SignedContractDocument.objects.get_or_create(
        contract=contract, defaults={"signed_content_hash": signature.content_hash},
    )
    if document.status == SignedContractDocument.Status.READY and document.file:
        return document
    try:
        pdf = render_signed_contract_pdf(signature.signed_snapshot)
        digest = hashlib.sha256(pdf).hexdigest()
        filename = f"signed-{contract.pk}-v{signature.contract_version}-{secrets.token_hex(8)}.pdf"
        with transaction.atomic():
            document = SignedContractDocument.objects.select_for_update().get(pk=document.pk)
            if document.status == SignedContractDocument.Status.READY and document.file:
                return document
            document.file.save(filename, ContentFile(pdf), save=False)
            document.status = SignedContractDocument.Status.READY
            document.generated_at = timezone.now()
            document.content_type = "application/pdf"
            document.file_size = len(pdf)
            document.file_hash = digest
            document.signed_content_hash = signature.content_hash
            document.error_message = ""
            document.save()
        return document
    except Exception as exc:
        SignedContractDocument.objects.update_or_create(
            contract=contract,
            defaults={"status": SignedContractDocument.Status.FAILED,
                      "signed_content_hash": signature.content_hash,
                      "error_message": str(exc)[:255]},
        )
        return SignedContractDocument.objects.get(contract=contract)
