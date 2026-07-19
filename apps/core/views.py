from django.shortcuts import render

PAGE_DEFAULTS = {
    "purpose": "Give photographers and clients a clear public overview of how this LumisPixel area will support modern photo discovery, delivery, and business workflows.",
    "benefits": "Centralized galleries, polished client experiences, AI-assisted workflows, and conversion-focused calls to action help teams launch faster without adding backend complexity here.",
    "future": "This landing page prepares the information architecture for deeper product workflows, integrations, and authenticated modules as they are released.",
}

PUBLIC_PAGES = {}


def add(key, title, category, heading=None, description=None, status=""):
    PUBLIC_PAGES[key] = {
        **PAGE_DEFAULTS,
        "title": title,
        "category": category,
        "heading": heading or title,
        "description": description
        or f"Learn how LumisPixel supports {title.lower()} with an AI-ready photography platform.",
        "status": status,
    }


for key, title in [
    ("products", "Products"),
    ("solutions", "Solutions"),
]:
    add(key, title, "Platform")

BUSINESS_HUB_PAGES = [
    (
        "business_hub",
        "Business Hub",
        "Bring the operational side of your photography business into one connected hub. Full page coming soon.",
    ),
    (
        "business_hub_dashboard",
        "Business Dashboard",
        "Run your entire photography business from one intelligent dashboard. Full page coming soon.",
    ),
    (
        "business_hub_client_crm",
        "Client CRM",
        "Manage leads, clients, relationships, and follow-ups in one organized workspace. Full page coming soon.",
    ),
    (
        "business_hub_booking_calendar",
        "Booking & Calendar",
        "Coordinate bookings, sessions, availability, and calendar workflows with less admin. Full page coming soon.",
    ),
    (
        "business_hub_contracts",
        "Contracts",
        "Prepare, send, and manage photography contracts from a future streamlined workflow. Full page coming soon.",
    ),
    (
        "business_hub_invoices_payments",
        "Invoices & Payments",
        "Simplify invoices, payments, and client billing from one business workspace. Full page coming soon.",
    ),
    (
        "business_hub_workflow_automation",
        "Workflow Automation",
        "Automate repetitive studio tasks so every job moves forward with less manual work. Full page coming soon.",
    ),
    (
        "business_hub_ai_business_assistant",
        "AI Business Assistant",
        "Use AI-assisted business support to plan, respond, and operate more efficiently. Full page coming soon.",
    ),
    (
        "business_hub_analytics_reports",
        "Analytics & Reports",
        "Track performance, revenue, clients, and growth signals with clearer reports. Full page coming soon.",
    ),
    (
        "business_hub_marketing_growth",
        "Marketing & Growth",
        "Plan campaigns, improve visibility, and grow bookings with future marketing tools. Full page coming soon.",
    ),
    (
        "business_hub_team_operations",
        "Team & Operations",
        "Coordinate team tasks, roles, and day-to-day operations for growing photography businesses. Full page coming soon.",
    ),
]

for key, title, description in BUSINESS_HUB_PAGES:
    add(key, title, "Business Hub", description=description, status="Coming Soon")
for key, title in [
    ("wedding_photography", "Wedding Photography"),
    ("portrait_photography", "Portrait Photography"),
    ("sports_photography", "Sports Photography"),
    ("school_photography", "School Photography"),
    ("corporate_photography", "Corporate Photography"),
    ("event_photography", "Event Photography"),
    ("real_estate_photography", "Real Estate Photography"),
    ("commercial_photography", "Commercial Photography"),
    ("studio_photography", "Studio Photography"),
    ("destination_photography", "Destination Photography"),
]:
    add(
        key,
        title,
        "Solutions",
        description=f"A polished landing page for {title.lower()} teams using LumisPixel to organize client delivery, discovery, and growth.",
    )
for key, title, status in [
    ("resources", "Resources", ""),
    ("how_it_works", "How It Works", ""),
    ("documentation", "Documentation", "Preview"),
    ("help_center", "Help Center", ""),
    ("faq", "FAQ", ""),
    ("blog", "Blog", ""),
    ("release_notes", "Release Notes", ""),
    ("system_status", "System Status", ""),
    ("tutorials", "Tutorials", ""),
    ("community", "Community", ""),
]:
    add(key, title, "Resources", status=status)
for key, title in [
    ("company", "Company"),
    ("about", "About"),
    ("our_story", "Our Story"),
    ("careers", "Careers"),
    ("partners", "Partners"),
    ("contact", "Contact"),
    ("privacy_policy", "Privacy Policy"),
    ("terms_of_service", "Terms of Service"),
    ("cookie_policy", "Cookie Policy"),
    ("accessibility", "Accessibility"),
]:
    add(key, title, "Company")


def index(request):
    return render(request, "index.html")


def public_page(request, page_key):
    if page_key == "wedding_photography":
        return wedding_photography(request)
    if page_key == "portrait_photography":
        return portrait_photography(request)
    if page_key == "sports_photography":
        return sports_photography(request)
    if page_key == "school_photography":
        return school_photography(request)
    if page_key == "corporate_photography":
        return corporate_photography(request)
    if page_key == "event_photography":
        return event_photography(request)
    if page_key == "destination_photography":
        return destination_photography(request)
    if page_key == "real_estate_photography":
        return real_estate_photography(request)
    if page_key == "commercial_photography":
        return commercial_photography(request)
    if page_key == "studio_photography":
        return studio_photography(request)
    if page_key == "business_hub_dashboard":
        return business_hub_dashboard(request)
    if page_key == "business_hub_client_crm":
        return business_hub_client_crm(request)
    if page_key == "business_hub_booking_calendar":
        return business_hub_booking_calendar(request)
    if page_key == "business_hub_contracts":
        return business_hub_contracts(request)
    if page_key == "business_hub_invoices_payments":
        return business_hub_invoices_payments(request)
    if page_key == "business_hub_workflow_automation":
        return business_hub_workflow_automation(request)
    if page_key == "business_hub_ai_business_assistant":
        return business_hub_ai_business_assistant(request)
    if page_key == "business_hub_analytics_reports":
        return business_hub_analytics_reports(request)
    if page_key == "business_hub_marketing_growth":
        return business_hub_marketing_growth(request)
    return render(request, "public_landing.html", {"page": PUBLIC_PAGES[page_key]})


def business_hub_dashboard(request):
    context = {
        "problem_cards": [
            ("bi-person-lines-fill", "Scattered Clients", "Client notes, files, and activity are split across too many places."),
            ("bi-inbox", "Missed Leads", "New inquiries can get buried before they become bookings."),
            ("bi-receipt", "Manual Billing", "Deposits, balances, and reminders take extra time to manage."),
            ("bi-calendar2-x", "Separate Calendars", "Shoots, consults, deadlines, and availability are hard to keep aligned."),
            ("bi-bell-slash", "Lost Follow-Ups", "Review requests, rebooking prompts, and next steps are easy to miss."),
            ("bi-graph-down", "Limited Visibility", "Revenue, workload, and priorities are difficult to see at a glance."),
        ],
        "workflow": [
            ("Inquiry", "Capture new leads and see what needs a response."),
            ("Booking", "Turn interested clients into confirmed sessions."),
            ("Contract", "Keep agreements connected to each client and job."),
            ("Invoice", "Track deposits, balances, and payment status."),
            ("Session", "Prepare shoot details, timelines, and locations."),
            ("Editing", "Monitor progress and delivery deadlines."),
            ("Gallery", "Follow proofing, delivery, and client activity."),
            ("Follow-Up", "Stay ready for reviews, reorders, and rebooking."),
        ],
        "features": [
            ("bi-speedometer2", "Business Overview", "See priorities, income, jobs, and client activity in one place."),
            ("bi-currency-dollar", "Revenue", "Track booked revenue, collected payments, balances, and trends."),
            ("bi-camera", "Sessions", "View upcoming shoots with key details, timelines, and prep tasks."),
            ("bi-people", "Clients", "Keep inquiries, messages, notes, and activity easy to find."),
            ("bi-images", "Galleries", "Monitor proofing, delivery, sales, and archive status."),
            ("bi-sliders", "Editing Queue", "See workloads, due dates, and jobs that need attention."),
            ("bi-file-earmark-text", "Invoices", "Manage deposits, payment links, balances, and reminders."),
            ("bi-pen", "Contracts", "Connect signed agreements to clients, sessions, and milestones."),
            ("bi-calendar-week", "Calendar", "Unify consults, shoots, deadlines, reminders, and availability."),
            ("bi-list-check", "Workflows", "Move every client through a clear, repeatable process."),
            ("bi-stars", "AI Insights", "Surface trends, risks, and tasks worth reviewing."),
            ("bi-bell", "Notifications", "See recent changes across clients, galleries, and payments."),
        ],
        "kpis": [
            "Monthly Revenue",
            "New Bookings",
            "Active Clients",
            "Galleries Due",
            "Unpaid Invoices",
            "Delivery Time",
            "Repeat Clients",
            "Upcoming Sessions",
        ],
        "ai_insights": [
            ("Find Follow-Ups", "Identify clients who may need a reply, review request, or rebooking note."),
            ("Spot Slow Seasons", "Review booking patterns before quieter months arrive."),
            ("Flag Overdue Invoices", "Bring unpaid balances and reminders to your attention."),
            ("Summarize Performance", "See a plain-language snapshot of recent business activity."),
            ("Detect Bottlenecks", "Notice editing delays or workflow steps that are falling behind."),
            ("Suggest Opportunities", "Find practical ways to improve service, sales, and retention."),
        ],
        "benefits": [
            ("Save Time", "Spend fewer hours chasing details across tools."),
            ("Stay Organized", "Keep jobs, notes, files, and next steps together."),
            ("Respond Faster", "See new inquiries and open tasks sooner."),
            ("Get Paid Sooner", "Keep balances and reminders close to each job."),
            ("Deliver On Time", "Track editing progress and upcoming deadlines."),
            ("Grow Revenue", "Spot rebooking, reorder, and follow-up opportunities."),
            ("Reduce Admin", "Simplify the repetitive work behind each session."),
            ("Make Better Decisions", "Use clear signals instead of guesswork."),
        ],
        "ecosystem": [
            "Business Dashboard",
            "Client CRM",
            "Booking Calendar",
            "Contracts",
            "Invoices",
            "Automation",
            "AI Editing",
            "Galleries",
            "Analytics",
            "Marketing",
            "Marketplace",
        ],
        "testimonial_placeholders": [
            ("Client clarity", "Placeholder area for a future photographer story."),
            ("Studio workflow", "Placeholder area for a verified customer quote."),
            ("Business insight", "Placeholder area for a real testimonial once available."),
        ],
    }
    return render(request, "business_hub_dashboard.html", context)


