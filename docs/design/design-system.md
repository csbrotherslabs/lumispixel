# LumisPixel Global Design System

This design system documents the visual language already established by the finished LumisPixel homepage. It is a practical reference for future Django templates, reusable components, and CSS work. It is not a redesign brief.

## Brand Principles

**Product name:** LumisPixel

LumisPixel should feel premium but approachable: photography-first, intelligent without looking overly technical, modern and minimal, confident with whitespace, and restrained with red accents. Imagery should stay emotionally central; AI features support the photography experience rather than replacing it.

### Homepage audit notes

The current homepage combines inherited template styles with LumisPixel-specific sections. The design language is consistent overall, but the audit found these documented differences:

- **Red accents:** the template brand token is `--color-one: #B90808`, while newer homepage modules use a brighter action red `#d70006` and hover/active reds `#c90006` / `#b70005`. This appears intentional for modern homepage CTAs and high-priority accents; do not globally change `--color-one` without a separate visual QA pass.
- **Text colors:** most light sections use near-black values between `#151515` and `#181818`; supporting copy ranges from warm gray `#4d4a47` to `#6c665f`. These are purposeful hierarchy differences.
- **Surfaces:** white cards sit on warm off-white sections (`#f8f6f3`, `#fbf8f5`, gradient creams). Dark marketplace and final CTA sections intentionally invert the palette.
- **Radii:** cards range from 18px to 30px; small controls use 8px to 16px; pills use 999px. The variation maps to component scale and should not be flattened into one universal radius.
- **Shadows:** light cards use restrained warm shadows; dark panels use deeper black shadows. Deep shadows should remain limited to floating previews and cinematic panels.
- **Motion:** most interactive homepage elements use 180ms, 220ms, or 260ms ease transitions. This is a compact motion system; avoid adding long or bouncy motion.
- **Breakpoints:** the project uses Bootstrap-style breakpoints plus homepage-specific cut points at 1365px, 1199px, 1024px, 991px, 767px, 430px, and 390px.

## Colors

Tokens are implemented in `static/css/main.css` and should be used for new homepage-adjacent work. Existing imported theme variables still exist and should not be removed.

| Token | Value | Purpose | Example usage | Contrast / restrictions |
|---|---:|---|---|---|
| `--color-brand-primary` | `#d70006` | Primary LumisPixel red for important CTAs and active accents. | Primary buttons, active tab bar, selected thumbnails. | Use with white text for high-priority actions; avoid as large page background. |
| `--color-brand-primary-hover` | `#c90006` | Hover red for primary actions. | Primary button hover. | Keep text white. |
| `--color-brand-primary-active` | `#b70005` | Active/deeper red and pricing badge text. | Pressed states, emphasized badge text. | Do not use for long body text. |
| `--color-brand-primary-soft` | `#fff1ef` | Pale red surface. | Active tabs and soft selected states. | Pair with dark text, not white text. |
| `--color-brand-primary-tint` | `rgba(215, 0, 6, 0.10)` | Transparent red tint. | Badges, glows, subtle overlays. | Decorative only; do not rely on tint alone for status. |
| `--color-text-primary` | `#181818` | Primary text on light backgrounds. | Headings, card titles, outline button text. | Strong contrast on white/warm surfaces. |
| `--color-text-heading` | `#151515` | Slightly deeper heading color. | Section headings. | Equivalent role to primary text. |
| `--color-text-secondary` | `#4d4a47` | Main supporting copy. | Section descriptions. | Use on light surfaces. |
| `--color-text-muted` | `#5e5a55` | Muted supporting text. | Metadata, helper copy. | Avoid for tiny text below 12px. |
| `--color-text-subtle` | `#6c665f` | Subtle labels. | Preview badges and subdued chip text. | Use sparingly for secondary labels. |
| `--color-text-inverse` | `#ffffff` | Text on dark/red surfaces. | Dark panels, red buttons. | Ensure background is dark enough. |
| `--color-surface-page` | `#ffffff` | Default page/card white. | Cards and secondary CTA surfaces. | Avoid white-on-white without border/shadow. |
| `--color-surface-card` | `#ffffff` | Card surface. | Feature cards and pricing cards. | Pair with border or shadow. |
| `--color-surface-alt` | `#f8f6f3` | Warm alternate section background. | AI features section. | Good behind white cards. |
| `--color-surface-warm` | `#fbf8f5` | Warm preview panel surface. | Preview/product panels. | Pair with warm borders. |
| `--color-surface-soft` | `#f2eee9` | Soft control/index background. | Number chips, neutral badges. | Keep text dark/muted. |
| `--color-surface-dark` | `#101010` | Dark cinematic section surface. | Marketplace/final CTA fallback. | Use inverse text. |
| `--color-surface-dark-card` | `rgba(10, 10, 10, 0.58)` | Glassy dark panel surface. | Final CTA panel. | Requires image/overlay context. |
| `--color-border-light` | `#eee9e4` | Subtle dividers. | Panel headers and card separators. | Do not use as only contrast for interactive controls. |
| `--color-border-medium` | `#ded8d1` | Standard control border. | Tabs and inputs. | Suitable against warm/white surfaces. |
| `--color-border-warm` | `#eaded5` | Warm card border. | Pricing cards. | Pair with white/cream surfaces. |
| `--color-border-inverse` | `rgba(255, 255, 255, 0.14)` | Dark-section borders. | Marketplace cards. | Increase opacity for focus/hover. |
| `--color-focus` | `rgba(215, 0, 6, 0.28)` | Visible focus outline on light surfaces. | `outline: 3px solid var(--color-focus)`. | Use white focus on dark red/black surfaces when red is low contrast. |
| `--color-status-success` | `#1d7f49` | Existing success badge text. | Success status label only. | Do not introduce broader status colors until needed. |

