from django.shortcuts import render

from apps.core.views import add, public_page as core_public_page

add("photographer_websites", "Photographer Websites", "Products", description="Introduce portfolio-ready photographer websites connected to the LumisPixel platform.")


def public_page(request, page_key):
    if page_key == "photographer_websites":
        context = {
            "first_impression": [
                ("bi-images", "Showcase your portfolio", "Present your strongest images in a focused, professional experience."),
                ("bi-shield-check", "Build trust", "Give prospects a polished place to understand your business."),
                ("bi-palette", "Display your style", "Let your visual direction and tone guide every page."),
                ("bi-card-checklist", "Highlight your services", "Explain what you offer without overwhelming new visitors."),
                ("bi-chat-dots", "Connect with clients", "Make inquiries easier with clear contact paths."),
                ("bi-graph-up-arrow", "Grow your brand", "Create a home base for sharing, referrals, and campaigns."),
            ],
            "theme_points": ["Elegant layouts", "Responsive design", "Photography-first presentation", "Clean navigation", "Modern typography", "Brand customization"],
            "workflow": ["Create Website", "Show Portfolio", "Display Galleries", "Clients View Photos", "Share Website", "Grow Business"],
            "photo_features": [
                ("Portfolio Pages", "Show curated work by specialty, session type, or campaign."),
                ("About Me", "Tell your story and help clients feel confident reaching out."),
                ("Services", "Describe packages, specialties, and engagement options clearly."),
                ("Contact Page", "Give visitors a direct path to ask questions or inquire."),
                ("Client Galleries", "Connect website discovery with gallery viewing when enabled."),
                ("Featured Work", "Spotlight signature shoots, recent events, or favorite projects."),
                ("Testimonials", "Reserve space for approved client feedback and social proof."),
                ("Blog", "Planned: publish stories, session tips, and updates in a future release."),
                ("Booking", "Coming Soon: support scheduling and booking when released."),
            ],
            "brand_items": ["Logo", "Colors", "Typography", "Homepage Layout", "Navigation", "Cover Images", "Portfolio Categories", "Business Information"],
            "device_points": ["Responsive layouts", "Fast loading", "Touch friendly", "Modern design"],
            "growth_points": [
                "Professional credibility", "Easy sharing", "Stronger online presence", "Gallery integration", "Client confidence", "Future booking integration", "SEO-ready structure",
            ],
            "comparison": [
                ("WordPress", "Website"),
                ("Gallery platform", "Portfolio"),
                ("Separate branding", "Galleries"),
                ("Separate hosting", "Branding"),
                ("Multiple logins", "AI features"),
                ("Disconnected updates", "One platform"),
            ],
            "photographer_types": ["Wedding", "Portrait", "Sports", "Commercial", "Corporate", "School", "Events", "Real Estate", "Studio", "Travel", "Drone", "Families"],
            "roadmap": ["Booking System", "Online Scheduling", "Custom Domains", "SEO Tools", "Marketing Dashboard", "Blog", "Client Portals", "AI Website Assistant", "Newsletter Integration"],
            "faqs": [
                ("Do I need coding skills?", "No. The website experience is designed for photographers to customize without writing code."),
                ("Can I use my own logo?", "Yes. Branding options are designed to support your logo and business identity."),
                ("Can I connect my galleries?", "LumisPixel is designed to connect websites with client galleries when gallery features are enabled."),
                ("Can I customize colors?", "Yes. Theme customization is designed to support brand colors and visual direction."),
                ("Will my website work on mobile?", "Yes. The page and theme direction prioritize responsive desktop, tablet, and mobile layouts."),
                ("Can I use my own domain?", "Custom domains are a roadmap item and should be considered available when released."),
                ("Can I update my portfolio anytime?", "Portfolio editing is designed to let photographers refresh featured work as their brand evolves."),
                ("Can clients contact me?", "Contact pages are designed to help visitors inquire directly when contact options are configured."),
            ],
        }
        return render(request, "photographer_websites.html", context)
    return core_public_page(request, page_key)