def business_hub_client_crm(request):
    context = {
        "problem_cards": [
            ("bi-inbox", "Lost Inquiries", "New leads disappear in crowded inboxes before you can reply."),
            ("bi-bell-slash", "Missed Follow-Ups", "Clients wait too long when next steps are not visible."),
            ("bi-journal-text", "Scattered Notes", "Preferences, names, and shoot details live in different places."),
            ("bi-clipboard2", "Manual Tracking", "Spreadsheets make every session harder to manage."),
            ("bi-credit-card", "Forgotten Payments", "Deposits and balances slip through without clear status."),
            ("bi-diagram-3", "Disconnected Tools", "Bookings, contracts, invoices, and galleries feel separate."),
        ],
        "timeline": ["Inquiry", "Consultation", "Booking", "Contract", "Invoice", "Session", "Editing", "Gallery Delivery", "Review", "Referral", "Repeat Client"],
        "profile_features": [
            ("bi-person-vcard", "Contact Info", "Names, emails, phone numbers, and preferences."),
            ("bi-camera", "Session History", "Every past and upcoming shoot in one view."),
            ("bi-file-earmark-text", "Contracts", "Signed agreements connected to each client."),
            ("bi-receipt", "Invoices", "Deposits, balances, and payment links."),
            ("bi-credit-card-2-front", "Payments", "Paid, due, and overdue status at a glance."),
            ("bi-images", "Galleries", "Proofing, favorites, delivery, and archive status."),
            ("bi-pencil-square", "Notes", "Personal details that help every client feel known."),
            ("bi-ui-checks", "Questionnaires", "Planning answers stored beside the job."),
            ("bi-heart", "Favorites", "Client selections and buying intent."),
            ("bi-chat-dots", "Communication", "Recent messages and important activity."),
            ("bi-list-check", "Tasks", "Follow-ups and reminders before they are missed."),
            ("bi-stars", "AI Summary", "A fast snapshot of the full relationship."),
        ],
        "kpis": ["Upcoming Sessions", "Contracts Awaiting Signature", "Outstanding Payments", "Pending Galleries", "Clients Awaiting Follow-Up", "New Inquiries", "Recent Reviews", "Repeat Clients"],
        "ai_cards": [
            ("Summarize History", "Review the full client relationship in seconds."),
            ("Suggest Follow-Ups", "Know who needs a reply, reminder, or thank-you."),
            ("Find Repeat Work", "Spot past clients ready for another session."),
            ("Flag Unpaid Invoices", "Bring balances back into focus."),
            ("Generate Notes", "Turn details into organized client notes."),
            ("Draft Emails", "Start personalized messages faster."),
            ("Surface Tasks", "See what matters before the day gets busy."),
            ("Recommend Actions", "Move each relationship forward with confidence."),
        ],
        "benefits": [
            ("Know Every Client", "Walk into each session with the right context."),
            ("Respond Faster", "Turn inquiries into bookings with less delay."),
            ("Stay Organized", "Keep the relationship, job, and files together."),
            ("Better Service", "Deliver a polished experience clients remember."),
            ("Save Time", "Spend fewer hours searching for details."),
            ("Build Loyalty", "Make every client feel remembered."),
            ("Reduce Admin", "Let the CRM carry the operational details."),
            ("Increase Repeat Work", "Follow up at the right moment."),
        ],
        "ecosystem": ["Business Dashboard", "Booking & Calendar", "Contracts", "Invoices & Payments", "Workflow Automation", "AI Editing", "Client Galleries", "Marketing", "Analytics", "Marketplace"],
    }
    return render(request, "business_hub_client_crm.html", context)