```css
.my-new-card {
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-primary);
}
```

## Typography

The project imports Sora, Playfair Display, and DM Sans. Sora is the dominant brand UI and display face, Playfair Display is the editorial/accent serif, and DM Sans appears in inherited template heading/supporting styles.

| Token | Value | Purpose | Example usage |
|---|---|---|---|
| `--font-display` | `var(--font-family-base)` / Sora | Hero and major display headings. | `.wptb-item--title` |
| `--font-heading` | `var(--font-family-base)` / Sora | Section and card headings. | Pricing card titles. |
| `--font-body` | `var(--font-family-base)` / Sora | Body copy and UI. | Paragraphs, controls. |
| `--font-editorial` | `var(--font-family-two)` / Playfair Display | Intentional editorial/italic emphasis only. | Photography-led pull quotes or elegant emphasis. |
| `--font-supporting` | `var(--font-family-three)` / DM Sans | Inherited supporting/template headings. | Legacy component styles. |

### Type hierarchy

| Role | Family | Size | Line height | Weight | Letter spacing / transform | Responsive behavior |
|---|---|---:|---:|---:|---|---|
| Hero heading | Sora | Existing slider styles; homepage sections use `clamp(54px, 5.2vw, 76px)` for large display. | Tight, about 1.02–1.08. | 600–800 depending inherited rule. | Negative tracking appears on large homepage headings. | Scales down at 767px and 390px. |
| Page heading | Sora | `clamp(42px, 5vw, 72px)` in final CTA; `clamp(40px, 4vw, 64px)` in pricing. | 1.02–1.05. | 700–900. | `-.04em` to `-.05em`. | Use section-specific clamps already present. |
| Section heading | Sora | `clamp(40px, 4vw, 56px)` or section-specific equivalent. | About 1.05–1.12. | 700–900. | Tight negative tracking when display-sized. | Reduce to `clamp(32px, 9vw, 42px)` on mobile where used. |
| Subsection heading | Sora | 22px–34px. | 1.15–1.25. | 700–900. | Normal to slight negative. | Step down by 2–6px on tablet/mobile. |
| Card title | Sora | 17px–22px. | 1.15–1.35. | 700–800. | Normal. | Keep compact on mobile. |
| Body large | Sora | `clamp(16px, 1.35vw, 19px)` or 18px. | 1.6. | 300–400. | Normal. | Clamp where tied to display sections. |
| Body regular | Sora | 15px–16px. | 1.45–1.6. | 300–400. | Normal. | Maintain readability. |
| Body small | Sora | 13px–14px. | 1.35–1.5. | 400–700. | Normal. | Do not go below 13px for important copy. |
| Eyebrow | Sora | 11px–12px. | 1.2. | 800–900. | `.08em`–`.18em`, uppercase. | Keep short. |
| Label | Sora | 12px–13px. | 1.2–1.35. | 700–900. | Uppercase only for preview labels. | Keep at least 12px. |
| Button text | Sora | 13px–14px. | 1–1.1. | 800–900. | Uppercase in some CTA systems. | Buttons should keep at least 46px height. |
| Metadata | Sora | 11px–13px. | 1.35–1.45. | 700–800. | Often uppercase with small tracking. | Avoid muted low-contrast metadata below 12px. |

