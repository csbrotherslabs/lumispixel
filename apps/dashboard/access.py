"""Role presets and studio-safe authorization helpers for the Business Hub.

UI visibility is deliberately not part of this module: callers must authorize a
request and scope every queryset on the server.
"""
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet

from apps.dashboard.models import StudioMembership


ROLE_PERMISSIONS = {
    StudioMembership.Role.OWNER: frozenset({
        "business_data", "clients", "galleries", "bookings", "schedule", "team",
        "financials", "growth", "analytics", "settings", "billing", "ai",
        "manage_members", "assign_owner", "ownership_transfer",
    }),
    StudioMembership.Role.MANAGER: frozenset({
        "clients", "galleries", "bookings", "schedule", "team", "analytics", "ai",
        "manage_members", "assignments",
    }),
    StudioMembership.Role.PHOTOGRAPHER: frozenset({
        "clients", "galleries", "bookings", "schedule", "ai", "delivery",
        "personal_performance",
    }),
}

ROLE_SUMMARIES = {
    StudioMembership.Role.OWNER: "Full Business Hub access, including Team, Financials, Growth, Analytics, Settings, Billing, and all business data.",
    StudioMembership.Role.MANAGER: "Operational access to permitted Clients, Galleries, Bookings, Schedule, Team assignments, operational analytics, and AI tools. No Billing, subscription management, ownership transfer, or unrestricted company settings.",
    StudioMembership.Role.PHOTOGRAPHER: "Access only to assigned bookings, assigned clients, assigned galleries, personal schedule, AI culling and editing, allowed delivery actions, and personal performance.",
}


@dataclass(frozen=True)
class StudioAccess:
    studio: object
    role: str
    membership: StudioMembership | None = None

    def allows(self, permission):
        return permission in ROLE_PERMISSIONS[self.role]


def access_for(user, *, studio=None, require=None):
    """Resolve active access without accepting a studio identifier from a client."""
    if not user.is_authenticated or not getattr(user, "can_login", False):
        raise PermissionDenied
    owned = getattr(user, "photographer_profile", None)
    if owned is not None and (studio is None or studio.pk == owned.pk):
        access = StudioAccess(owned, StudioMembership.Role.OWNER)
    else:
        memberships = StudioMembership.objects.select_related("studio").filter(
            user=user, status=StudioMembership.Status.ACTIVE
        )
        if studio is not None:
            memberships = memberships.filter(studio=studio)
        membership = memberships.first()
        if membership is None:
            raise PermissionDenied
        access = StudioAccess(membership.studio, membership.role, membership)
    if require and not access.allows(require):
        raise PermissionDenied
    return access


def scope_assigned(queryset: QuerySet, access: StudioAccess):
    """Studio-scope records and restrict photographers to explicit assignments."""
    queryset = queryset.filter(photographer=access.studio)
    if access.role == StudioMembership.Role.PHOTOGRAPHER:
        if access.membership is None:
            raise PermissionDenied
        queryset = queryset.filter(assigned_members=access.membership)
    return queryset.distinct()


def validate_assignment(membership, record):
    if membership.studio_id != record.photographer_id:
        raise ValidationError("The member and assigned record must belong to the same studio.")