def business_hub_booking_calendar(request):
    context = {
        "problem_cards": [
            ("bi-calendar2-x", "Scheduling Conflicts", "Shoots, consults, and deadlines compete for the same time."),
            ("bi-envelope-exclamation", "Manual Confirmations", "Every booking needs another email, text, or reminder."),
            ("bi-bell-slash", "Missed Appointments", "Clients forget details when reminders are not automatic."),
            ("bi-chat-left-dots", "Back-and-Forth Emails", "Finding the right time takes too many messages."),
            ("bi-credit-card", "Forgotten Deposits", "Sessions stay unconfirmed when payment is disconnected."),
            ("bi-intersect", "Double Bookings", "Separate calendars make availability harder to trust."),
        ],
        "journey": ["Inquiry", "Choose Package", "Select Date", "Sign Contract", "Pay Deposit", "Confirmation", "Automatic Reminders", "Photo Session", "Gallery Delivery"],
        "features": [
            ("bi-window", "Online Booking", "Let clients choose a session without waiting on replies."),
            ("bi-calendar-week", "Availability Calendar", "Show open dates while protecting personal time."),
            ("bi-box-seam", "Session Packages", "Guide clients to the right offer faster."),
            ("bi-grid-3x3-gap", "Mini Sessions", "Launch limited spots with clean booking windows."),
            ("bi-credit-card-2-front", "Deposits", "Collect commitment before a date is confirmed."),
            ("bi-file-earmark-text", "Contracts", "Connect agreements to each booking automatically."),
            ("bi-arrow-repeat", "Calendar Sync", "Keep sessions aligned across your workday."),
            ("bi-bell", "Reminders", "Send timely prep, payment, and arrival notes."),
            ("bi-ui-checks", "Questionnaires", "Collect planning details before the shoot."),
            ("bi-arrow-left-right", "Rescheduling", "Move sessions without losing the details."),
            ("bi-check2-circle", "Booking Approvals", "Review requests before they become confirmed."),
            ("bi-clock-history", "Booking History", "See every past request, change, and payment."),
        ],
        "kpis": ["Upcoming Sessions", "Available Time Slots", "Pending Booking Requests", "Confirmed Sessions", "Rescheduled Sessions", "Deposits Collected", "Upcoming Mini Sessions", "Today's Schedule"],
        "ai_cards": [
            ("Better Time Slots", "Offer openings that fit your schedule and client needs."),
            ("Detect Conflicts", "Catch calendar issues before clients are affected."),
            ("Recommend Follow-Ups", "Know which inquiries need a nudge."),
            ("Identify Slow Weeks", "Spot gaps where a promotion could help."),
            ("Predict Busy Seasons", "Prepare packages and availability ahead of demand."),
            ("Mini Session Dates", "Find smart windows for limited session days."),
            ("Booking Gaps", "Protect travel, prep, and editing time."),
            ("Unconfirmed Sessions", "Highlight bookings still missing a step."),
        ],
        "benefits": [
            ("Book Faster", "Turn interest into a confirmed date sooner."),
            ("Reduce No-Shows", "Keep clients prepared with automatic reminders."),
            ("Stay Organized", "See every session, request, and deadline together."),
            ("Avoid Conflicts", "Protect your time with clearer availability."),
            ("Collect Earlier", "Secure deposits during the booking flow."),
            ("Save Admin Time", "Spend fewer hours coordinating schedules."),
            ("Better Experience", "Give clients a smooth path from inquiry to shoot."),
            ("Increase Bookings", "Make it easier for clients to say yes."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Contracts", "Invoices & Payments", "Workflow Automation", "Client Galleries", "AI Business Assistant", "Marketing", "Analytics"],
    }
    return render(request, "business_hub_booking_calendar.html", context)


def business_hub_contracts(request):
    context = {
        "problem_cards": [
            ("bi-pencil-square", "Unsigned Agreements", "Sessions stay uncertain when signatures are still missing."),
            ("bi-envelope-paper", "Manual Emails", "Every client follow-up becomes another message to send."),
            ("bi-folder-x", "Lost Documents", "Contracts disappear across inboxes, drives, and downloads."),
            ("bi-clock-history", "Missed Deadlines", "Important signing dates are easy to overlook."),
            ("bi-file-diff", "Version Confusion", "Old drafts make it harder to know what was approved."),
            ("bi-diagram-3", "Disconnected Workflows", "Bookings, deposits, clients, and galleries feel separate."),
        ],
        "workflow": ["Booking", "Generate Contract", "Send Automatically", "Client Reviews", "Digital Signature", "Deposit Payment", "Confirmation", "Session Ready"],
        "features": [
            ("bi-file-earmark-richtext", "Contract Templates", "Start with reusable contracts built for repeat sessions."),
            ("bi-pen", "Digital Signatures", "Let clients sign from any device in minutes."),
            ("bi-card-checklist", "Custom Clauses", "Adjust terms for weddings, portraits, events, and studios."),
            ("bi-link-45deg", "Session Linking", "Attach every agreement to the right client and shoot."),
            ("bi-send-check", "Automatic Delivery", "Send contracts when a booking reaches the right step."),
            ("bi-activity", "Status Tracking", "See sent, viewed, signed, and pending agreements."),
            ("bi-clock", "Version History", "Keep approved versions organized and easy to review."),
            ("bi-shield-lock", "Secure Storage", "Store completed agreements in one protected workspace."),
            ("bi-phone", "Client Access", "Give clients a simple place to review and sign."),
            ("bi-arrow-repeat", "Renewable Templates", "Reuse polished contracts without rebuilding each time."),
            ("bi-boxes", "Multi-Package Contracts", "Match agreements to packages, add-ons, and session types."),
            ("bi-bell", "Contract Reminders", "Nudge clients before unsigned agreements slow you down."),
        ],
        "kpis": ["Pending Signatures", "Completed Contracts", "Contracts Sent", "Expiring Agreements", "Unsigned Contracts", "Today's Activity", "Recent Signatures", "Upcoming Sessions"],
        "ai_cards": [
            ("Remind Clients", "Prompt unsigned clients before the session gets close."),
            ("Summarize Status", "See which agreements need attention now."),
            ("Suggest Details", "Spot missing client, session, or package information."),
            ("Detect Gaps", "Find incomplete agreements before they create delays."),
            ("Recommend Follow-Ups", "Know when a friendly nudge can move things forward."),
            ("Highlight Deadlines", "Surface signing dates tied to upcoming sessions."),
            ("Generate Summaries", "Review key agreement details in plain language."),
            ("Surface Priorities", "Focus on the contracts most likely to block a booking."),
        ],
        "benefits": [
            ("Stay Protected", "Start every session with clear expectations."),
            ("Save Time", "Spend fewer hours chasing paperwork."),
            ("Reduce Paperwork", "Replace scattered files with one clean workflow."),
            ("Look Professional", "Give clients a polished signing experience."),
            ("Sign Faster", "Make approval simple from desktop or mobile."),
            ("Stay Organized", "Keep every agreement beside its client and session."),
            ("Stay Connected", "Link contracts to bookings, invoices, and galleries."),
            ("Better Experience", "Help clients feel ready before session day."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Invoices & Payments", "Workflow Automation", "Client Galleries", "AI Business Assistant", "Analytics"],
    }
    return render(request, "business_hub_contracts.html", context)


def business_hub_invoices_payments(request):
    context = {
        "problem_cards": [
            ("bi-clock-history", "Late Payments", "Unpaid invoices slow down cash flow after the session is complete."),
            ("bi-file-earmark-spreadsheet", "Manual Invoices", "Rebuilding invoices by hand takes time away from clients and editing."),
            ("bi-credit-card", "Forgotten Deposits", "Bookings feel uncertain when deposits are not easy to track."),
            ("bi-wallet2", "Outstanding Balances", "Final balances get missed when payment status lives in different tools."),
            ("bi-question-circle", "Payment Confusion", "Clients need a clear way to know what is due and how to pay."),
            ("bi-diagram-3", "Multiple Tools", "Invoices, checkout links, notes, and reminders should not be scattered."),
        ],
        "workflow": ["Booking", "Contract Signed", "Invoice Sent", "Deposit Paid", "Session", "Final Invoice", "Payment Received", "Gallery Delivered"],
        "features": [
            ("bi-receipt", "Invoices", "Create polished invoices connected to each client and booking."),
            ("bi-credit-card-2-front", "Online Payments", "Let clients pay from a simple, secure online experience."),
            ("bi-piggy-bank", "Deposits", "Collect retainers and see deposit status before session day."),
            ("bi-calendar2-check", "Payment Plans", "Break larger packages into clear scheduled payments."),
            ("bi-envelope-check", "Automatic Receipts", "Send clean confirmations after every successful payment."),
            ("bi-bell", "Invoice Reminders", "Nudge clients before balances become overdue."),
            ("bi-arrow-repeat", "Recurring Payments", "Support ongoing retainers, studio plans, and repeat work."),
            ("bi-percent", "Tax Tracking", "Keep tax amounts visible without accounting complexity."),
            ("bi-clock", "Payment History", "Review every charge, deposit, refund, and receipt in one place."),
            ("bi-clipboard-data", "Balance Tracking", "Know what is paid, pending, overdue, or coming next."),
            ("bi-wallet", "Payment Methods", "Offer flexible ways to pay while keeping records together."),
            ("bi-shield-lock", "Secure Transactions", "Give clients a trusted checkout experience from any device."),
        ],
        "kpis": ["Revenue This Month", "Outstanding Invoices", "Deposits Collected", "Payments Received", "Pending Payments", "Average Payment Time", "Upcoming Revenue", "Recent Transactions"],
        "ai_cards": [
            ("Flag Overdue", "Spot invoices that need attention before cash flow slips."),
            ("Suggest Reminders", "Draft friendly follow-ups tied to each client and balance."),
            ("Predict Revenue", "See what is likely to arrive this month."),
            ("Find Balances", "Identify unpaid amounts across active bookings."),
            ("Summarize Activity", "Review payments, deposits, and trends in plain language."),
            ("Recommend Follow-Ups", "Know which clients to nudge and when."),
            ("Detect Deposits", "Surface bookings missing required retainers."),
            ("Highlight Trends", "Understand payment speed, seasonality, and revenue patterns."),
        ],
        "benefits": [
            ("Get Paid Faster", "Make every next payment easy for clients to complete."),
            ("Reduce Manual Work", "Spend less time creating invoices and chasing status."),
            ("Stay Organized", "Keep deposits, balances, and receipts connected to each job."),
            ("Improve Cash Flow", "See what has arrived and what is coming next."),
            ("Track Every Dollar", "Follow payment history from inquiry to delivery."),
            ("Chase Less", "Use reminders and clear status instead of awkward follow-ups."),
            ("Look Professional", "Give clients a polished billing experience."),
            ("Focus On Photos", "Let payment admin move quietly in the background."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Contracts", "Workflow Automation", "Client Galleries", "Analytics", "AI Business Assistant"],
    }
    return render(request, "business_hub_invoices_payments.html", context)


def business_hub_workflow_automation(request):
    context = {
        "problem_cards": [
            ("bi-envelope", "Manual Emails", "Every inquiry, reminder, and follow-up takes another message."),
            ("bi-bell-slash", "Forgotten Follow-Ups", "Great clients can slip away when the next step is not automatic."),
            ("bi-calendar2-x", "Missed Deadlines", "Contracts, payments, prep notes, and delivery dates need constant attention."),
            ("bi-arrow-repeat", "Repeated Admin", "The same tasks repeat for every wedding, portrait, event, or listing."),
            ("bi-list-check", "Scattered Checklists", "To-dos live across notes, inboxes, calendars, and memory."),
            ("bi-ui-checks", "Small Tasks", "Tiny operational details can steal hours from shooting and editing."),
        ],
        "journey": ["Inquiry", "Welcome Email", "Booking Confirmation", "Contract Sent", "Invoice Sent", "Reminder", "Photo Session", "Gallery Notification", "Review Request", "Referral Request"],
        "features": [
            ("bi-envelope-check", "Email Automation", "Send polished client messages at the right moment."),
            ("bi-file-earmark-text", "Contract Automation", "Move signed agreements forward without manual chasing."),
            ("bi-receipt", "Invoice Automation", "Send invoices, deposits, receipts, and payment nudges."),
            ("bi-lightning-charge", "Booking Triggers", "Start the next step when a client books or changes status."),
            ("bi-bell", "Reminder Scheduling", "Keep clients prepared before consults, sessions, and deadlines."),
            ("bi-card-checklist", "Questionnaires", "Collect planning details before you need them."),
            ("bi-check2-square", "Task Automation", "Create internal to-dos for prep, editing, delivery, and follow-up."),
            ("bi-images", "Gallery Notifications", "Tell clients when galleries, proofs, and downloads are ready."),
            ("bi-star", "Review Requests", "Ask happy clients for reviews while the experience is fresh."),
            ("bi-share", "Referral Requests", "Turn completed sessions into warm future bookings."),
            ("bi-diagram-3", "Custom Workflows", "Build repeatable paths for every photography service you offer."),
            ("bi-layers", "Workflow Templates", "Launch proven workflows without starting from a blank page."),
        ],
        "kpis": ["Active Workflows", "Tasks Completed", "Emails Sent", "Reminders Scheduled", "Clients Automated", "Pending Actions", "Time Saved", "Upcoming Automations"],
        "ai_cards": [
            ("Better Workflows", "Suggest simpler paths for each client journey."),
            ("Smart Follow-Ups", "Recommend the right message when a client goes quiet."),
            ("Missing Steps", "Catch skipped tasks before they affect the experience."),
            ("Find Delays", "Spot bookings that are moving slower than expected."),
            ("Busy Periods", "Predict weeks that may need extra preparation."),
            ("Templates", "Generate workflows for weddings, portraits, events, and studios."),
            ("Bottlenecks", "Highlight where work keeps getting stuck."),
            ("Improvements", "Recommend small changes that save more time."),
        ],
        "benefits": [
            ("Reduce Admin", "Let routine work happen in the background."),
            ("Never Forget", "Keep every next step visible and moving."),
            ("Respond Faster", "Give clients timely replies without living in your inbox."),
            ("Stay Organized", "Keep tasks, reminders, and client progress connected."),
            ("Consistent Service", "Deliver the same polished experience every time."),
            ("Better Experiences", "Make clients feel guided from inquiry to referral."),
            ("Grow Easier", "Handle more bookings without adding more busywork."),
            ("Focus On Photography", "Spend more time creating and less time managing."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Contracts", "Invoices & Payments", "Client Galleries", "AI Business Assistant", "Analytics", "Marketing"],
    }
    return render(request, "business_hub_workflow_automation.html", context)


def business_hub_analytics_reports(request):
    context = {
        "problem_cards": [
            ("bi-speedometer", "No Clear Metrics", "Important numbers are hard to find when they live in separate tools."),
            ("bi-file-earmark-bar-graph", "Scattered Reports", "Revenue, bookings, galleries, and payments rarely tell one story."),
            ("bi-graph-down", "Unknown Trends", "Busy seasons and slow periods can appear without warning."),
            ("bi-lightbulb", "Missed Opportunities", "Repeat clients, pricing signals, and growth moments are easy to overlook."),
            ("bi-hourglass-split", "Slow Decisions", "Planning takes longer when every answer requires manual digging."),
            ("bi-eye-slash", "Limited Visibility", "It is difficult to know what is working and what needs attention."),
        ],
        "flow": ["Bookings", "Revenue", "Clients", "Sessions", "Galleries", "Payments", "Reviews", "Business Growth"],
        "features": [
            ("bi-currency-dollar", "Revenue Reports", "Understand booked, collected, pending, and growing revenue."),
            ("bi-calendar2-week", "Booking Trends", "See which months, services, and offers drive demand."),
            ("bi-people", "Client Growth", "Track new clients, repeat clients, and relationship momentum."),
            ("bi-images", "Gallery Performance", "Measure delivery, activity, favorites, proofing, and sales signals."),
            ("bi-credit-card", "Payment Reports", "Keep deposits, balances, and overdue payments visible."),
            ("bi-speedometer2", "Business Dashboard", "Review your studio health from one polished dashboard."),
            ("bi-camera", "Session Reports", "Understand session volume, workload, timing, and outcomes."),
            ("bi-megaphone", "Marketing Performance", "See which campaigns and offers create real interest."),
            ("bi-list-check", "Workflow Reports", "Find bottlenecks before they slow delivery."),
            ("bi-sliders", "Custom Reports", "Build focused views for the questions you ask most."),
            ("bi-download", "Export Reports", "Share clean summaries for planning, bookkeeping, or review."),
            ("bi-activity", "Real-Time Metrics", "Stay current as bookings, payments, and galleries change."),
        ],
        "kpis": ["Monthly Revenue", "Bookings This Month", "New Clients", "Repeat Clients", "Average Booking Value", "Pending Payments", "Gallery Deliveries", "Business Growth"],
        "ai_cards": [
            ("Highlight Trends", "See revenue changes and booking shifts in plain language."),
            ("Predict Seasons", "Prepare for busy stretches before your calendar fills."),
            ("Find Slow Periods", "Spot quiet weeks where a promotion could help."),
            ("Recommend Pricing", "Notice packages that may be ready for a smarter price."),
            ("Spot Client Trends", "Understand which clients, services, and sessions repeat."),
            ("Measure Growth", "Compare progress over time without complex spreadsheets."),
            ("Repeat Opportunities", "Find past clients who may be ready to book again."),
            ("Next Steps", "Turn insights into clear actions for the week ahead."),
        ],
        "benefits": [
            ("Grow Revenue", "See the offers and seasons that create stronger income."),
            ("Understand Performance", "Know what is working across your business."),
            ("Track Progress", "Measure improvement month by month."),
            ("Improve Efficiency", "Find workflow delays before they become client issues."),
            ("Measure Growth", "Follow your business from bookings to delivery."),
            ("Stay Informed", "Keep key activity visible without digging."),
            ("Plan Ahead", "Use trends to prepare offers, dates, and capacity."),
            ("Decide Confidently", "Move forward with clear signals instead of guesses."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Contracts", "Invoices & Payments", "Workflow Automation", "AI Business Assistant", "Client Galleries", "Marketing", "Marketplace"],
    }
    return render(request, "business_hub_analytics_reports.html", context)


def business_hub_marketing_growth(request):
    context = {
        "problem_cards": [
            ("bi-share", "Few Referrals", "Happy clients are not always prompted to share your studio."),
            ("bi-inbox", "Inconsistent Leads", "New inquiries can rise and fall without a clear system."),
            ("bi-eye-slash", "Limited Visibility", "Your best work may not reach the right clients."),
            ("bi-megaphone", "Manual Marketing", "Campaigns take time when every step starts from scratch."),
            ("bi-lightbulb", "Missed Opportunities", "Reviews, rebookings, and follow-ups are easy to forget."),
            ("bi-graph-down", "Slow Growth", "Growth is harder when results are not connected."),
        ],
        "journey": ["Website Visit", "Inquiry", "Booking", "Session", "Gallery Delivery", "Review", "Referral", "Repeat Client", "Business Growth"],
        "features": [
            ("bi-person-plus", "Lead Tracking", "Capture inquiries and see which sources create interest."),
            ("bi-share", "Referrals", "Invite happy clients to recommend your studio."),
            ("bi-star", "Reviews", "Ask for testimonials while the experience is fresh."),
            ("bi-envelope-heart", "Email Campaigns", "Send polished updates, offers, and rebooking notes."),
            ("bi-speedometer2", "Marketing Dashboard", "See campaigns, leads, reviews, and growth in one place."),
            ("bi-window", "Website Performance", "Understand visits, inquiries, and page activity."),
            ("bi-search", "SEO Insights", "Improve visibility for the services clients search for."),
            ("bi-send", "Social Sharing", "Turn galleries and reviews into shareable moments."),
            ("bi-percent", "Discount Campaigns", "Promote mini sessions, seasonal offers, and add-ons."),
            ("bi-arrow-repeat", "Client Retention", "Bring past clients back at the right time."),
            ("bi-file-earmark-bar-graph", "Growth Reports", "Track progress across leads, bookings, and revenue."),
            ("bi-activity", "Campaign Analytics", "Measure what works without spreadsheets."),
        ],
        "kpis": ["New Leads", "Bookings", "Referral Rate", "Repeat Clients", "Review Requests", "Campaign Performance", "Website Visitors", "Revenue Growth"],
        "ai_cards": [
            ("Referral Chances", "Find clients likely to share your work."),
            ("Campaign Ideas", "Suggest timely offers for each season."),
            ("Follow-Ups", "Recommend messages for quiet leads."),
            ("Repeat Clients", "Highlight clients ready to book again."),
            ("Busy Seasons", "Prepare marketing before demand peaks."),
            ("Pricing Signals", "Spot packages that may need adjustment."),
            ("Growth Trends", "Explain lead and booking patterns clearly."),
            ("Marketing Ideas", "Generate simple prompts for posts and emails."),
        ],
        "benefits": [
            ("Book More", "Turn more attention into confirmed sessions."),
            ("More Referrals", "Make sharing easy for happy clients."),
            ("Build Brand", "Keep your studio visible and memorable."),
            ("Improve Visibility", "Help the right clients discover your work."),
            ("Grow Revenue", "Connect campaigns to bookings and sales."),
            ("Stronger Relationships", "Stay present after gallery delivery."),
            ("Retain Clients", "Bring families, couples, and teams back."),
            ("Market Efficiently", "Spend less time guessing what to send."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Contracts", "Invoices & Payments", "Workflow Automation", "AI Business Assistant", "Analytics", "Client Galleries", "Marketplace"],
    }
    return render(request, "business_hub_marketing_growth.html", context)


def business_hub_ai_business_assistant(request):
    context = {
        "problem_cards": [
            ("bi-bell-slash", "Forgotten Follow-Ups", "Warm leads and past clients can go quiet without a clear next step."),
            ("bi-search", "Missed Opportunities", "Revenue, repeat bookings, and client needs are hard to spot manually."),
            ("bi-ui-checks", "Too Many Admin Tasks", "Small decisions pile up between shooting, editing, and delivery."),
            ("bi-folder2-open", "Scattered Information", "Client details, payments, galleries, and deadlines live in too many places."),
            ("bi-hourglass-split", "Slow Decisions", "Pricing, scheduling, and workflow choices take longer without context."),
            ("bi-graph-down-arrow", "Business Blind Spots", "It is difficult to see what needs attention before it becomes urgent."),
        ],
        "questions": [
            ("Who still owes a payment?", "Three clients have open balances. Harper Wedding is due Friday and ready for a reminder."),
            ("Which galleries are overdue?", "Two galleries are past target delivery. Prioritize Nguyen Family before tomorrow afternoon."),
            ("Summarize my busiest month.", "October has 14 booked sessions, three weddings, and the highest projected revenue."),
            ("Who should I follow up with?", "Five inquiries have not replied in seven days. I drafted a short follow-up for each."),
            ("What is on my schedule tomorrow?", "You have a newborn session at 10 AM, editing block at 1 PM, and a consult at 4 PM."),
            ("Which sessions still need editing?", "Eight sessions are in editing. Two are due this week and one needs final review."),
        ],
        "features": [
            ("bi-bar-chart", "Business Insights", "See plain-language answers about revenue, bookings, and workload."),
            ("bi-person-vcard", "Client Summaries", "Review client history before calls, sessions, and follow-ups."),
            ("bi-calendar2-check", "Smart Scheduling", "Find open time, conflicts, and upcoming session details."),
            ("bi-envelope-paper", "Email Drafts", "Start client messages, reminders, and replies faster."),
            ("bi-currency-dollar", "Revenue Reports", "Understand payments, balances, trends, and expected income."),
            ("bi-diagram-3", "Workflow Guidance", "Know which jobs, galleries, and tasks need attention."),
            ("bi-credit-card", "Payment Tracking", "Find unpaid invoices and deposits without searching."),
            ("bi-images", "Gallery Updates", "See proofing, delivery, favorites, and overdue galleries."),
            ("bi-tags", "Pricing Suggestions", "Review practical pricing ideas based on your services."),
            ("bi-list-check", "Task Lists", "Turn business questions into focused to-do lists."),
            ("bi-arrow-repeat", "Follow-Up Ideas", "Find clients who need a reply, review, or rebooking note."),
            ("bi-chat-dots", "Business Q&A", "Ask everyday questions and get clear next steps."),
        ],
        "kpis": ["Revenue Trends", "Upcoming Sessions", "Pending Tasks", "Outstanding Payments", "Editing Queue", "Repeat Clients", "Business Health", "Weekly Summary"],
        "ai_cards": [
            ("Summarize History", "Understand each client relationship before you respond."),
            ("Generate Emails", "Create friendly drafts you can review and send."),
            ("Recommend Pricing", "Compare packages, add-ons, and booking patterns."),
            ("Find Revenue", "Surface balances, reorders, and rebooking opportunities."),
            ("Predict Seasons", "Prepare for busier weeks before they arrive."),
            ("Suggest Marketing", "Get simple campaign ideas for quieter periods."),
            ("Create Tasks", "Turn decisions into organized next steps."),
            ("Recommend Follow-Ups", "Know who needs attention and why."),
            ("Analyze Performance", "Review business activity in clear language."),
            ("Surface Alerts", "See important changes across your studio."),
            ("Organize Workflows", "Keep jobs moving from inquiry to delivery."),
            ("Answer Questions", "Ask about clients, payments, schedules, and work."),
        ],
        "benefits": [
            ("Save Time", "Spend less time searching and more time shooting."),
            ("Stay Organized", "Keep daily priorities clear across your business."),
            ("Respond Faster", "Turn questions into polished client replies."),
            ("Reduce Admin", "Let repetitive planning become easier to manage."),
            ("Better Decisions", "Use business context instead of guesswork."),
            ("Increase Revenue", "Spot follow-ups, balances, and repeat work."),
            ("Better Experience", "Give clients quicker, more prepared service."),
            ("Focus On Photos", "Protect more time for creative work."),
        ],
        "ecosystem": ["Business Dashboard", "Client CRM", "Booking & Calendar", "Contracts", "Invoices & Payments", "Workflow Automation", "AI Editing", "Client Galleries", "Analytics", "Marketing", "Marketplace"],
        "responsible": [
            ("Human Control", "You review and approve every important decision."),
            ("Privacy", "Business context stays focused on helping your studio operate."),
            ("Security", "Assistant experiences follow LumisPixel platform protections."),
            ("Transparency", "Suggestions are clear, practical, and easy to review."),
            ("Reliable Suggestions", "Recommendations are designed to support, not replace, your judgment."),
            ("Business Context", "Answers are shaped around photography clients, jobs, and workflows."),
        ],
    }
    return render(request, "business_hub_ai_business_assistant.html", context)


def wedding_photography(request):
    context = {
        "stats": [
            "Culling",
            "Face Recognition",
            "Client Galleries",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "Culling"),
            ("bi-magic", "Editing"),
            ("bi-images", "Galleries"),
            ("bi-graph-up-arrow", "Sales"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly identify your strongest images."),
            ("bi-magic", "Editing Assistance", "Speed up repetitive editing tasks."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize couples, families, and guests automatically.",
            ),
            (
                "bi-images",
                "Client Galleries",
                "Deliver polished galleries on any device.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Help guests find their photos with a selfie.",
            ),
            (
                "bi-window",
                "Photographer Websites",
                "Showcase your work and attract new clients.",
            ),
            ("bi-bag-heart", "Print Sales", "Sell prints, albums, and downloads."),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage inquiries, bookings, and communication.",
            ),
            (
                "bi-bar-chart",
                "Analytics",
                "Track galleries, sales, and client activity.",
            ),
        ],
        "pain_solutions": [
            ("Too Many Photos", "Faster Culling"),
            ("Long Editing Hours", "Editing Assistance"),
            ("Slow Delivery", "Easy Gallery Delivery"),
            ("Missed Sales", "Built-In Sales"),
            ("Too Many Tools", "Selfie Photo Search"),
            ("Repeated Client Requests", "One Connected Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate matching images.",
            ),
            ("bi-grid", "Online Galleries", "Browse photos from any device."),
            ("bi-heart", "Favorites", "Save images for albums and prints."),
            (
                "bi-shield-check",
                "Secure Downloads",
                "Access approved high-resolution files.",
            ),
            (
                "bi-bag-check",
                "Print Ordering",
                "Order prints directly from the gallery.",
            ),
            ("bi-share", "Easy Sharing", "Share photos with friends and family."),
        ],
        "timeline": [
            "Book",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Deliver",
            "Search",
            "Download",
            "Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us organize wedding galleries faster and keep delivery simple for clients.",
                "Wedding photographer",
            ),
            (
                "Guests can find their photos without asking us to search through folders after delivery.",
                "Studio owner",
            ),
            (
                "Our gallery was easy to use, and ordering prints felt simple.",
                "Wedding client",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easier Photo Search",
            "More Sales Opportunities",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Guests upload a selfie when the photographer enables search. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "How many photos can I upload?",
                "LumisPixel supports large wedding galleries. Upload limits depend on your plan and storage tier.",
            ),
            (
                "Can I sell prints and albums?",
                "Yes. You can offer prints, albums, downloads, and other products from the gallery.",
            ),
            (
                "Can I create multiple galleries?",
                "Yes. Create separate galleries for weddings, couples, clients, or events.",
            ),
            (
                "Can clients download full-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for galleries, websites, search, sales, client messages, and analytics.",
            ),
        ],
    }
    return render(request, "wedding_photography.html", context)


def portrait_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Online Galleries",
            "Print Sales",
            "Client Management",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Client Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize every client automatically.",
            ),
            ("bi-images", "Client Galleries", "Deliver polished online galleries."),
            (
                "bi-search-heart",
                "Photo Search",
                "Clients find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your portfolio."),
            ("bi-bag-heart", "Print Sales", "Sell prints and digital downloads."),
            ("bi-chat-dots", "Client Management", "Manage bookings and communication."),
            ("bi-bar-chart", "Analytics", "Track sales and gallery activity."),
        ],
        "pain_solutions": [
            ("Finding New Clients", "Better Workflow"),
            ("Editing Time", "Faster Editing"),
            ("Gallery Delivery", "Easy Galleries"),
            ("Missed Print Sales", "Built-In Store"),
            ("Multiple Software Tools", "One Platform"),
            ("Client Communication", "Happy Clients"),
        ],
        "guest_cards": [
            ("bi-search-heart", "Find My Photos", "Use a selfie to find portraits."),
            ("bi-grid", "Online Galleries", "Browse portraits from any device."),
            ("bi-heart", "Favorites", "Save favorite images for later."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share portraits with family."),
        ],
        "timeline": [
            "Book Session",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Gallery",
            "Search",
            "Download",
            "Print Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel keeps sessions organized and makes gallery delivery feel simple.",
                "Portrait photographer",
            ),
            (
                "Clients find favorites quickly, which helps us sell prints without extra emails.",
                "Studio owner",
            ),
            (
                "Our portrait gallery was easy to browse, download, and share with family.",
                "Portrait client",
            ),
        ],
        "metrics": [
            "Better Organization",
            "Faster Delivery",
            "More Print Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Clients upload a selfie when search is enabled. LumisPixel finds matching portraits in the gallery.",
            ),
            (
                "Can clients download full-resolution photos?",
                "Yes. Photographers control download access by gallery and package.",
            ),
            (
                "Can I sell prints?",
                "Yes. You can sell prints and digital downloads from each gallery.",
            ),
            (
                "Can I create multiple galleries?",
                "Yes. Create galleries for sessions, clients, families, or campaigns.",
            ),
            (
                "Can I organize clients automatically?",
                "Yes. Face recognition helps organize people across portrait galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, messages, and analytics.",
            ),
        ],
    }
    return render(request, "portrait_photography.html", context)


def studio_photography(request):
    context = {
        "stats": [
            "Client Galleries",
            "Online Booking",
            "Print Sales",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Client Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-images",
                "Client Galleries",
                "Deliver polished galleries for every session.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Clients find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your studio portfolio."),
            (
                "bi-bag-heart",
                "Print Sales",
                "Sell prints, albums, wall art, and downloads.",
            ),
            (
                "bi-calendar-check",
                "Session Management",
                "Manage appointments and communication.",
            ),
            ("bi-calendar-plus", "Online Booking", "Accept session requests anytime."),
            ("bi-bar-chart", "Analytics", "Track bookings, galleries, and sales."),
        ],
        "pain_solutions": [
            ("Busy Schedule", "Faster Workflow"),
            ("Editing Time", "Better Organization"),
            ("Client Communication", "Easy Galleries"),
            ("Missed Sales", "Built-In Store"),
            ("Too Many Tools", "Online Booking"),
            ("Session Management", "One Platform"),
        ],
        "guest_cards": [
            ("bi-grid", "Client Galleries", "Browse every session in one place."),
            ("bi-heart", "Favorites", "Save favorite images for review."),
            ("bi-shield-check", "Secure Downloads", "Download approved photos safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share images with family or teams."),
            ("bi-phone", "Mobile Access", "View galleries on any device."),
        ],
        "timeline": [
            "Book Session",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Favorites",
            "Order Prints",
            "Download",
        ],
        "testimonials": [
            (
                "Our studio workflow is smoother, from booking to final gallery delivery.",
                "Studio photographer",
            ),
            (
                "Clients choose favorites faster, and print orders are easier to manage.",
                "Portrait studio owner",
            ),
            (
                "LumisPixel helps us deliver sessions quickly while keeping every client organized.",
                "Commercial studio lead",
            ),
        ],
        "metrics": [
            "Better Organization",
            "Faster Delivery",
            "More Print Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "Can clients order prints online?",
                "Yes. Clients can order prints, albums, wall art, and downloads from the gallery.",
            ),
            (
                "Can I manage multiple studio sessions?",
                "Yes. You can organize sessions, clients, galleries, and communication in one place.",
            ),
            (
                "Can clients download high-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I accept online bookings?",
                "Yes. LumisPixel supports online session requests and booking workflows.",
            ),
            (
                "Can clients create favorites?",
                "Yes. Clients can mark favorites for review, downloads, and print orders.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, booking, websites, stores, messages, and analytics.",
            ),
        ],
    }
    return render(request, "studio_photography.html", context)


def sports_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Online Galleries",
            "Team Galleries",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-collection", "Team Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly remove duplicates and missed shots."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize athletes automatically.",
            ),
            ("bi-collection", "Team Galleries", "Create galleries by team or event."),
            ("bi-search-heart", "Photo Search", "Find photos with a selfie."),
            ("bi-window", "Photographer Websites", "Showcase your sports portfolio."),
            ("bi-bag-heart", "Print Sales", "Sell prints, banners, and downloads."),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage teams, leagues, and communication.",
            ),
            ("bi-bar-chart", "Analytics", "Track gallery views and sales."),
        ],
        "pain_solutions": [
            ("Thousands of Photos", "Faster Culling"),
            ("Fast Turnaround", "AI Face Search"),
            ("Finding Athletes", "Organized Galleries"),
            ("Multiple Teams", "Easy Delivery"),
            ("Missed Sales", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate game photos.",
            ),
            ("bi-collection", "Team Galleries", "Browse photos by team or event."),
            ("bi-heart", "Favorites", "Save favorite action shots."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints and banners online."),
            ("bi-share", "Easy Sharing", "Share highlights with family and teammates."),
        ],
        "timeline": [
            "Book Event",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Search",
            "Download",
            "Print Order",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us sort game-day photos faster and publish galleries while families are still excited.",
                "Sports photographer",
            ),
            (
                "Selfie search makes athlete discovery simple. Parents spend less time scrolling and more time ordering favorites.",
                "Tournament photographer",
            ),
            (
                "Team galleries keep everything organized, and built-in print sales make banners and downloads easy.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Athlete Search",
            "More Print Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Athletes or parents upload a selfie when search is enabled. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "Can I create galleries for multiple teams?",
                "Yes. Create galleries by team, league, tournament, or event.",
            ),
            (
                "Can parents download full-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I sell prints and banners?",
                "Yes. Sell prints, banners, downloads, and other products from the gallery.",
            ),
            (
                "Can I organize athletes automatically?",
                "Yes. Face recognition helps group athletes across high-volume galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, messages, search, and analytics.",
            ),
        ],
    }
    return render(request, "sports_photography.html", context)


