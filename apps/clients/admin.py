from django.contrib import admin

from .models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead


class PhotographerOwnedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.for_user(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == "photographer":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Lead)
class LeadAdmin(PhotographerOwnedAdmin):
    list_display = ("first_name", "last_name", "email", "event_type", "status", "event_date", "photographer")
    list_filter = ("status", "event_type", "lead_source")
    search_fields = ("first_name", "last_name", "email", "phone")
    date_hierarchy = "created_at"


@admin.register(Client)
class ClientAdmin(PhotographerOwnedAdmin):
    list_display = ("first_name", "last_name", "email", "company", "status", "photographer")
    list_filter = ("status",)
    search_fields = ("first_name", "last_name", "email", "phone", "company")


@admin.register(ClientNote)
class ClientNoteAdmin(PhotographerOwnedAdmin):
    list_display = ("client", "photographer", "created_at")
    search_fields = ("client__first_name", "client__last_name", "content")


@admin.register(ClientTask)
class ClientTaskAdmin(PhotographerOwnedAdmin):
    list_display = ("title", "priority", "status", "due_date", "photographer")
    list_filter = ("priority", "status")
    search_fields = ("title", "client__first_name", "client__last_name", "lead__first_name", "lead__last_name")


@admin.register(ClientActivity)
class ClientActivityAdmin(PhotographerOwnedAdmin):
    list_display = ("event_type", "lead", "client", "occurred_at", "photographer")
    list_filter = ("event_type",)
    search_fields = ("description", "client__first_name", "client__last_name", "lead__first_name", "lead__last_name")
    date_hierarchy = "occurred_at"


@admin.register(ClientSession)
class ClientSessionAdmin(PhotographerOwnedAdmin):
    list_display = ("client", "session_type", "starts_at", "location", "status", "photographer")
    list_filter = ("status", "session_type")
    search_fields = ("client__first_name", "client__last_name", "location")


@admin.register(ClientInvoice)
class ClientInvoiceAdmin(PhotographerOwnedAdmin):
    list_display = ("client", "total", "amount_paid", "due_date", "status", "photographer")
    list_filter = ("status",)
    search_fields = ("client__first_name", "client__last_name")