Use Playfair Display only for intentional editorial contrast. Do not use it for navigation, dense cards, forms, or metadata.

## Spacing

The scale below reflects the homepage’s repeated 4px-derived spacing, card padding, section rhythm, and CTA gaps.

| Token | Value | Purpose | Example usage |
|---|---:|---|---|
| `--space-1` | `4px` | Fine adjustment. | Icon nudge, compact internal offset. |
| `--space-2` | `8px` | Tight inline gaps. | Button icon gap, chip gap. |
| `--space-3` | `12px` | Standard compact gap. | Tabs, badges, panel labels. |
| `--space-4` | `16px` | Paragraph/card internal rhythm. | Description top margin. |
| `--space-5` | `24px` | CTA and card grouping. | Button rows, pricing plan gap. |
| `--space-6` | `32px` | Larger group separation. | Section header to content. |
| `--space-7` | `48px` | Major content separation. | Two-column internal spacing. |
| `--space-8` | `64px` | Compact mobile section padding. | Mobile cinematic sections. |
| `--space-9` | `80px` | Standard section rhythm. | Tablet sections. |
| `--space-10` | `96px` | Desktop section rhythm. | Desktop section padding. |
| `--space-11` | `120px` | Extra-large section rhythm. | Large desktop visual breathing room. |

Guidance:

- Inline spacing: use 8px, 12px, or 14px only when matching existing component rhythm.
- Card padding: use 18px–24px for compact cards; use `clamp(28px, 4vw, 54px)` for cinematic panels.
- Section padding: use the established `clamp(76px, 7vw, 112px)` for standard homepage sections.
- Mobile spacing: reduce to roughly 56px–72px vertical padding and stack CTAs where already established.

## Containers and Layout

| Token | Value | Purpose | Example usage |
|---|---:|---|---|
| `--container-standard` | `1300px` | Standard Bootstrap `.container` width at desktop. | Content sections. |
| `--container-wide` | `1920px` | Maximum full-width container. | Full-bleed media wrappers. |
| `--gutter-desktop` | `15px` | Inherited Bootstrap horizontal gutter. | `.container` padding. |
| `--gutter-tablet` | `15px` | Tablet gutter. | Tablet stacked layouts. |
| `--gutter-mobile` | `15px` | Mobile gutter. | Phone layouts. |
| `--grid-gap` | `24px` | Standard grid gap. | Card grids. |

Layout rules:

- Use `.container` for standard content; it resolves to 1300px on desktop and full width below 992px.
- Use `.container-fluid`/wide wrappers only when the media treatment is intentionally full bleed, such as sliders and cinematic image areas.
- Two-column sections typically use a text/visual split with `clamp()` gaps around 34px–76px and stack at 1199px or 991px depending complexity.
- Stretched carousels may expand the media track while keeping text and controls aligned to the standard container.
- Pricing layouts are centered and collapse from three columns to one column at 991px.

## Buttons

Button styles are rendered through `templates/components/button.html` and section-specific CTA classes. Keep semantic anchors for navigation actions and buttons for in-page controls.

| Type | Background | Text | Border | Height | Padding | Radius | Hover / active | Disabled |
|---|---|---|---|---:|---|---:|---|---|
| Primary | `--color-brand-primary` | white | transparent or red | 52px typical; 46px in pricing cards | 14px–24px horizontal | 12px or pill in inherited buttons | darken to hover/active red, lift up to 2px where existing | Use `aria-disabled="true"`, reduce opacity, no hover lift. |
| Secondary | white or dark-section translucent | dark or white depending surface | light/inverse border | 52px typical | 22px–24px | 12px or pill | increase border contrast and subtle background | Same as primary. |
| Outline | transparent/white-opacity | context-aware | visible border | 46px–52px | 14px–24px | 12px/pill | fill with dark or subtle inverse surface | Same as primary. |
| Text link with arrow | transparent | primary text or white | none | at least 44px hit area | 0–4px plus hit-area padding | none/pill if mobile dark CTA | arrow moves or row lifts where existing | Disable link behavior; do not mimic button if inactive. |

