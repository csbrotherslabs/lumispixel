"""Invoice workspace mutations that require real client email delivery."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.clients.models import ClientInvoice
from apps.dashboard.invoices import InvoiceDeliveryError, save_invoice, send_existing_invoice

from . import views as workspace_views


@workspace_views.photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_create(request):
    if request.method == "POST":
        try:
            invoice = save_invoice(
                request.studio,
                request.POST,
                send=request.POST.get("intent") == "send",
            )
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return render(
                request,
                "photographer_workspace/invoices/form.html",
                workspace_views._invoice_context(request, errors=errors),
                status=400,
            )
        except InvoiceDeliveryError:
            return render(
                request,
                "photographer_workspace/invoices/form.html",
                workspace_views._invoice_context(
                    request,
                    errors={"__all__": [
                        "The email could not be delivered. The invoice was not marked as sent."
                    ]},
                ),
                status=502,
            )
        messages.success(
            request,
            f"{invoice.invoice_number} was "
            f"{'sent' if invoice.status == ClientInvoice.Status.SENT else 'saved as a draft'}.",
        )
        return redirect("photographer_workspace:invoice_view", pk=invoice.pk)
    return render(
        request,
        "photographer_workspace/invoices/form.html",
        workspace_views._invoice_context(request),
    )


@workspace_views.photographer_workspace_required
@require_http_methods(["GET", "POST"])
def invoice_edit(request, pk):
    invoice = get_object_or_404(
        ClientInvoice.objects.for_photographer(request.studio).prefetch_related(
            "line_items", "payment_schedule"
        ),
        pk=pk,
    )
    if invoice.status != ClientInvoice.Status.DRAFT:
        messages.error(request, "Only draft invoices can be edited.")
        return redirect("photographer_workspace:invoice_view", pk=pk)
    if request.method == "POST":
        try:
            invoice = save_invoice(
                request.studio,
                request.POST,
                invoice,
                request.POST.get("intent") == "send",
            )
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return render(
                request,
                "photographer_workspace/invoices/form.html",
                workspace_views._invoice_context(request, invoice, errors),
                status=400,
            )
        except InvoiceDeliveryError:
            invoice.refresh_from_db()
            return render(
                request,
                "photographer_workspace/invoices/form.html",
                workspace_views._invoice_context(
                    request,
                    invoice,
                    {"__all__": [
                        "The email could not be delivered. The invoice was not marked as sent."
                    ]},
                ),
                status=502,
            )
        messages.success(
            request,
            "Invoice sent." if invoice.status == ClientInvoice.Status.SENT else "Invoice updated.",
        )
        return redirect("photographer_workspace:invoice_view", pk=pk)
    return render(
        request,
        "photographer_workspace/invoices/form.html",
        workspace_views._invoice_context(request, invoice),
    )


@workspace_views.photographer_workspace_required
@require_POST
def invoice_action(request, pk, action):
    if action not in {"send", "resend"}:
        return workspace_views.invoice_action(request, pk, action)

    invoice = get_object_or_404(
        ClientInvoice.objects.for_photographer(request.studio),
        pk=pk,
    )
    try:
        send_existing_invoice(request.studio, invoice, action=action)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    except InvoiceDeliveryError:
        messages.error(
            request,
            "The email could not be delivered. The invoice was not marked as sent.",
        )
    else:
        messages.success(request, "Invoice sent.")
    return redirect("photographer_workspace:invoice_view", pk=pk)
