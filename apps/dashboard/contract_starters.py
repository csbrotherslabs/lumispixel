"""Central definitions for contract-template authoring starters.

Starter values are copied into a workspace-owned ``ContractTemplate`` by the
authoring UI. They are never persisted as a relationship to that template.
"""
from dataclasses import asdict, dataclass, replace

from apps.clients.models import ContractTemplate


@dataclass(frozen=True)
class ContractStarter:
    key: str
    label: str
    name: str
    category: str
    title: str
    content: str = ""


# Editable authoring outlines, not attorney-approved agreements.
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

CONTRACT_STARTERS += tuple(
    ContractStarter(key, name, name, ContractTemplate.Category.GENERAL, name)
    for key, name in (("fashion", "Fashion Photography Agreement"), ("product", "Product Photography Agreement"), ("general", "General Photography Agreement"))
)
# Concise, editable agreement language. Commercial terms are agreed separately.
SCOPES = {
    "wedding": "The Photographer will cover the ceremony, reception and other events included in the agreed package. The Client will provide a timeline and priority shot list. Coverage is subject to venue restrictions, guest cooperation and available time; no particular moment or image is guaranteed.",
    "portrait": "The Photographer will photograph the agreed participants during the scheduled portrait session and deliver selected, edited images under the agreed package. The Client will coordinate attendance, clothing and any requested poses. Additional retouching or participants require mutual agreement.",
    "event": "The Photographer will document the agreed event, including scheduled activities and requested group photographs where practicable. The Client will provide the event schedule, access credentials and a designated contact. Coverage outside the agreed hours requires mutual approval.",
    "commercial": "The Photographer will produce images according to the approved creative brief, shot list and technical specifications. The Client will coordinate approvals and supply agreed production resources. Additional revisions, production expenses or changes to the brief require written approval.",
    "real-estate": "The Photographer will capture the agreed property areas and deliver edited listing images. The Client will arrange lawful access, prepare the property and disclose access or safety restrictions. Floor plans, aerial imagery and virtual staging are included only if separately agreed.",
    "mini-session": "The Photographer will provide the agreed short session and selected edited images. The Client will arrive ready at the scheduled time. Late arrival may reduce available coverage; extensions, additional images and rescheduling are subject to availability and mutual agreement.",
    "fashion": "The Photographer will create images in accordance with the approved creative direction, looks and shot list. The Client will coordinate agreed models, wardrobe, styling and production resources. Changes to the creative brief, additional looks or retouching require written approval.",
    "product": "The Photographer will photograph the agreed products using approved styling, backgrounds and image specifications. The Client will supply accurate product details and suitable samples. Both parties will agree on shipping, return arrangements and additional styling or retouching before work begins.",
    "general": "The Photographer will provide photography coverage at the agreed date, time and location, select suitable images and apply standard professional editing. Coverage duration, image quantities and any additional products or retouching will follow the agreed package or written booking confirmation.",
}

LICENSES = {
    "commercial": "The Photographer retains copyright unless a written assignment states otherwise. The Client receives only the commercial usage rights agreed in writing, including permitted media, territory and duration. Additional usage requires written permission.",
    "fashion": "The Photographer retains copyright unless assigned in writing. Campaign, editorial and advertising use is limited to the agreed license and applicable model releases. Expanded usage requires written approval.",
    "product": "The Photographer retains copyright unless assigned in writing. The Client may use delivered images for the product marketing channels and duration agreed in writing. Third-party licensing and additional uses require permission.",
    "real-estate": "The Photographer retains copyright unless assigned in writing. The Client may use delivered images to market the agreed property during the listing period. Transfer to another agent, unrelated advertising or resale requires written permission.",
    "event": "The Photographer retains copyright unless assigned in writing. The Client may use delivered images for the event-related purposes agreed in writing. Advertising, resale and third-party licensing require separate permission.",
}

PERSONAL_LICENSE = (
    "The Photographer retains copyright unless assigned in writing. The Client may use delivered images for personal sharing and printing. Commercial use, resale and third-party licensing require written permission."
)

