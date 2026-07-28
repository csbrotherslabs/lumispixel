from django.contrib import admin

from .models import Gallery


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ("name", "photographer", "client", "status", "visibility", "image_count", "updated_at")
    list_filter = ("status", "visibility")
    search_fields = ("name", "slug", "photographer__business_name", "client__first_name", "client__last_name")
    prepopulated_fields = {"slug": ("name",)}
