"""Central definitions for contract-template authoring starters.

Starter values are copied into a workspace-owned ``ContractTemplate`` by the
authoring UI. They are never persisted as a relationship to that template.
"""
from dataclasses import asdict, dataclass

from apps.clients.models import ContractTemplate


@dataclass(frozen=True)
class ContractStarter:
    key: str
    label: str
    name: str
    category: str
    title: str
    content: str = ""


# TODO: Add attorney-reviewed contract content to each ``content`` value before
# presenting these starters as complete agreements. Until then, the entries
# intentionally provide authoring metadata only; no production legal terms are
# fabricated here.
CONTRACT_STARTERS = (
    ContractStarter(
        "wedding", "Wedding Photography Agreement", "Wedding Photography Agreement",
        ContractTemplate.Category.WEDDING, "Wedding Photography Agreement",
    ),
    ContractStarter(
        "portrait", "Portrait Photography Agreement", "Portrait Photography Agreement",
        ContractTemplate.Category.PORTRAIT, "Portrait Photography Agreement",
    ),
    ContractStarter(
        "event", "Event Photography Agreement", "Event Photography Agreement",
        ContractTemplate.Category.EVENT, "Event Photography Agreement",
    ),
    ContractStarter(
        "commercial", "Commercial Photography Agreement", "Commercial Photography Agreement",
        ContractTemplate.Category.COMMERCIAL, "Commercial Photography Agreement",
    ),
    ContractStarter(
        "real-estate", "Real Estate Photography Agreement", "Real Estate Photography Agreement",
        ContractTemplate.Category.GENERAL, "Real Estate Photography Agreement",
    ),
    ContractStarter(
        "mini-session", "Mini Session Agreement", "Mini Session Agreement",
        ContractTemplate.Category.PORTRAIT, "Mini Session Agreement",
    ),
    ContractStarter(
        "second-shooter", "Second Shooter / Associate Photographer Agreement",
        "Second Shooter / Associate Photographer Agreement", ContractTemplate.Category.WEDDING,
        "Second Shooter / Associate Photographer Agreement",
    ),
)

CONTRACT_STARTER_CHOICES = (("", "Blank Template"),) + tuple(
    (starter.key, starter.label) for starter in CONTRACT_STARTERS
)


def serialized_contract_starters():
    """Return JSON-safe starter data keyed for the authoring UI."""
    return {starter.key: asdict(starter) for starter in CONTRACT_STARTERS}
