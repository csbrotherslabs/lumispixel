# Canonical LumisPixel Workspace page standard

The Photographer Workspace dashboard is the reference implementation for authenticated product pages. This standard is normative: new pages should compose the shared templates in `templates/photographer_workspace/components/`, use `--lp-*` tokens from `static/css/workspace_design_system.css`, and keep domain rules outside presentation. Compatibility `lpw-` classes preserve existing visuals while pages migrate; they are not an invitation to create new local systems.

## Canonical page anatomy

Use these regions in this order, omitting only those marked optional.

1. **Page container:** one semantic `main` supplied by `base.html`; use `.lp-container` (or `--wide` only for genuinely dense tables).
2. **Contextual page header:** required, with one `h1`, concise context, and optional date/breadcrumb. Use `page_header.html`.
3. **Primary actions:** optional when the page has no creation or completion action. Put at most one primary action first; supporting actions use lower emphasis through `action_group.html`.
4. **Attention area:** optional and exceptional. Show actionable warnings, overdue work, or failures—not routine information. Use `attention_item.html` and link to resolution.
5. **Summary/KPI area:** optional. Use only source-backed, decision-useful metrics; suppress the zero-heavy row for a new workspace.
6. **Main operational content:** required. Put the user's core workflow, list, table, form, or chart first.
7. **Supporting side content:** optional. Use for quick actions, recent activity, help, or secondary status; never place the page's essential task only in the sidebar.
8. **States:** every data region must define applicable loading, empty, error, and permission states. Preserve surrounding context; explain the condition and provide one useful next step.
9. **Responsive behavior:** collapse header actions and main/sidebar grids at tablet width, then use a single column and full-width actions on small screens. Never hide essential values or controls to make a layout fit.
10. **Accessibility:** retain the skip link and landmarks; use one `h1`, ordered headings, labelled controls, semantic dates/progress, visible focus, 44px practical targets, non-color status cues, and reduced-motion support.

## Component contract catalog

All inputs are display values; includes never query models or decide authorization. The caller must scope data to the active studio and omit unauthorized actions/values before rendering.

### Page header — `page_header.html`
- **Purpose/inputs:** identifies context with `title`; supports `greeting`, `description`, `date`, a primary and secondary URL/label/icon, and transitional `visually_hidden_title` when the workspace shell already supplies the single page `h1`.
- **Variants/responsive:** standard or visually quiet dashboard title; actions wrap and stack through `.lp-page-header`/`.lp-header-actions`.
- **States/permissions:** no loading or empty visual; use stable copy while regions load. Omit actions the user cannot perform.
- **Accessibility/usage:** exactly one page `h1`; semantic `time`; concise description. Never use a card title as the page title or add a second `h1`.

### Action group — `action_group.html`
- **Purpose/inputs:** prioritizes `primary_*` and optional `secondary_*` action inputs.
- **Variants/responsive:** one primary plus one secondary; wraps and becomes comfortably tappable on narrow screens.
- **States/permissions:** loading belongs on the shared button when actions submit asynchronously; omit unauthorized actions rather than disabling them and revealing capability.
- **Accessibility/usage:** real links for navigation, buttons for commands; icon-only actions require an accessible label. Never place adjacent primary actions.

### Attention item — `attention_item.html`
- **Purpose/inputs:** links a real warning to resolution using an `item` with `title`, `url`, and `icon`.
- **Variants/responsive:** warning/urgent meaning is conveyed by copy and icon, not color alone; wraps without truncating the resolution.
- **States/permissions:** omit the attention region when empty; while loading use one compact skeleton; show only scoped, permitted alerts.
- **Accessibility/usage:** decorative icons are hidden. Do not use attention styling for announcements or marketing.

### KPI card — `kpi_card.html` (dashboard compatibility: `dashboard_kpi_card.html`)
- **Purpose/inputs:** `label`, `value`, `icon`, optional `change`, `trend`, `comparison`, footer, unavailable and loading values.
- **Variants/responsive:** increase/decrease/neutral and unavailable; responsive card grid. The dashboard compatibility include preserves its reference layout during migration.
- **States/permissions:** skeleton while fetching; suppress the KPI area if metrics would only be unexplained zeros; render “Unavailable” with a reason for a permitted page whose role cannot view the value.
- **Accessibility/usage:** trend includes text plus direction; label every card. Never invent comparison periods or infer revenue from bookings.