SECOND_SHOOTER = (
    "Parties: {{ workspace.name }} (Hiring Studio) and {{ client.full_name }} (Associate Photographer)\n"
    "Assignment: {{ booking.service }}\nDate: {{ booking.date }} at {{ booking.start_time }}\nLocation: {{ booking.location }}\n\n"
    "1. Scope and deliverables\nThe Associate will provide photography coverage as directed by the Hiring Studio, follow the agreed schedule and deliver all required image files in the agreed format. The Associate will not independently promise services to the Studio's clients.\n\n"
    "2. Compensation and expenses\nCompensation, payment timing and reimbursable expenses must be agreed in writing before work begins. Additional hours or expenses require approval.\n\n"
    "3. Cancellation and substitution\nEither party will promptly notify the other of any inability to perform. Cancellation charges, replacement arrangements and any compensation for completed work will follow the written assignment terms and applicable law.\n\n"
    "4. File delivery and confidentiality\nThe Associate will deliver files securely by the agreed deadline, protect client information and retain or delete copies as agreed. Client images and information may not be shared without authorization.\n\n"
    "5. Copyright and portfolio use\nOwnership and usage rights in assignment images will be established by a written license or assignment before work begins. The Associate may not publish, sell or use assignment images in a portfolio without the Studio's written permission and any necessary releases.\n\n"
    "6. Professional responsibilities\nBoth parties will cooperate, observe venue rules and take reasonable safety precautions. The Associate will promptly report equipment failure or other issues. Each party remains responsible for its own conduct, subject to applicable law.\n\n"
    "7. Acceptance and signatures\nBy signing, both parties accept this Agreement and the written assignment terms. Changes require mutual written agreement. Electronic signatures may be used where permitted by law."
)


def agreement_content(key):
    if key == "second-shooter":
        return SECOND_SHOOTER
    return (
        "Parties: {{ workspace.name }} (Photographer) and {{ client.full_name }} (Client)\n"
        "Client email: {{ client.email }}\n"
        "Service: {{ booking.service }}\nDate: {{ booking.date }} at {{ booking.start_time }}\nLocation: {{ booking.location }}\n\n"
        "1. Scope and deliverables\n" + SCOPES[key] + "\n\n"
        "2. Agreed fee and payment\n{{ booking.payment_terms }} Additional services or expenses require mutual approval.\n\n"
        "3. Cancellation and rescheduling\nEither party will promptly notify the other of a requested cancellation or date change. Rescheduling is subject to availability. Refunds, deposits and cancellation charges will follow the separately agreed written terms and applicable law.\n\n"
        "4. Image delivery\nThe Photographer will deliver selected, professionally edited images in the agreed format and timeframe through a secure gallery or other agreed method. RAW files are excluded unless agreed in writing. The Client will download and back up delivered files within the agreed retention period.\n\n"
        "5. Copyright, usage and releases\n" + LICENSES.get(key, PERSONAL_LICENSE) + " Each party will obtain permissions within its responsibility. Portfolio or promotional publication requires any necessary consent and releases.\n\n"
        "6. Responsibilities and other terms\nBoth parties will cooperate and observe safety and venue requirements. The Photographer will exercise reasonable professional care and artistic judgment. If circumstances beyond either party's reasonable control prevent performance, the parties will seek a reasonable alternative or resolution consistent with applicable law. Disputes should first be addressed in good faith.\n\n"
        "7. Acceptance and signatures\nBy signing, both parties accept this Agreement and the mutually agreed written booking terms. Changes require mutual written agreement. Electronic signatures may be used where permitted by law."
    )


CONTRACT_STARTERS = tuple(
    replace(starter, content=agreement_content(starter.key)) for starter in CONTRACT_STARTERS
)

CONTRACT_STARTER_CHOICES = (("", "Blank Template"),) + tuple(
    (starter.key, starter.label) for starter in CONTRACT_STARTERS
)


def serialized_contract_starters():
    """Return JSON-safe starter data keyed for the authoring UI."""
    return {starter.key: asdict(starter) for starter in CONTRACT_STARTERS}
