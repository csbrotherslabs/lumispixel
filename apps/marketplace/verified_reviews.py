from datetime import timedelta

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
    session_type = forms.CharField(max_length=120, label="Photography service")
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
        )
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


@login_required
@require_http_methods(["GET", "POST"])
def request_booking(request, slug):
    website = published_website(slug)
    photographer = website.photographer_profile
    if not customer_allowed(request.user, photographer):
        return HttpResponseForbidden("A verified customer account is required.")
    form = BookingRequestForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Never attach an account to a CRM record merely by matching email.
            client = Client.objects.filter(photographer=photographer, user=request.user).order_by("pk").first()
            if client is None:
                client = Client.objects.create(photographer=photographer, user=request.user,
                    first_name=request.user.first_name or "Client", last_name=request.user.last_name, email=request.user.email)
            session = ClientSession.objects.create(photographer=photographer, client=client,
                session_type=form.cleaned_data["session_type"], starts_at=form.cleaned_data["starts_at"],
                status=ClientSession.Status.TENTATIVE, event_kind=ClientSession.EventKind.BOOKING)
            PlatformBooking.objects.create(session=session, customer=request.user, photographer=photographer)
        return render(request, "marketplace/verified_booking_form.html", {"heading": "Booking request sent", "success": True, "slug": slug})
    return render(request, "marketplace/verified_booking_form.html", {"heading": "Request a photography booking", "form": form, "slug": slug})


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