def real_estate_photography(request):
    context = {
        "stats": [
            "Property Galleries",
            "Fast Delivery",
            "Digital Downloads",
            "Client Management",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Property Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best property photos."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            ("bi-images", "Property Galleries", "Create galleries for every listing."),
            ("bi-window", "Photographer Websites", "Showcase your portfolio."),
            (
                "bi-cloud-download",
                "Digital Downloads",
                "Deliver high-resolution files instantly.",
            ),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage listings, agents, and communication.",
            ),
            (
                "bi-calendar-check",
                "Scheduling",
                "Keep shoots and appointments organized.",
            ),
            ("bi-bar-chart", "Analytics", "Track galleries, downloads, and activity."),
            (
                "bi-megaphone",
                "Marketing Assets",
                "Deliver files for MLS and social media.",
            ),
        ],
        "pain_solutions": [
            ("Tight Deadlines", "Faster Workflow"),
            ("Multiple Listings", "Organized Listings"),
            ("Large File Delivery", "Easy Delivery"),
            ("Client Revisions", "Secure Downloads"),
            ("Too Many Tools", "One Platform"),
            ("Busy Schedules", "Better Client Experience"),
        ],
        "guest_cards": [
            ("bi-images", "Property Galleries", "View every listing in one gallery."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-heart", "Favorites", "Save preferred property photos."),
            ("bi-share", "Easy Sharing", "Share galleries with clients quickly."),
            ("bi-lightning", "Fast Delivery", "Access final photos sooner."),
            ("bi-phone", "Mobile Access", "Review galleries from any device."),
        ],
        "timeline": [
            "Book Shoot",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Download",
            "Share",
            "List Property",
        ],
        "testimonials": [
            (
                "LumisPixel helps us publish property galleries quickly and keep every listing organized for agents.",
                "Real estate photographer",
            ),
            (
                "Agents get clean galleries, fast downloads, and fewer back-and-forth messages after each shoot.",
                "Photography studio owner",
            ),
            (
                "Faster delivery and organized files have helped us win repeat business from busy brokers.",
                "Property photographer",
            ),
        ],
        "metrics": [
            "Faster Delivery",
            "Organized Listings",
            "Better Client Experience",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "Can I create galleries for every property?",
                "Yes. Create a separate gallery for each listing, property, or client.",
            ),
            (
                "Can agents download full-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I organize multiple listings?",
                "Yes. Keep listings, agents, galleries, and files organized in one place.",
            ),
            (
                "Can I deliver MLS-ready files?",
                "Yes. Deliver final files for MLS, websites, and social media.",
            ),
            (
                "Can I manage multiple clients?",
                "Yes. Manage agents, brokers, property managers, and homeowners together.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, file sharing, galleries, websites, scheduling, messages, and analytics.",
            ),
        ],
    }
    return render(request, "real_estate_photography.html", context)


