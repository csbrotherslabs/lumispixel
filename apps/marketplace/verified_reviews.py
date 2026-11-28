from datetime import timedelta
import hashlib
import secrets
from apps.notifications.email_delivery import queue_transactional_email, public_url
from django.template.loader import render_to_string
from django.core.cache import cache
from django.db.models import Q

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import PhotographerWebsiteProfile
from apps.clients.models import Client, ClientSession
from .models import BookingReview, PlatformBooking


class BookingRequestForm(forms.Form):
    session_type = forms.ChoiceField(label="Photography service", widget=forms.RadioSelect)
    duration_minutes = forms.TypedChoiceField(label="Estimated duration", choices=[(n, f"{n} minutes") for n in (30,60,120,180,240,360,480,720)], coerce=int)
    location = forms.CharField(max_length=255, label="Event location")
    guests = forms.IntegerField(min_value=1, max_value=100000, required=False, label="Number of guests")
    budget = forms.ChoiceField(required=False, choices=[("", "Not sure yet")]+[(v,v) for v in ("Under $500","$500–$1,000","$1,000–$2,500","$2,500–$5,000","$5,000+")], label="Estimated budget (USD)")
    description = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={"rows":4}), label="Tell us about your project")
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField(label="Client email address")
    phone = forms.CharField(max_length=32, required=False)
    contact_method = forms.ChoiceField(choices=[("email","Email"),("phone","Phone")], label="Preferred contact method")
    acknowledge = forms.BooleanField(label="I understand this is a request, not a confirmed booking or payment.")

    def __init__(self, *args, specialties=(), verified_email=None, **kwargs):
        super().__init__(*args, **kwargs)
        if verified_email:
            self.fields["email"].disabled = True
            self.initial["email"] = verified_email
        placeholders = {"location": "Venue, address or city", "guests": "e.g. 50", "description": "Tell us about your vision, occasion and any special requests...", "first_name": "First name", "last_name": "Last name", "email": "name@example.com", "phone": "e.g. +1 555 123 4567"}
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder
        for name, autocomplete in {"first_name": "given-name", "last_name": "family-name", "email": "email", "phone": "tel"}.items():
            self.fields[name].widget.attrs["autocomplete"] = autocomplete
        self.fields["phone"].widget.attrs["inputmode"] = "tel"
        self.fields["session_type"].choices = [(name, name) for name in specialties] or [("Other photography","Other photography")]

    def clean(self):
        data = super().clean()
        if data.get("contact_method") == "phone" and not data.get("phone"):
            self.add_error("phone", "Enter a phone number for phone contact.")
        return data
    starts_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Requested date and time")

    def clean_starts_at(self):
        value = self.cleaned_data["starts_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Choose a future date.")
        return value


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(5, 0, -1)], coerce=int)
    comment = forms.CharField(max_length=3000, widget=forms.Textarea)


def customer_allowed(user, photographer):
    return (user.is_authenticated and user.is_active and user.email_verified
            and user.account_status == user.AccountStatus.ACTIVE
            and user.pk != photographer.user_id)


def eligible_bookings(user, photographer):
    qs = PlatformBooking.objects.none()
    if customer_allowed(user, photographer):
        qs = PlatformBooking.objects.filter(
            customer=user, photographer=photographer,
            session__photographer=photographer,
            session__client__photographer=photographer,
            session__client__user=user,
            session__event_kind=ClientSession.EventKind.BOOKING,
            session__status=ClientSession.Status.COMPLETED,
            session__starts_at__lte=timezone.now(),
            review__isnull=True,
        ).filter(Q(origin="client") | Q(acknowledged_at__isnull=False, client_email__iexact=user.email))
    return qs.select_related("session")


def review_context(request, photographer, draft_preview=False):
    reviews = BookingReview.objects.filter(booking__photographer=photographer).select_related("booking__customer")
    summary = reviews.aggregate(average=Avg("rating"))
    page = Paginator(reviews, 6).get_page(request.GET.get("reviews_page", 1))
    return {"review_page": page, "review_average": summary["average"],
            "review_count": page.paginator.count,
            "eligible_reviews": eligible_bookings(request.user, photographer) if not draft_preview else PlatformBooking.objects.none()}