Usage:

- Primary examples: “Start Free”, “Find My Photos”, “Browse All Photographers”. Reserve strong red for high-priority actions.
- Secondary examples: “View Profile”, “Compare Features”.
- Text link examples: “Learn More →”, “Explore AI Tools →”.
- Do not create low-contrast dark-on-dark or light-on-light states.

## Cards

Use card families rather than one universal component.

| Family | Background | Border | Radius | Shadow | Padding | Image treatment | Hover | CTA placement |
|---|---|---|---:|---|---|---|---|---|
| Feature card | White or warm white | Light/warm | 18px–22px | Subtle/card | 18px–24px | Optional icon/preview image | Lift `-3px`, stronger border/shadow | Bottom or inline. |
| Photographer card | White | Light | 22px | Card/hover shadow | 18px+ | Portrait/profile image with object-fit cover | Lift/shadow | Profile CTA within card. |
| Pricing card | `rgba(255,255,255,.86)` or red-tinted featured gradient | `#eaded5`, featured red tint | 20px | `0 14px 34px rgba(48,35,27,.07)` | 20px 18px | Pricing visual separate from cards | Lift `-3px`; border to `#dccbc0` | Full-width bottom CTA. |
| Workflow card | Dark translucent in marketplace/workflow contexts | Inverse border | 18px | Usually none/subtle | 18px | Number chip/icon-led | Lift `-3px` and brighten background | Usually no card CTA. |
| Preview/product panel | White or dark glass | Light/inverse | 26px–30px | Floating/dark floating | 18px–22px or clamp | Product mockup, thumbs, chips | Minimal; panels are display objects | CTA may be simulated but noninteractive if preview. |
| Marketplace/form preview panel | Dark glass gradient | Inverse/dashed inner | 26px | Dark floating | 22px | Field-like blocks, badges | None unless interactive | Full-width simulated button. |

Shared tokens:

- `--radius-xl: 22px`
- `--radius-2xl: 26px`
- `--shadow-card`
- `--shadow-card-hover`
- `--motion-hover-lift: -3px`

Do not create a universal card component with many conditional props. Build small, purpose-led components.

## Images

Approved image categories:

- **Hero/cinematic:** full-slide or full-section imagery with dark overlay; uses background-image or absolutely positioned image with `object-fit: cover`.
- **Landscape feature:** wide images inside rounded cards/panels, usually with 16px–28px radii.
- **Photographer profile:** portrait or square crop, object-fit cover, clear focal point.
- **Product preview:** mock interface panels and thumbnails; may use gradients or object-fit cover.
- **Editorial overlap image:** pricing visual uses overlapping images with 22px–28px radii and warm borders.

Guidance:

- Use `object-fit: cover` for photography previews and `object-position` when a focal point needs adjustment.
- Preserve aspect ratios already present in sections; do not stretch portraits into landscape cards.
- Images may extend beyond the standard container only for hero sliders, full-bleed carousel/media treatments, and cinematic CTA sections.
- Use overlays to protect text legibility on hero and final CTA imagery.
- Add meaningful alt text for content images; use empty alt text for purely decorative layers.
- Use lazy loading for below-the-fold content images unless the image participates in a carousel/plugin that manages loading.

## Badges and Filters

| Pattern | Semantics | Colors | Radius | Size | State guidance |
|---|---|---|---:|---|---|
| Eyebrow labels | Noninteractive text labels. | Red or pale inverse text. | None. | 11px–12px uppercase. | Keep concise; not a status. |
| Feature badges/pills | Noninteractive feature highlights. | Neutral surface or red tint. | 999px. | 11px–13px. | Use as supporting labels only. |
| Category filters | Interactive controls. | Neutral default, dark/red active. | 999px or 15px mobile. | 13px. | Must be buttons/links with active state and focus. |
| Status labels | Noninteractive semantic labels. | Existing success only if needed. | 999px. | 11px–12px uppercase. | Do not convey status by color alone. |
| “Most Popular” pricing badge | Noninteractive pricing emphasis. | Red tint + active red text. | 999px. | 11px uppercase. | Use once per pricing group. |
| Preview labels | Noninteractive UI simulation labels. | Dark-section inverse or neutral. | 999px. | 11px–12px. | Mark decorative labels `aria-hidden` if redundant. |