def school_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Student Galleries",
            "Online Ordering",
            "Print Sales",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Student Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best photos."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize students automatically.",
            ),
            (
                "bi-images",
                "Student Galleries",
                "Create secure galleries for every student.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Parents find student photos with a selfie.",
            ),
            (
                "bi-window",
                "Photographer Websites",
                "Promote your school photography services.",
            ),
            (
                "bi-bag-heart",
                "Print Sales",
                "Sell print packages and digital downloads.",
            ),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage schools, classes, and communication.",
            ),
            ("bi-bar-chart", "Analytics", "Track orders, galleries, and sales."),
        ],
        "pain_solutions": [
            ("Thousands of Students", "Faster Organization"),
            ("Picture Day Deadlines", "AI Face Search"),
            ("Finding Students", "Secure Galleries"),
            ("Multiple Schools", "Easy Delivery"),
            ("Print Orders", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate school photos.",
            ),
            ("bi-images", "Student Galleries", "View photos in a private gallery."),
            ("bi-heart", "Favorites", "Save favorite poses for ordering."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Online Ordering", "Order prints and downloads online."),
            ("bi-share", "Easy Sharing", "Share photos with family."),
        ],
        "timeline": [
            "Book School",
            "Picture Day",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Galleries",
            "Photo Search",
            "Order Prints",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us organize students faster and deliver galleries before picture day questions pile up.",
                "School photographer",
            ),
            (
                "Parents find their child quickly, choose favorites, and order prints without extra emails.",
                "Studio owner",
            ),
            (
                "Picture day feels smoother when galleries, search, and orders stay in one place.",
                "School coordinator",
            ),
        ],
        "metrics": [
            "Faster Student Organization",
            "Easier Parent Search",
            "More Print Orders",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Parents upload a selfie when search is enabled. LumisPixel finds matching student photos in the gallery.",
            ),
            (
                "Can parents order photos online?",
                "Yes. Parents can order print packages and digital downloads from the gallery.",
            ),
            (
                "Can I create galleries for each student?",
                "Yes. You can create secure galleries organized around each student.",
            ),
            (
                "Can schools have private galleries?",
                "Yes. Photographers can keep school galleries private and control access.",
            ),
            (
                "Can I sell print packages?",
                "Yes. LumisPixel supports print packages, downloads, and online ordering.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, galleries, websites, stores, parent communication, search, and analytics.",
            ),
        ],
    }
    return render(request, "school_photography.html", context)