### Standard card — `card.html`
- **Purpose/inputs:** groups one coherent unit via `title`, `description`, rendered `body`, header action, footer, loading/empty inputs.
- **Variants/responsive:** standard, elevated, interactive, muted, alert, flush; padding reduces on small screens.
- **States/permissions:** built-in skeleton/empty branches; caller supplies an alert/error or permission state where applicable.
- **Accessibility/usage:** use semantic content and an actual link for interactive cards. Avoid nested cards, fixed empty heights, and card-wrapping every sentence.

### Section header — `section_header.html` (dashboard compatibility: `dashboard_section_header.html`)
- **Purpose/inputs:** introduces a region with `section_id`, `title`, optional description/badge/action/eyebrow.
- **Variants/responsive:** standard tokenized or compatibility command-card header; action stacks below copy on small screens.
- **States/permissions:** header remains stable while content loads; omit unauthorized action only.
- **Accessibility/usage:** its id must match the section's `aria-labelledby`; do not skip heading levels or repeat page actions without need.

### Chart card — `chart_container.html`
- **Purpose/inputs:** answers a stated question with `chart_id`, title, description, body, controls, legend, insight, and loading/empty inputs.
- **Variants/responsive:** flush chart card; controls and headings stack, graphic scales without horizontal page overflow.
- **States/permissions:** required loading, empty and error handling; omit restricted series and explicitly explain hidden data.
- **Accessibility/usage:** accessible title, textual summary/table for unique data, labelled legend/tooltips. Never fabricate trends or chart data better expressed as a number/list.

### Quick-action tile — `quick_action.html` (dashboard compatibility: `dashboard_quick_action.html`)
- **Purpose/inputs:** direct route to a frequent task using URL, icon, title, optional description/metadata and disabled state.
- **Variants/responsive:** link/button and disabled; metadata hides on narrow screens, not the action.
- **States/permissions:** no skeleton normally; hide unavailable permissions, or disable with explanation when discoverability is intentional.
- **Accessibility/usage:** link for navigation; visible focus. Do not use tiles as navigation duplication or give several “primary” emphasis.

### Booking item — `booking_item.html`
- **Purpose/inputs:** schedule row from `item.url/date/client/type/location/status`.
- **Variants/responsive:** shared status badge and compact responsive row.
- **States/permissions:** parent owns skeleton, actionable empty and error states; queryset must already be assignment-scoped.
- **Accessibility/usage:** machine-readable datetime, visible status text. Never expose private client/session data from another studio.

### Gallery queue item — `gallery_queue_item.html`
- **Purpose/inputs:** delivery row from `item.url/name/client/stage`; explicitly identifies unavailable deadline/progress.
- **Variants/responsive:** stage badge and compact row that reflows.
- **States/permissions:** parent owns skeleton/empty/error; only authorized galleries enter the list.
- **Accessibility/usage:** decorative thumbnail icon is hidden; do not synthesize deadlines, thumbnails, or completion percentages.

### Activity item — `activity_item.html`
- **Purpose/inputs:** event `description`, entity, icon/avatar, display timestamp plus ISO datetime, optional status and URL.
- **Variants/responsive:** avatar/icon and linked/unlinked; content reflows while its target remains reachable.
- **States/permissions:** activity skeleton; compact explained empty state; scope every event and omit forbidden destinations.
- **Accessibility/usage:** empty avatar alt, semantic time, labelled destination. Do not manufacture “recent activity” to populate a dashboard.

### Progress indicator — `progress.html`
- **Purpose/inputs:** `label`, numeric `value`, optional maximum/display text/description.
- **Variants/responsive:** determinate only; fills available width.
- **States/permissions:** use a skeleton while unknown and an explanatory unavailable state if no denominator exists; never estimate an allowance.
- **Accessibility/usage:** native `progress` plus visible value. Do not use progress for status steps or omit the numeric meaning.

