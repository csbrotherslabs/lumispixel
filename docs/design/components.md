# LumisPixel Template Components

Reusable components live in `templates/components/` and are included from page templates with explicit `with` variables. They preserve the homepage's existing classes and behavior while reducing repeated markup.

## Button
- **Path:** `templates/components/button.html`
- **Purpose:** Render existing LumisPixel CTA button/link markup.
- **Required variables:** `label`
- **Optional variables:** `href`, `variant` (`primary`, `secondary`, `outline`, `solid`, default theme button), `extra_class`, `aria_label`, `icon`, `show_second`, `second_label`, `target`, `disabled`, `placeholder`.
- **Example:** `{% include "components/button.html" with label="Start Free" href="#" variant="primary" show_second=True %}`
- **Current pages:** Homepage (`templates/index.html`).
- **Accessibility:** Renders semantic links, supports `aria_label`, preserves visible focus styles from existing button classes, and adds safe `rel` behavior for `_blank` targets.

## Text Link
- **Path:** `templates/components/text_link.html`
- **Purpose:** Render simple text CTA links that are visually distinct from filled buttons.
- **Required variables:** `label`
- **Optional variables:** `href`, `class_name`, `extra_class`, `aria_label`, `arrow`, `placeholder`.
- **Example:** `{% include "components/text_link.html" with label="Hire a Photographer →" href="#" class_name="wptb-hero-text-link" %}`
- **Current pages:** Homepage.
- **Accessibility:** Keeps links as anchors and supports explicit accessible labels where visible text is not enough.

## Section Heading
- **Path:** `templates/components/section_heading.html`
- **Purpose:** Render repeated homepage heading groups with eyebrow, title, and supporting copy.
- **Required variables:** At least one of `eyebrow`, `title`, or `copy`.
- **Optional variables:** `wrapper_class`, `extra_class`, `section_number`, `alignment`, `title_class`, `title_id`, `copy_class`.
- **Example:** `{% include "components/section_heading.html" with wrapper_class="wptb-heading mb-0" section_number="01 //" eyebrow="FIND YOUR PHOTOS" title="Your Photos. <span>Found in Seconds.</span>" title_id="photo-match-title" copy="Upload a selfie and quickly find your photos from participating events and galleries." %}`
- **Current pages:** Homepage.
- **Accessibility:** Preserves heading IDs for section `aria-labelledby` relationships; `title` allows approved inline emphasis markup already present in the homepage.

## Badge
- **Path:** `templates/components/badge.html`
- **Purpose:** Render small noninteractive labels and preview/status badges.
- **Required variables:** `label`
- **Optional variables:** `class_name`, `variant`, `extra_class`, `aria_hidden`.
- **Example:** `{% include "components/badge.html" with label="Visual only" class_name="lumis-marketplace-panel__badge" %}`
- **Current pages:** Homepage.
- **Accessibility:** Noninteractive by default; can be hidden from assistive technology when the badge is decorative.

## Carousel Controls
- **Path:** `templates/components/carousel_controls.html`
- **Purpose:** Render Swiper previous/next arrow controls without changing plugin selectors.
- **Required variables:** None.
- **Optional variables:** `style`, `wrapper_class`, `previous_class`, `next_class`, `previous_label`, `next_label`.
- **Example:** `{% include "components/carousel_controls.html" with style="style2" previous_label="Show previous LumisPixel feature" next_label="Show next LumisPixel feature" %}`
- **Current pages:** Homepage.
- **Accessibility:** Keeps Swiper classes intact and supports explicit labels plus keyboard roles when labels are supplied.

## Pricing Card
- **Path:** `templates/components/pricing_card.html`
- **Purpose:** Render the repeated pricing plan card structure.
- **Required variables:** `plan_name`, `audience`, `price`, `monthly_price`, `cta_label`.
- **Optional variables:** `annual_price`, `feature_1` through `feature_6`, `cta_url`, `highlighted`, `badge_text`, `disclaimer`.
- **Example:** `{% include "components/pricing_card.html" with plan_name="Starter" audience="For photographers getting started." price="Free" monthly_price="Free" annual_price="Free" feature_1="Essential client galleries" cta_label="Start Free" cta_url="#" %}`
- **Current pages:** Homepage.
- **Accessibility:** Uses semantic `<article>` cards, keeps pricing toggle data attributes on the price element, and preserves link CTAs.