Do not style interactive filters as passive badges; interactive controls need hover, active, and keyboard focus states.

## Icons

The project currently uses Bootstrap Icons (`bi ...`) and imported template icon/font resources. Prefer Bootstrap Icons for new UI additions unless a template component already uses another icon family.

Guidance:

- Preferred UI icon size: 16px–20px; step-number circles and larger controls may use 24px+ containers.
- Use consistent stroke/visual weight within a component group.
- Button icons should sit 8px–10px from text.
- Metadata icons should use muted text color and align to the text baseline.
- Decorative icons/layers should use `aria-hidden="true"` or empty alt text when rendered as images.
- Semantic icons need visible text or an accessible label; never rely on the icon alone.

## Shadows

| Token | Value | Purpose | Example usage |
|---|---|---|---|
| `--shadow-none` | `none` | Flat elements. | Passive badges. |
| `--shadow-subtle` | `0 10px 24px rgba(26, 20, 16, 0.04)` | Low elevation. | AI tabs. |
| `--shadow-card` | `0 18px 44px rgba(16, 24, 40, 0.10)` | Standard cards. | Photographer/feature cards. |
| `--shadow-card-hover` | `0 24px 58px rgba(16, 24, 40, 0.15)` | Hover elevation. | Interactive card hover. |
| `--shadow-floating` | `0 24px 60px rgba(29, 24, 20, 0.12)` | Product panels. | AI product panel. |
| `--shadow-dark-floating` | `0 24px 62px rgba(0, 0, 0, 0.24)` | Dark glass panels. | Marketplace panel. |

Avoid deep shadows on every card. Use them to indicate important floating previews or interactive hover only.

## Border Radius

| Token | Value | Purpose | Example usage |
|---|---:|---|---|
| `--radius-sm` | `8px` | Small controls. | Text link hit areas, compact chips. |
| `--radius-md` | `12px` | Buttons and control indexes. | CTA buttons, tab indexes. |
| `--radius-lg` | `16px` | Larger controls. | AI tabs, marketplace fields. |
| `--radius-xl` | `22px` | Cards/images. | Pricing cards, image cards. |
| `--radius-2xl` | `26px` | Product panels. | AI/marketplace panels. |
| `--radius-panel` | `30px` | Cinematic panels. | Final CTA panel. |
| `--radius-pill` | `999px` | Pills and badges. | Pricing badge, feature pills. |
| `--radius-circle` | `50%` | Circular controls. | Carousel buttons, step numbers. |

## Forms

No backend form implementation is required for this design-system task. The visual form language is based on marketplace and pricing preview panels.

| Element | Standard |
|---|---|
| Input height | 52px typical; preview fields can be 78px display blocks. |
| Label | 12px–13px Sora, 700–900 weight; uppercase only for preview/metadata fields. |
| Placeholder | Muted warm gray; never lower contrast than `--color-text-subtle` on light surfaces. |
| Border | `1px solid var(--color-border-medium)` on light; inverse border on dark. |
| Focus | `outline: 3px solid var(--color-focus); outline-offset: 3px;` on light; white outline on dark where red is low contrast. |
| Error | Do not invent an error palette yet; define it when real error states are implemented. Include icon/text, not color alone. |
| Helper text | 13px–14px, muted, line-height around 1.45. |
| Textarea | Same border/focus as input, larger min-height, vertical resize when useful. |
| Select | Match input height, border, radius; keep native affordance visible. |
| Checkbox/toggle | At least 44px touch target; visible checked and focus states. |
| Disabled | Reduce opacity and remove hover/lift; keep label readable. |

## Motion

| Token | Value | Purpose | Example usage |
|---|---|---|---|
| `--motion-fast` | `180ms ease` | Small controls. | AI tab border/background transitions. |
| `--motion-default` | `260ms ease` | Default component transitions. | Buttons/cards using homepage aliases. |
| `--motion-card` | `220ms ease` | Card hover lift. | Pricing/marketplace cards. |
| `--motion-slow` | `600ms ease` | Larger staged effects only. | Scroll-entry/plugin animations. |
| `--motion-hover-lift` | `-3px` | Standard card lift amount. | `transform: translateY(var(--motion-hover-lift))`. |

