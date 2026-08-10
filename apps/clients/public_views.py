from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse

from apps.core.views import add
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods

from apps.clients.contracts import (ContractSignatureForm, DEFAULT_SIGNATURE_CONSENT,
                                    open_contract_review, send_signed_contract_copy_link, sign_contract)
from apps.clients.models import SignedContractDocument

add(
    "for_clients",
    "For Clients",
    "Products",
    description="Help clients find, view, favorite, and purchase photography through simple LumisPixel experiences.",
)


def for_clients(request):
    context = {
        "pain_points": [
            {"icon": "bi-arrow-down-up", "text": "Endless gallery scrolling"},
            {"icon": "bi-person-bounding-box", "text": "Hard to find yourself"},
            {"icon": "bi-link-45deg", "text": "Lost gallery links"},
            {"icon": "bi-images", "text": "Too many similar images"},
            {"icon": "bi-download", "text": "Confusing download steps"},
            {"icon": "bi-chat-dots", "text": "Asking the photographer for help"},
            {"icon": "bi-share", "text": "Difficult sharing with family"},
            {"icon": "bi-bag", "text": "Unclear print options"},
        ],
        "selfie_steps": [
            "Upload a Selfie",
            "LumisPixel Searches the Gallery",
            "View Your Matching Photos",
            "Favorite, Download, or Order",
        ],
        "comparison": [
            {
                "traditional": "Scroll through hundreds or thousands of photos",
                "lumis": "Start with a selfie search",
            },
            {
                "traditional": "Search every folder manually",
                "lumis": "View likely matching photos",
            },
            {
                "traditional": "Ask the photographer for help",
                "lumis": "Create a favorites collection",
            },
            {
                "traditional": "Save photos one at a time",
                "lumis": "Download available photos easily",
            },
            {
                "traditional": "Lose track of favorites",
                "lumis": "Share your collection with family",
            },
        ],
        "gallery_features": [
            "Beautiful gallery viewing",
            "Favorites",
            "Collections",
            "Slideshows",
            "Mobile-friendly browsing",
            "High-quality previews",
            "Easy navigation",
            "Photographer branding",
        ],
        "enjoy_options": [
            (
                "Digital Downloads",
                "Save available images when your photographer enables downloads.",
            ),
            ("Prints", "Order printed memories when products are available."),
            ("Albums", "Turn favorite moments into a keepsake album when offered."),
            ("Frames", "Choose framed options from supported galleries."),
            ("Canvas", "Create wall-ready artwork when enabled."),
            ("Wall Art", "Explore larger display pieces through available products."),
            ("Photo Packages", "Select bundled options your photographer provides."),
            ("Gift Options", "Share memories through available gifts and keepsakes."),
        ],
        "sharing": [
            "Shareable gallery links",
            "QR codes",
            "Favorites collections",
            "Private links",
            "Password-protected access",
            "Mobile sharing",
            "Family downloads when enabled",
        ],
        "privacy": [
            "Password-protected galleries",
            "Private gallery links",
            "Download permissions",
            "Watermarks",
            "Gallery expiration settings",
            "Photographer-controlled access",
        ],
        "screens": [
            "Responsive galleries",
            "Simple browser access",
            "Touch-friendly controls",
        ],
        "journey": [
            "Attend a wedding, tournament, graduation, or special event.",
            "The photographer uploads the finished gallery.",
            "Receive a private link or event access code.",
            "Browse the gallery or upload a selfie to narrow results.",
            "Save your favorite moments.",
            "Download available images or order keepsakes.",
            "Share memories with family and friends.",
        ],
        "memory_types": [
            ("Weddings", "bi-heart"),
            ("Family Portraits", "bi-people"),
            ("Graduations", "bi-mortarboard"),
            ("Youth Sports", "bi-trophy"),
            ("School Events", "bi-building"),
            ("Corporate Events", "bi-briefcase"),
            ("Conferences", "bi-mic"),
            ("Festivals", "bi-music-note-beamed"),
            ("Races and Marathons", "bi-stopwatch"),
            ("Parties", "bi-balloon"),
            ("Community Events", "bi-calendar-event"),
            ("Travel Experiences", "bi-airplane"),
        ],
        "faqs": [
            (
                "Do I need an account to view a gallery?",
                "Some galleries may open from a private link, while others may require an account, password, or event code.",
            ),
            (
                "How do I find my event or gallery?",
                "Use the link, QR code, or event details shared by your photographer. If access does not work, contact the photographer.",
            ),
            (
                "Can I use a selfie to find my photos?",
                "Selfie search is designed to help locate likely matches when the photographer enables it for that gallery.",
            ),
            (
                "Are my photos private?",
                "Photographers can control who accesses a gallery and which actions are available.",
            ),
            (
                "Can I download my photos?",
                "Downloads depend on the photographer’s settings, package, and gallery permissions.",
            ),
            (
                "Can I order prints or albums?",
                "Prints, albums, and products may be available when your photographer offers them for the gallery.",
            ),
            (
                "Can I share photos with family and friends?",
                "You may be able to share a gallery link or favorites collection when sharing is enabled.",
            ),
            (
                "What should I do if I cannot find myself?",
                "Try a clear selfie and check related folders. If you still need help, contact your photographer.",
            ),
            (
                "How long will my gallery remain available?",
                "Gallery availability is determined by the photographer and may vary by event or package.",
            ),
            (
                "Who controls gallery access and pricing?",
                "Your photographer controls access, products, prices, downloads, and gallery availability.",
            ),
        ],
    }
    return render(request, "for_clients.html", context)


@require_http_methods(["GET", "POST"])
def contract_review(request, token):
    contract = open_contract_review(token)
    if contract is None:
        raise Http404("This contract review link is invalid or has expired.")
    form = ContractSignatureForm(request.POST or None)
    if request.method == "POST" and contract.status != contract.Status.SIGNED and form.is_valid():
        ip_address = request.META.get("REMOTE_ADDR") or None
        try:
            sign_contract(raw_token=token, ip_address=ip_address,
                          user_agent=request.META.get("HTTP_USER_AGENT", ""), **form.cleaned_data)
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.add_error(None, exc.messages[0])
        else:
            contract.refresh_from_db()
            try:
                send_signed_contract_copy_link(
                    contract=contract,
                    signed_pdf_url=request.build_absolute_uri(
                        reverse("clients:signed-contract-pdf-download", args=[token])
                    ),
                )
            except Exception:
                # The signed record and PDF status remain authoritative; email can be retried separately.
                pass
    return render(request, "clients/contracts/review.html", {
        "contract": contract, "form": form, "token": token,
        "consent_text": getattr(settings, "CONTRACT_SIGNATURE_CONSENT_TEXT", DEFAULT_SIGNATURE_CONSENT),
    })


def signed_contract_pdf(request, token, disposition="inline"):
    contract = open_contract_review(token)
    if contract is None or contract.status != contract.Status.SIGNED:
        raise Http404("This signed contract link is invalid or has expired.")
    document = getattr(contract, "signed_document", None)
    if document is None or document.status != SignedContractDocument.Status.READY:
        raise Http404("The signed contract PDF is not available.")
    response = FileResponse(document.file.open("rb"), content_type=document.content_type)
    response["Content-Disposition"] = f'{disposition}; filename="signed-contract-{contract.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