def corporate_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Private Galleries",
            "Team Galleries",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Private Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize employees and attendees automatically.",
            ),
            (
                "bi-images",
                "Private Galleries",
                "Deliver secure galleries for every client.",
            ),
            (
                "bi-search-heart",
                "Photo Search",
                "Employees find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your business portfolio."),
            (
                "bi-cloud-download",
                "Digital Downloads",
                "Deliver high-resolution files with ease.",
            ),
            (
                "bi-chat-dots",
                "Client Management",
                "Manage companies, events, and communication.",
            ),
            (
                "bi-bar-chart",
                "Analytics",
                "Track galleries, downloads, and engagement.",
            ),
        ],
        "pain_solutions": [
            ("Large Events", "Faster Organization"),
            ("Tight Deadlines", "AI Face Search"),
            ("Finding Attendees", "Private Galleries"),
            ("Multiple Clients", "Easy Delivery"),
            ("Secure Delivery", "Secure Sharing"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate event photos.",
            ),
            ("bi-images", "Private Galleries", "Access approved client galleries."),
            ("bi-heart", "Favorites", "Save images for review."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-share", "Easy Sharing", "Share photos with approved teams."),
            ("bi-people", "Team Access", "Give organizers controlled gallery access."),
        ],
        "timeline": [
            "Book Client",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Photo Search",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "Corporate galleries stay organized, and delivery feels faster for every event client.",
                "Corporate photographer",
            ),
            (
                "Employees find headshots and conference images without extra requests to our team.",
                "Event organizer",
            ),
            (
                "LumisPixel keeps our workflow simple from upload to secure client delivery.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Employee Search",
            "Secure Delivery",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Employees upload a selfie when search is enabled. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "Can I create private client galleries?",
                "Yes. Create private galleries for companies, events, teams, or headshot sessions.",
            ),
            (
                "Can employees download high-resolution photos?",
                "Yes. Photographers control which files employees can download.",
            ),
            (
                "Can I organize multiple events?",
                "Yes. Manage separate companies, events, galleries, and communication in one place.",
            ),
            (
                "Is gallery access secure?",
                "Yes. Private galleries and controlled downloads help protect client access.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace tools for editing, galleries, face search, websites, file sharing, messages, and analytics.",
            ),
        ],
    }
    return render(request, "corporate_photography.html", context)