Guidance:

- Button-arrow and card motion should be subtle and fast.
- Image hover scale should be minimal and only when already part of an image card pattern.
- Carousel timing is managed by Swiper/theme scripts; do not change timing as part of token work.
- Respect `prefers-reduced-motion: reduce`; existing homepage sections disable transitions for key interactions.

## Responsive Breakpoints

Actual project/homepage breakpoints:

| Breakpoint | Role | Current behavior |
|---:|---|---|
| `>= 1200px` | Desktop/large desktop | `.container` max-width is 1300px; multi-column layouts display. |
| `1365px` | Desktop/laptop refinement | Pricing and marketplace padding/type tighten. |
| `1199px` | Tablet landscape / small laptop | Complex two-column sections stack or reduce visual width. |
| `1024px` | Tablet/CTA refinement | Final CTA adjusts height and image focal point. |
| `991px` | Bootstrap tablet transition | Container becomes 100%; pricing cards collapse to one column. |
| `767px` | Mobile transition | Section padding reduces; CTAs often stack; images/panels shrink; mobile nav applies through existing partials/theme. |
| `430px` | Large phone refinement | Pricing visuals, marketplace panels, final CTA adjust spacing and image position. |
| `390px` | Small phone refinement | Hero/feature typography and gaps tighten further. |
| `375px` | Small-phone QA width | No unique token, but must be tested to ensure 390px rules still hold. |

Responsive rules:

- Typography should use existing section `clamp()` values where already established.
- Keep horizontal gutters aligned with Bootstrap defaults unless a full-bleed media treatment is intentional.
- Stack dense grids before content becomes cramped; pricing stacks at 991px and feature tab grids at 767px.
- Buttons may wrap on tablet and should stack full-width in mobile cinematic CTAs.
- Preserve carousel slide behavior in Swiper/theme scripts.

## Accessibility

Minimum standards for future work:

- Maintain WCAG-conscious contrast, but do not claim full WCAG compliance unless formally tested.
- Provide visible keyboard focus on all interactive elements.
- Keep touch targets around 44px minimum.
- Use semantic heading order; do not choose heading levels based only on visual size.
- Use links for navigation and buttons for in-page actions/state changes.
- Provide meaningful alt text for content images; empty alt for decorative images.
- Respect reduced-motion preferences.
- Do not convey status only by color; include text/icon semantics.
- Use real labels for form controls.
- Carousel controls need accessible labels, as supported by the reusable component.

## Implementation Guidance

Tokens live in the LumisPixel homepage token block in `static/css/main.css`. The imported template system in `static/css/global.css` remains the underlying theme foundation.

```css
:root {
  --color-brand-primary: #d70006;
  --space-5: 24px;
  --radius-xl: 22px;
  --shadow-card: 0 18px 44px rgba(16, 24, 40, 0.10);
}

.new-feature-card {
  padding: var(--space-5);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
}
```

Rules:

1. Prefer tokens for repeated colors, spacing, radius, shadows, and motion.
2. Preserve section-specific values when they protect a unique composition, such as the final CTA overlay, pricing image overlap, or marketplace glass panel.
3. Do not add a competing CSS framework.
4. Do not replace the inherited theme wholesale.
5. When adding a reusable template component, document it in `docs/design/components.md` and align its classes with this system.

## Do / Avoid

Do:

- Use clear visual hierarchy.
- Use real photography prominently.
- Keep copy concise.
- Reserve strong red for primary actions.
- Use warm off-white backgrounds to separate content blocks.
- Keep card density moderate and readable.

Avoid:

- Generic AI robot imagery.
- Excessive gradients.
- Dense card layouts.
- Too many competing accent colors.
- Oversized text inside navigation or cards.
- One-off shadows, radii, colors, or breakpoints without documenting why.

## Change Process

Future design changes should follow this order:

1. Update this design system first.
2. Update shared CSS tokens and reusable components second.
3. Update section-specific exceptions last.
4. Test desktop and mobile, including 1920px, 1366px, 1024px, 768px, 430px, 390px, and 375px.
5. Verify homepage rendering, static assets, console output, carousel behavior, focus states, and reduced-motion behavior.
6. Avoid one-off visual values unless the exception is documented here.