### Badge — `badge.html`
- **Purpose/inputs:** compact status with `label`, variant, optional dot/icon.
- **Variants/responsive:** neutral, brand, success, warning, danger, info; stays compact but may not clip its text.
- **States/permissions:** no loading state; skeleton belongs to its containing item. Badge text must not reveal unauthorized state.
- **Accessibility/usage:** always visible text; semantic colors only. Never show an unexplained colored dot.

### Empty state — `empty_state.html` (dashboard compatibility: `dashboard_empty_state.html`)
- **Purpose/inputs:** explains `title` and `description`; optional icon, compact mode and one primary/secondary next step.
- **Variants/responsive:** full/compact; actions become full-width on small screens.
- **States/permissions:** empty is not loading/error/permission. Tailor the next step to allowed actions; otherwise explain who can help.
- **Accessibility/usage:** meaningful heading and concise reason. Never use “No data” alone or several competing actions.

### Skeleton loader — `skeleton.html`
- **Purpose/inputs:** geometry placeholder with `variant` (`kpi`, `list`, `activity`, `chart`, `card`).
- **Variants/responsive:** matches final region width; motion stops with reduced-motion.
- **States/permissions:** only for genuine loading, replaced atomically by content/error/empty; never reveal shapes of forbidden fields.
- **Accessibility/usage:** shapes are hidden and one loading label is exposed. Never leave skeletons as decoration.

## Visual governance

- **Color:** brand is for emphasis/action, not every icon or heading. Status colors carry meaning and always have text/icon reinforcement. Neutral surfaces dominate.
- **Cards:** group coherent content, not every fragment. Avoid nesting unless hierarchy requires it, fixed empty heights, and inconsistent padding/radius. Interactive cards require hover and visible focus.
- **Buttons:** one primary per section; no adjacent primaries. Label icon-only controls. Destructive styling must be explicit and consequential actions confirmed where appropriate.
- **Typography:** one page title; consistent section headings; no oversized dashboard headings. Keep support copy concise and combine size, spacing, color and semantics—not weight alone—for hierarchy.
- **Spacing:** use `--lp-space-*`; no arbitrary repair margins. Keep data screens compact but readable with consistent section gaps.
- **Visualization:** every chart answers a business question. Prefer a number/list when clearer, never fabricate a trend, always implement loading/empty/error, and provide accessible legends/tooltips and a text alternative.
- **Motion:** explain interaction/state only; no decorative entrance animations; honor `prefers-reduced-motion`.
- **Empty states:** explain why, give one useful permitted next step, stay compact, and replace unexplained zero-heavy dashboards.

## Migration checklist

- [ ] Page hierarchy follows the canonical anatomy and contains one `h1`.
- [ ] Header uses the shared page header; contextual copy and date/breadcrumb are accurate.
- [ ] Actions are permission-filtered with one clear primary priority.
- [ ] Cards group coherent units, are not unnecessarily nested, and use shared radius/padding.
- [ ] Typography roles and semantic heading order are consistent.
- [ ] Gaps and padding use spacing tokens; arbitrary margins are removed.
- [ ] Forms use shared fields, explicit labels, help/error association, and sensible autocomplete.
- [ ] Tables have captions/headers, responsive overflow or an intentional compact representation, and no lost actions.
- [ ] Search/filter state is labelled, keyboard-operable, reflected in the URL when shareable, and has a clear reset.
- [ ] Empty states explain the reason and offer one permitted next step.
- [ ] Loading state matches final geometry and does not cause major layout shift.
- [ ] Error state preserves user work, explains recovery, and avoids leaking exception details.
- [ ] Permission state neither leaks values nor relies on client-side hiding.
- [ ] Narrow phone, tablet, desktop, zoom, long copy and reduced-motion behavior are checked.
- [ ] Every action is keyboard reachable with logical order and visible focus.
- [ ] Landmarks, names, descriptions, status announcements, headings, dates and progress are screen-reader meaningful.
- [ ] Queries are workspace/assignment scoped and bounded; assets/JavaScript are not duplicated.
- [ ] Metrics, trends, charts and status are derived from real persisted data with honest unknowns.
- [ ] Mock/seed/placeholder production data and inline presentational styles are removed.
