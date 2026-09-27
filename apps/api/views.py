from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.accounts.models import AdministrativeRegion, Country
from apps.core.views import public_page, add

add("api_coming_soon", "API", "Resources", description="A public placeholder for future LumisPixel API availability without publishing unsupported API references.", status="Coming Soon")
add("developer_center", "Developer Center", "Resources", description="A future home for integration guides, API updates, and developer resources as LumisPixel expands.", status="Coming Soon")


@require_GET
@cache_page(60 * 60)
def administrative_regions(request):
    country_value = request.GET.get("country", "").strip()
    if not country_value:
        return JsonResponse({"error": "A country id or ISO-2 code is required."}, status=400)

    country_filters = {"pk": country_value} if country_value.isdigit() else {"iso2__iexact": country_value}
    country = Country.objects.filter(is_active=True, **country_filters).first()
    if country is None:
        return JsonResponse({"error": "Country not found."}, status=404)

    regions = AdministrativeRegion.objects.filter(country=country, is_active=True).values("id", "name", "code", "region_type")
    return JsonResponse({"country": {"id": country.pk, "name": country.name, "iso2": country.iso2}, "regions": list(regions)})
