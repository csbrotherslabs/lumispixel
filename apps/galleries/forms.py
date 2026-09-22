from datetime import datetime, time

from django import forms
from django.utils import timezone

from apps.clients.models import Client, ClientSession

from .models import Album, DiscountCode, Gallery, GalleryStore, GallerySettings, StoreProduct


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = GalleryStore
        fields = ("enabled", "name", "message", "currency", "collect_sales_tax", "expires_at", "minimum_order_amount", "digital_delivery_enabled", "delivery_message")
        widgets = {"message": forms.Textarea(attrs={"rows": 3}), "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].widget = forms.Select(choices=(("USD", "USD — US Dollar"), ("CAD", "CAD — Canadian Dollar"), ("EUR", "EUR — Euro"), ("GBP", "GBP — British Pound")))
        for field in self.fields.values(): field.widget.attrs.setdefault("class", "lpw-form-control")


class StoreProductForm(forms.ModelForm):
    variants = forms.CharField(required=False, help_text="One size or variant per line (for example: 8 × 10).", widget=forms.Textarea(attrs={"rows": 4}))
    class Meta:
        model = StoreProduct
        fields = ("name", "product_type", "description", "image", "price", "sale_price", "fulfillment", "download_resolution", "maximum_download_count", "active", "display_order")
        widgets = {"description": forms.Textarea(attrs={"rows": 5}), "image": forms.FileInput(attrs={"accept": "image/*"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs.setdefault("class", "lpw-form-control")
        if self.instance.pk: self.fields["variants"].initial = "\n".join(self.instance.variants.values_list("name", flat=True))


class DiscountCodeForm(forms.ModelForm):
    class Meta:
        model = DiscountCode
        fields = ("code", "discount_type", "amount", "minimum_order", "starts_at", "expires_at", "usage_limit", "active")
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type":"datetime-local"}), "expires_at": forms.DateTimeInput(attrs={"type":"datetime-local"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values(): field.widget.attrs.setdefault("class", "lpw-form-control")
    def clean_code(self): return self.cleaned_data["code"].strip().upper()


class BookingSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-client-id"] = str(instance.client_id)
        return option


class GalleryForm(forms.ModelForm):
    expiration_date = forms.DateField(
        required=False,
        label="Expiration date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = Gallery
        fields = ("name", "client", "booking", "event_date", "description", "design_template", "cover_image", "status", "visibility")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Add a short note for your team or client…"}),
            "cover_image": forms.FileInput(attrs={"accept": "image/*", "data-cover-input": ""}),
        }

    def __init__(self, *args, photographer, **kwargs):
        super().__init__(*args, **kwargs)
        self.photographer = photographer
        self.instance.photographer = photographer
        self.fields["design_template"].label = "Gallery design"
        self.fields["design_template"].help_text = "Choose how this gallery will be presented to clients. You can change the design later without affecting photos or access settings."
        self.fields["client"].queryset = Client.objects.for_photographer(photographer).order_by("first_name", "last_name")
        self.fields["client"].required = False
        self.fields["client"].empty_label = "Search or choose a client"
        self.fields["booking"].queryset = ClientSession.objects.for_photographer(photographer).filter(
            event_kind=ClientSession.EventKind.BOOKING
        ).select_related("client").order_by("-starts_at", "-pk")
        self.fields["booking"].required = False
        self.fields["booking"].label = "Booking / shoot"
        self.fields["booking"].empty_label = "No booking linked"
        self.fields["booking"].help_text = "Connect this gallery to the booking that produced it."
        self.fields["booking"].widget = BookingSelect(attrs={"data-gallery-booking-select": ""})
        self.fields["booking"].widget.choices = self.fields["booking"].choices
        if self.instance and self.instance.expires_at:
            self.fields["expiration_date"].initial = timezone.localtime(self.instance.expires_at).date()
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "lpw-form-control")
            field.widget.attrs.setdefault("id", f"gallery-{name.replace('_', '-')}")

    def clean_expiration_date(self):
        expiration = self.cleaned_data.get("expiration_date")
        event_date = self.cleaned_data.get("event_date")
        if expiration and event_date and expiration < event_date:
            raise forms.ValidationError("Expiration date must be on or after the event date.")
        return expiration

    def clean(self):
        cleaned_data = super().clean()
        expiration = cleaned_data.get("expiration_date")
        status = cleaned_data.get("status")
        client = cleaned_data.get("client")
        booking = cleaned_data.get("booking")
        if booking:
            if booking.photographer_id != self.photographer.id:
                self.add_error("booking", "Choose a booking belonging to this photographer.")
            elif not client or booking.client_id != client.id:
                self.add_error("booking", "Choose a booking belonging to the selected client.")
        if expiration and status == Gallery.Status.PUBLISHED:
            expires_at = timezone.make_aware(datetime.combine(expiration, time.max))
            published_at = self.instance.published_at if self.instance and self.instance.published_at else timezone.now()
            if expires_at <= published_at:
                self.add_error("expiration_date", "Expiration date must be after the gallery is published.")
        return cleaned_data

    def save(self, commit=True):
        gallery = super().save(commit=False)
        gallery.photographer = self.photographer
        expiration = self.cleaned_data.get("expiration_date")
        gallery.expires_at = timezone.make_aware(datetime.combine(expiration, time.max)) if expiration else None
        if commit:
            gallery.save()
            self.save_m2m()
        return gallery


class AlbumForm(forms.ModelForm):
    class Meta:
        model = Album
        fields = ("name", "description", "visibility", "cover_image", "display_order")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe the story this collection tells…"}),
            "cover_image": forms.FileInput(attrs={"accept": "image/*"}),
            "display_order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, gallery, **kwargs):
        super().__init__(*args, **kwargs)
        self.gallery = gallery
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "lpw-form-control")
            field.widget.attrs.setdefault("id", f"album-{name.replace('_', '-')}")

    def validate_unique(self):
        self.instance.gallery = self.gallery
        super().validate_unique()


class GallerySettingsForm(forms.ModelForm):
    class Meta:
        model = GallerySettings
        exclude = (
            "gallery",
            # Client authorization lives exclusively in GalleryPermission.
            "allow_downloads",
            "allow_original_downloads",
            "enable_favorites",
            "enable_comments",
        )
        widgets = {
            "studio_logo": forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
            "download_limit": forms.NumberInput(attrs={"min": 1, "placeholder": "Unlimited"}),
            "meta_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, photographer, **kwargs):
        super().__init__(*args, **kwargs)
        self.photographer = photographer
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "lpw-form-control")

    def clean_accent_color(self):
        value = self.cleaned_data["accent_color"].upper()
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789ABCDEF" for c in value[1:]):
            raise forms.ValidationError("Enter a valid six-digit hex color.")
        return value

    def clean_gallery_url(self):
        slug = self.cleaned_data["gallery_url"]
        queryset = GallerySettings.objects.filter(gallery__photographer=self.photographer, gallery_url=slug)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("You already use this gallery URL.")
        return slug
