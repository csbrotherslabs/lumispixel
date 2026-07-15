from django.http import HttpResponse
from django.shortcuts import render


def index(request):
    return render(request, "index.html")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def custom_404(request, exception):
    return render(request, "404.html", status=404)


def custom_500(request):
    return render(request, "500.html", status=500)