def commercial_photography(request):
    context = {
        "stats": [
            "Client Galleries",
            "Fast Delivery",
            "Digital Downloads",
            "Project Management",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Client Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-images",
                "Client Galleries",
                "Deliver polished galleries for every project.",
            ),
            (
                "bi-window",
                "Photographer Websites",
                "Showcase your commercial portfolio.",
            ),
            (
                "bi-cloud-download",
                "Digital Downloads",
                "Deliver high-resolution files instantly.",
            ),
            (
                "bi-kanban",
                "Project Management",
                "Manage clients, projects, and communication.",
            ),
            ("bi-heart", "Proofing & Favorites", "Collect client selections quickly."),
            ("bi-bar-chart", "Analytics", "Track gallery activity and downloads."),
            (
                "bi-shield-check",
                "Brand Asset Delivery",
                "Share approved marketing assets securely.",
            ),
        ],
        "pain_solutions": [
            ("Tight Deadlines", "Faster Workflow"),
            ("Multiple Revisions", "Easy Proofing"),
            ("Large File Delivery", "Secure Delivery"),
            ("Client Approvals", "Organized Projects"),
            ("Too Many Tools", "One Platform"),
            ("Multiple Projects", "Better Client Experience"),
        ],
        "guest_cards": [
            ("bi-images", "Client Galleries", "Review every project in one place."),
            ("bi-heart", "Favorites", "Mark preferred images for approval."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-share", "Easy Sharing", "Share assets with your team."),
            (
                "bi-check2-square",
                "Project Proofing",
                "Approve selections without long email threads.",
            ),
            (
                "bi-people",
                "Team Access",
                "Give collaborators controlled gallery access.",
            ),
        ],
        "timeline": [
            "Book Project",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Review",
            "Publish Gallery",
            "Approve",
            "Download",
            "Deliver",
        ],
        "testimonials": [
            (
                "Approvals move faster because clients review, favorite, and download from one organized gallery.",
                "Commercial photographer",
            ),
            (
                "Each campaign stays organized, from proofing to final asset delivery for our brand clients.",
                "Studio owner",
            ),
            (
                "Clients enjoy the clean gallery experience, and that helps us earn repeat projects.",
                "Creative director",
            ),
        ],
        "metrics": [
            "Faster Approvals",
            "Organized Projects",
            "Better Client Experience",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "Can clients review and approve images?",
                "Yes. Clients can review galleries, mark favorites, and approve selections in one place.",
            ),
            (
                "Can I create galleries for multiple projects?",
                "Yes. Create separate galleries for campaigns, products, clients, or deliverables.",
            ),
            (
                "Can teams download approved files?",
                "Yes. Photographers control which files teams can download.",
            ),
            (
                "Can clients mark favorites?",
                "Yes. Favorites help clients share selections and request edits quickly.",
            ),
            (
                "Can I manage multiple commercial clients?",
                "Yes. Keep clients, projects, galleries, and communication organized together.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace separate tools for editing, file sharing, galleries, proofing, project management, messages, and analytics.",
            ),
        ],
    }
    return render(request, "commercial_photography.html", context)


def event_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Private Galleries",
            "Event Galleries",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-stars", "AI Culling"),
            ("bi-person-bounding-box", "Face Recognition"),
            ("bi-images", "Event Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            (
                "bi-person-bounding-box",
                "Face Recognition",
                "Organize attendees automatically.",
            ),
            ("bi-images", "Event Galleries", "Create galleries for every event."),
            (
                "bi-search-heart",
                "Photo Search",
                "Guests find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your event portfolio."),
            (
                "bi-cloud-download",
                "Print & Downloads",
                "Sell prints and digital files.",
            ),
            ("bi-chat-dots", "Client Management", "Manage events and communication."),
            ("bi-bar-chart", "Analytics", "Track galleries, downloads, and sales."),
        ],
        "pain_solutions": [
            ("Large Crowds", "Faster Organization"),
            ("Tight Deadlines", "AI Face Search"),
            ("Finding Guests", "Event Galleries"),
            ("Multiple Events", "Easy Delivery"),
            ("Missed Sales", "Built-In Store"),
            ("Too Many Tools", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Use a selfie to locate event photos.",
            ),
            ("bi-images", "Event Galleries", "Browse photos from every event."),
            ("bi-heart", "Favorites", "Save favorite moments for later."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share photos with friends and teams."),
        ],
        "timeline": [
            "Book Event",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Organize",
            "Publish Gallery",
            "Photo Search",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel helps us deliver event galleries faster without losing track of important guest photos.",
                "Event photographer",
            ),
            (
                "Guests use selfie search instead of asking our team to find photos manually.",
                "Gala photographer",
            ),
            (
                "Our client galleries stay organized, and attendees leave happier with easy downloads.",
                "Studio owner",
            ),
        ],
        "metrics": [
            "Faster Organization",
            "Easy Guest Search",
            "More Sales",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Guests upload a selfie when search is enabled. LumisPixel finds matching photos in the event gallery.",
            ),
            (
                "Can I create galleries for multiple events?",
                "Yes. Create separate galleries for conferences, galas, festivals, fundraisers, and private events.",
            ),
            (
                "Can guests download high-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I sell prints and digital downloads?",
                "Yes. Sell prints and digital files directly from each gallery.",
            ),
            (
                "Can I organize attendees automatically?",
                "Yes. Face recognition helps group attendees across high-volume event galleries.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace tools for editing, galleries, face search, websites, stores, messages, and analytics.",
            ),
        ],
    }
    return render(request, "event_photography.html", context)


def destination_photography(request):
    context = {
        "stats": [
            "AI Photo Search",
            "Client Galleries",
            "Print Sales",
            "Digital Downloads",
        ],
        "photographer_cards": [
            ("bi-funnel", "AI Culling"),
            ("bi-magic", "Editing Assistance"),
            ("bi-images", "Client Galleries"),
            ("bi-graph-up-arrow", "Business Growth"),
        ],
        "features": [
            ("bi-funnel", "AI Culling", "Quickly sort your best images."),
            ("bi-magic", "Editing Assistance", "Reduce repetitive editing work."),
            ("bi-images", "Client Galleries", "Deliver galleries from anywhere."),
            (
                "bi-search-heart",
                "Photo Search",
                "Clients find their photos with a selfie.",
            ),
            ("bi-window", "Photographer Websites", "Showcase your travel portfolio."),
            ("bi-bag-check", "Print Sales", "Sell prints and digital downloads."),
            ("bi-chat-dots", "Client Management", "Manage travelers and bookings."),
            ("bi-phone", "Mobile Access", "Access projects anywhere."),
            ("bi-bar-chart", "Analytics", "Track galleries, downloads, and sales."),
        ],
        "pain_solutions": [
            ("Travel Logistics", "Faster Workflow"),
            ("Tight Timelines", "Organized Projects"),
            ("Remote Delivery", "Easy Galleries"),
            ("Client Communication", "Secure Delivery"),
            ("Too Many Tools", "Better Communication"),
            ("Busy Schedule", "One Platform"),
        ],
        "guest_cards": [
            (
                "bi-search-heart",
                "Find My Photos",
                "Upload a selfie to find travel photos.",
            ),
            (
                "bi-images",
                "Client Galleries",
                "Browse memories in one private gallery.",
            ),
            ("bi-heart", "Favorites", "Save favorite images for later."),
            ("bi-shield-check", "Secure Downloads", "Download approved files safely."),
            ("bi-bag-check", "Print Ordering", "Order prints from the gallery."),
            ("bi-share", "Easy Sharing", "Share photos with friends and family."),
        ],
        "timeline": [
            "Book Session",
            "Travel",
            "Capture",
            "Upload",
            "Cull",
            "Edit",
            "Publish Gallery",
            "Photo Search",
            "Download",
            "Share",
        ],
        "testimonials": [
            (
                "LumisPixel keeps destination shoots organized while we move between locations and clients.",
                "Destination photographer",
            ),
            (
                "Our travelers receive galleries faster, even when we are still on the road.",
                "Travel photographer",
            ),
            (
                "Selfie search creates happier clients and helps bring repeat bookings from past travelers.",
                "Elopement photographer",
            ),
        ],
        "metrics": [
            "Better Organization",
            "Faster Delivery",
            "Happy Travelers",
            "One Connected Workflow",
        ],
        "faqs": [
            (
                "How does selfie photo search work?",
                "Clients upload a selfie when search is enabled. LumisPixel finds matching photos in the gallery.",
            ),
            (
                "Can clients download high-resolution photos?",
                "Yes. Photographers control download access for each gallery and package.",
            ),
            (
                "Can I manage multiple destinations?",
                "Yes. Organize shoots, galleries, and clients by trip or location.",
            ),
            (
                "Can I sell prints and downloads?",
                "Yes. Sell prints and digital downloads directly from each gallery.",
            ),
            (
                "Can I deliver galleries while traveling?",
                "Yes. Publish and share client galleries from anywhere with access.",
            ),
            (
                "Which tools can LumisPixel replace?",
                "It can replace tools for editing, galleries, websites, stores, messages, file sharing, and analytics.",
            ),
        ],
    }
    return render(request, "destination_photography.html", context)


