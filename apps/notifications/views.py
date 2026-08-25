from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Notification


def _inbox_url(request):
    query = request.POST.get("return_query", "").strip()
    return f"{reverse('notifications:index')}?{query}" if query else reverse("notifications:index")


@login_required
@require_GET
def index(request):
    status = request.GET.get("status", "all")
    category = request.GET.get("category", "all")
    if status not in {"all", "unread", "read"}:
        raise Http404
    categories = {value for value, _ in Notification.Category.choices}
    if category != "all" and category not in categories:
        raise Http404

    notifications = Notification.objects.filter(recipient=request.user)
    if status == "unread":
        notifications = notifications.filter(is_read=False)
    elif status == "read":
        notifications = notifications.filter(is_read=True)
    if category != "all":
        notifications = notifications.filter(category=category)

    counts = Notification.objects.filter(recipient=request.user).aggregate(
        total=Count("pk"),
        unread=Count("pk", filter=Q(is_read=False)),
    )
    context = {
        "page_obj": Paginator(notifications, 20).get_page(request.GET.get("page")),
        "status": status,
        "category": category,
        "categories": Notification.Category.choices,
        "total_count": counts["total"],
        "unread_count": counts["unread"],
        "read_count": counts["total"] - counts["unread"],
        "return_query": request.GET.urlencode(),
    }
    return render(request, "notifications/index.html", context)


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_unread() if request.POST.get("state") == "unread" else notification.mark_read()
    return redirect(_inbox_url(request))


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return redirect(_inbox_url(request))


@login_required
@require_POST
def dismiss(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    return redirect(_inbox_url(request))