def published_website(slug):
    website = get_object_or_404(PhotographerWebsiteProfile.objects.select_related("photographer_profile__user"), photographer_profile__slug=slug)
    if not (website.theme_content or {}).get("_published_website"):
        from django.http import Http404
        raise Http404
    return website


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@require_http_methods(["GET", "POST"])
def request_booking(request, slug):
    website = published_website(slug)
    photographer = website.photographer_profile
    user = request.user
    assisted = user.is_authenticated and user.pk == photographer.user_id
    if assisted and not (user.is_active and user.email_verified and user.account_status == user.AccountStatus.ACTIVE):
        return HttpResponseForbidden("An active verified photographer account is required.")
    direct = customer_allowed(user, photographer)
    published = website.theme_content["_published_website"]
    form = BookingRequestForm(request.POST if request.method == "POST" else None,
        specialties=published.get("specialties", []), verified_email=user.email if direct else None,
        initial={"first_name": user.first_name, "last_name": user.last_name} if direct else {})
    context = {"form": form, "slug": slug, "brand": published.get("brand") or photographer.display_name,
               "assisted": assisted, "direct": direct, "booking_timezone": timezone.get_current_timezone_name()}
    context["booking_cover"] = website.hero_image.storage.url(published["hero_image"]) if published.get("hero_image") else ""
    context["booking_portrait"] = photographer.profile_photo.storage.url(published["portrait"]) if published.get("portrait") else ""
    if request.method == "GET" and request.session.pop("booking_sent_" + slug, False):
        context["success"] = True
        context["pending"] = not direct
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        email = data["email"].strip().lower()
        if email == photographer.user.email.lower():
            form.add_error("email", "Enter your client's email, not the photographer's email.")
        else:
            if not direct:
                key = "booking-email:" + digest(email)
                if not cache.add(key, 1, timeout=60):
                    form.add_error(None, "Please wait a minute before requesting another verification email.")
                    return render(request, "marketplace/booking_request.html", context)
            token = secrets.token_urlsafe(32)
            with transaction.atomic():
                client = Client.objects.filter(photographer=photographer, user=user).first() if direct else None
                if client is None:
                    client = Client.objects.create(photographer=photographer, user=user if direct else None,
                        first_name=data["first_name"], last_name=data["last_name"], email=email,
                        phone=data["phone"], preferred_contact_method=data["contact_method"])
                session = ClientSession.objects.create(photographer=photographer, client=client,
                    session_type=data["session_type"], starts_at=data["starts_at"],
                    duration_minutes=data["duration_minutes"], location=data["location"],
                    notes="\n".join([("Verified client request" if direct else "Pending client verification"),
                        f"Guests: {data['guests'] or 'Not specified'}", f"Budget (USD): {data['budget'] or 'Not specified'}", data["description"]]),
                    status=ClientSession.Status.TENTATIVE, event_kind=ClientSession.EventKind.BOOKING)
                booking = PlatformBooking.objects.create(session=session, customer=user if direct else None,
                    photographer=photographer, created_by=user if user.is_authenticated else None,
                    origin="client" if direct else ("photographer" if assisted else "guest"), client_email=email,
                    acknowledged_at=timezone.now() if direct else None,
                    verification_digest="" if direct else digest(token),
                    verification_expires_at=None if direct else timezone.now()+timedelta(hours=48))
                if not direct:
                    link = public_url(reverse("public-booking-verify", kwargs={"slug":slug,"token":token}))
                    try:
                        email_context = {"client_name": data["first_name"], "studio_name": context["brand"],
                            "session": session, "verification_url": link,
                            "booking_timezone": context["booking_timezone"]}
                        sent = queue_transactional_email(event_key=f"booking.acknowledgment:{booking.pk}",
                            subject="Acknowledge your LumisPixel booking request",
                            plain_body=render_to_string("marketplace/email/booking_acknowledgment.txt", email_context),
                            recipients=[email], sensitive=True, expires_at=booking.verification_expires_at,
                            lifecycle_kind="booking.acknowledgment",
                            lifecycle_context={"booking_id": booking.pk, "studio_id": photographer.pk, "digest": booking.verification_digest},
                            html_body=render_to_string("marketplace/email/booking_acknowledgment.html", email_context))
                        if not sent:
                            raise RuntimeError("Email not sent")
                    except Exception:
                        transaction.set_rollback(True)
                        form.add_error(None, "Verification email could not be queued. Please try again later.")
                        return render(request, "marketplace/booking_request.html", context)
            if direct:
                from .booking_approval import notify_photographer
                notify_photographer(session.pk, "A verified client booking is awaiting your approval.")
            request.session["booking_sent_" + slug] = True
            return redirect("public-photographer-booking", slug=slug)
    return render(request, "marketplace/booking_request.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def verify_booking(request, slug, token):
    website = published_website(slug)
    photographer = website.photographer_profile
    if not customer_allowed(request.user, photographer):
        return HttpResponseForbidden("Sign in with your own verified client account to acknowledge this request.")
    with transaction.atomic():
        booking = get_object_or_404(PlatformBooking.objects.select_for_update(), photographer=photographer,
            verification_digest=digest(token), verification_expires_at__gt=timezone.now(),
            acknowledged_at__isnull=True, customer__isnull=True, client_email__iexact=request.user.email)
        session = ClientSession.objects.select_for_update().get(pk=booking.session_id)
        client = Client.objects.select_for_update().get(pk=session.client_id)
        if (session.photographer_id != photographer.pk or client.photographer_id != photographer.pk
            or client.user_id is not None or client.email.lower() != booking.client_email.lower()
            or session.status != ClientSession.Status.TENTATIVE):
            return HttpResponseForbidden("This request is no longer eligible for verification.")
        if request.method == "POST":
            if request.POST.get("acknowledge") != "yes":
                return HttpResponseForbidden("Please acknowledge the booking details.")
            client.user = request.user
            client.save(update_fields=["user"])
            booking.customer = request.user
            booking.acknowledged_at = timezone.now()
            booking.verification_digest = ""
            booking.save(update_fields=["customer","acknowledged_at","verification_digest"])
            session.notes = session.notes.replace("Pending client verification", "Client verified and acknowledged", 1)
            session.save(update_fields=["notes"])
            if booking.origin == "photographer":
                from .booking_approval import confirm_booking
                confirm_booking(session, actor=request.user, client_acknowledgment=True)
            else:
                from .booking_approval import notify_photographer
                transaction.on_commit(lambda: notify_photographer(session.pk, "A verified client booking is awaiting your approval."))
            return render(request, "marketplace/booking_verify.html", {"success":True,"slug":slug})
    return render(request, "marketplace/booking_verify.html", {"booking":booking,"session":session,"slug":slug})


@login_required
@require_http_methods(["GET", "POST"])
def submit_review(request, slug, booking_id):
    website = published_website(slug)
    photographer = website.photographer_profile
    booking = get_object_or_404(eligible_bookings(request.user, photographer), pk=booking_id)
    form = ReviewForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Lock both provenance and session; recheck eligibility after locking.
            PlatformBooking.objects.select_for_update().get(pk=booking.pk)
            session = ClientSession.objects.select_for_update().get(pk=booking.session_id)
            booking = get_object_or_404(eligible_bookings(request.user, photographer), pk=booking.pk)
            if session.starts_at + timedelta(minutes=session.duration_minutes) > timezone.now():
                return HttpResponseForbidden("The session must have ended.")
            BookingReview.objects.create(booking=booking, **form.cleaned_data)
        return redirect(reverse("public-photographer-website", kwargs={"slug": slug}) + "#reviews")
    return render(request, "marketplace/verified_booking_form.html", {"heading": "Write a verified review", "form": form, "slug": slug})
