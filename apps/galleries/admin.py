from django.contrib import admin

from .models import Album, AlbumPhoto, Gallery


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ("name", "photographer", "client", "status", "visibility", "image_count", "updated_at")
    list_filter = ("status", "visibility")
    search_fields = ("name", "slug", "photographer__business_name", "client__first_name", "client__last_name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("name", "gallery", "visibility", "display_order", "updated_at")
    list_filter = ("visibility",)
    search_fields = ("name", "gallery__name")


admin.site.register(AlbumPhoto)