def robots_txt(request):
    from django.http import HttpResponse

    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def for_photographers(request):
    context = {
        "pain_points": [
            {
                "icon": "bi-images",
                "text": "Too many photos to organize after each shoot.",
            },
            {
                "icon": "bi-chat-dots",
                "text": "Clients asking you to find their photos.",
            },
            {
                "icon": "bi-cloud-arrow-up",
                "text": "Hours lost uploading galleries and links.",
            },
            {
                "icon": "bi-bag-x",
                "text": "Missed print sales from disconnected buying.",
            },
            {
                "icon": "bi-grid-3x3-gap",
                "text": "Separate apps for galleries, websites, sales, and analytics.",
            },
            {
                "icon": "bi-search",
                "text": "Hard-to-search events, people, and moments.",
            },
            {
                "icon": "bi-window",
                "text": "A website that does not match your brand.",
            },
            {
                "icon": "bi-graph-up",
                "text": "Scattered insights across disconnected tools.",
            },
        ],
        "workflow": [
            "Client books session",
            "Create Event",
            "Shoot",
            "Upload Photos",
            "AI Organizes",
            "Client Finds Photos",
            "Sell Photos",
            "Grow Business",
        ],
        "features": [
            {
                "title": "Photographer Workspace",
                "copy": "Manage clients, events, billing, orders, analytics, and marketing from one calm workspace.",
                "bullets": [
                    "Dashboard, clients, and events",
                    "Billing, orders, and revenue",
                    "Marketing and business visibility",
                ],
                "image": "img/landing/gallery/31.jpg",
                "alt": "Photographer reviewing a business workspace",
                "callout": "Studio overview",
                "micro": "Know what needs attention today.",
            },
            {
                "title": "AI Photo Search",
                "copy": "Let clients find themselves, people, and moments without scrolling through every image.",
                "bullets": [
                    "Face recognition and selfie search",
                    "Semantic, event, and people search",
                    "Auto tagging for faster discovery",
                ],
                "image": "img/landing/gallery/38.jpg",
                "alt": "Client gallery search experience",
                "callout": "Selfie search",
                "micro": "The right photos in seconds.",
            },
            {
                "title": "AI Editing & Culling",
                "copy": "Speed up review with AI signals for quality issues, duplicates, and likely keepers.",
                "bullets": [
                    "Blur and closed-eye detection",
                    "Quality scoring and duplicates",
                    "Best image selection and editing assistance",
                ],
                "image": "img/landing/gallery/25.jpg",
                "alt": "Photographer selecting best images",
                "callout": "Smart culling",
                "micro": "Less sorting. More creating.",
            },
            {
                "title": "Client Galleries",
                "copy": "Deliver polished galleries clients can access, share, favorite, download, and buy from.",
                "bullets": [
                    "Password protection and watermarks",
                    "Favorites, downloads, QR codes",
                    "Event codes for fast access",
                ],
                "image": "img/landing/gallery/40.jpg",
                "alt": "Beautiful online client gallery",
                "callout": "Client-ready",
                "micro": "Beautiful delivery every time.",
            },
            {
                "title": "Photographer Websites",
                "copy": "Build a professional portfolio site that turns visitors into inquiries.",
                "bullets": [
                    "Portfolio and theme selection",
                    "Branding, SEO, and contact pages",
                    "Professional websites for every specialty",
                ],
                "image": "img/landing/gallery/20.jpg",
                "alt": "Photography website portfolio",
                "callout": "Brand home",
                "micro": "Your portfolio, polished.",
            },
            {
                "title": "Sales & Store",
                "copy": "Sell downloads, prints, albums, and offers directly from the gallery.",
                "bullets": [
                    "Digital downloads, prints, and frames",
                    "Albums, packages, and gift cards",
                    "Coupons for campaigns and events",
                ],
                "image": "img/landing/gallery/12.jpg",
                "alt": "Photography print and album sales",
                "callout": "Built-in sales",
                "micro": "Capture demand in the moment.",
            },
            {
                "title": "Business Analytics",
                "copy": "See revenue, downloads, views, popular images, and client engagement in one place.",
                "bullets": [
                    "Revenue and sales performance",
                    "Downloads and gallery views",
                    "Popular images and client engagement",
                ],
                "image": "img/landing/gallery/9.jpg",
                "alt": "Analytics for photography business",
                "callout": "Live insights",
                "micro": "Make growth visible.",
            },
            {
                "title": "Marketplace",
                "copy": "Connect with requests, collaborators, second shooters, editors, and future client discovery.",
                "bullets": [
                    "Photography requests",
                    "Second shooters, retouchers, and editors",
                    "Future client marketplace",
                ],
                "image": "img/landing/gallery/15.jpg",
                "alt": "Photography marketplace collaboration",
                "callout": "Growth network",
                "micro": "More ways to expand.",
            },
        ],
        "ai_tools": [
            "Face Recognition",
            "Smart Search",
            "Quality Detection",
            "Blur Detection",
            "Duplicate Detection",
            "Auto Tagging",
            "Editing Assistance",
            "Smart Collections",
            "Semantic Search",
            "Future AI Recommendations",
        ],
        "comparison": [
            {
                "category": "Gallery delivery",
                "traditional": "Upload, copy links, explain access, repeat.",
                "lumis": "Branded galleries with event codes, favorites, downloads, and sales.",
            },
            {
                "category": "Website",
                "traditional": "Separate site builder and disconnected portfolio.",
                "lumis": "Photography websites, themes, branding, SEO, and contact pages.",
            },
            {
                "category": "AI Search",
                "traditional": "Manual folders and endless scrolling.",
                "lumis": "Face, selfie, semantic, and event search.",
            },
            {
                "category": "AI Culling",
                "traditional": "Manual checks for blur, duplicates, and closed eyes.",
                "lumis": "Quality signals, duplicate detection, and best image selection.",
            },
            {
                "category": "Online Sales",
                "traditional": "Separate store or missed print demand.",
                "lumis": "Downloads, prints, albums, frames, packages, coupons, and gift cards.",
            },
            {
                "category": "Business Dashboard",
                "traditional": "Spreadsheets and scattered apps.",
                "lumis": "Clients, events, billing, orders, analytics, and marketing.",
            },
            {
                "category": "Marketplace",
                "traditional": "Text threads and informal referrals.",
                "lumis": "Requests, collaborators, second shooters, retouchers, and editors.",
            },
            {
                "category": "Client Selfie Search",
                "traditional": "Clients ask you to find their photos.",
                "lumis": "Clients upload a selfie and find images instantly.",
            },
        ],
        "photographer_types": [
            {"name": n, "icon": i}
            for n, i in [
                ("Wedding", "bi-heart"),
                ("Portrait", "bi-person-square"),
                ("Sports", "bi-trophy"),
                ("School", "bi-mortarboard"),
                ("Corporate", "bi-briefcase"),
                ("Commercial", "bi-badge-ad"),
                ("Events", "bi-calendar-event"),
                ("Real Estate", "bi-house"),
                ("Studio", "bi-camera"),
                ("Travel", "bi-airplane"),
                ("Families", "bi-people"),
                ("Drone", "bi-broadcast"),
            ]
        ],
        "roadmap": [
            {
                "status": "Future",
                "title": "AI Editing",
                "copy": "Style-aware edits and guided adjustments.",
            },
            {
                "status": "Future",
                "title": "AI Album Design",
                "copy": "Layouts based on story, emotion, and selections.",
            },
            {
                "status": "Future",
                "title": "Marketing Assistant",
                "copy": "Campaign ideas, email drafts, and sales prompts.",
            },
            {
                "status": "Future",
                "title": "Mobile App",
                "copy": "Studio and client access on the go.",
            },
            {
                "status": "Expanding",
                "title": "Marketplace",
                "copy": "Requests, collaborators, and discovery.",
            },
            {
                "status": "Future",
                "title": "Studio CRM",
                "copy": "Client history and pipeline management.",
            },
            {
                "status": "Future",
                "title": "Booking System",
                "copy": "Availability, deposits, packages, and scheduling.",
            },
            {
                "status": "Future",
                "title": "Smart Contracts",
                "copy": "Templates and guided agreements.",
            },
        ],
        "testimonials": [
            {
                "text": "It understands gallery delivery, client questions, and the chaos after a big event.",
                "role": "Placeholder testimonial — wedding photographer",
            },
            {
                "text": "Fewer tools, faster client discovery, and more ways to sell the work I already created.",
                "role": "Placeholder testimonial — sports photographer",
            },
            {
                "text": "My website, galleries, orders, and analytics should finally work together.",
                "role": "Placeholder testimonial — portrait studio owner",
            },
        ],
        "faqs": [
            {
                "q": "Can clients upload selfies?",
                "a": "Yes. Clients can use selfie-based discovery to find their images quickly in supported galleries.",
            },
            {
                "q": "Can I sell prints?",
                "a": "Yes. The sales vision includes prints, frames, albums, packages, downloads, coupons, and gift cards.",
            },
            {
                "q": "Can I use my own branding?",
                "a": "Yes. Websites and galleries support themes, branding, portfolios, SEO, and contact pages.",
            },
            {
                "q": "Can clients download photos?",
                "a": "Yes. Galleries support downloads with passwords, favorites, watermarks, QR codes, and event codes.",
            },
            {
                "q": "How does AI work?",
                "a": "AI powers search, face recognition, quality checks, blur and duplicate detection, tagging, smart collections, and future recommendations.",
            },
            {
                "q": "Can I migrate from another gallery provider?",
                "a": "Migration tools are planned. LumisPixel is being built for photographers replacing multiple disconnected tools.",
            },
            {
                "q": "What file formats are supported?",
                "a": "Final file-format support will be confirmed as upload and processing services are implemented.",
            },
            {
                "q": "How secure are my galleries?",
                "a": "Galleries are designed for passwords, event codes, watermarks, and controlled downloads. Production security depends on backend enforcement.",
            },
        ],
    }
    return render(request, "for_photographers.html", context)
