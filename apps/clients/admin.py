from django.contrib import admin

from .models import Client, ClientActivity, ClientInvoice, ClientNote, ClientSession, ClientTask, Lead


class PhotographerOwnedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.for_user(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            related_model = db_field.remote_field.model
            if db_field.name == "photographer":
                kwargs["queryset"] = related_model.objects.filter(user=request.user)
            elif issubclass(related_model, (Lead, Client)):
                kwargs["queryset"] = related_model.objects.for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Lead)
class LeadAdmin(PhotographerOwnedAdmin):
    list_display = ("first_name", "last_name", "email", "event_type", "status", "event_date", "next_follow_up", "photographer")
    list_filter = ("status", "event_type", "lead_source")
    search_fields = ("first_name", "last_name", "email", "phone")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "last_contacted_at")


@admin.register(Client)
class ClientAdmin(PhotographerOwnedAdmin):
    list_display = ("first_name", "last_name", "email", "company", "client_type", "status", "photographer", "updated_at")
    list_filter = ("status", "client_type", "preferred_contact_method")
    search_fields = ("first_name", "last_name", "email", "phone", "company", "tags")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "converted_lead")
    date_hierarchy = "created_at"


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
