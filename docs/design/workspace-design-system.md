# LumisPixel Photographer Workspace design system

This document is the implementation reference for authenticated Photographer Workspace pages. The foundation lives in `static/css/workspace_design_system.css`, is loaded by the workspace base template before legacy component CSS, and deliberately does not change models, routes, permissions, or JavaScript behavior.

## Architecture and consumption

- Use the `--lp-*` custom properties for all new workspace work. They are the public design-system API.
- Existing `--lpw-*` and `--workspace-*` names are compatibility aliases only. Migrate a component to `--lp-*` when it is next edited; do not create more legacy tokens.
- Use `lp-` for system primitives and retain `lpw-` for existing feature components. Put reusable foundations in `workspace_design_system.css`; feature-specific rules remain in `photographer_workspace.css` until that stylesheet can be split by domain.
- Load order is `main.css` (vendor and public-site styles), `workspace_design_system.css` (tokens/primitives), then `photographer_workspace.css` (legacy and feature components). Do not reverse it without a full workspace regression pass.
- Dark colors are opt-in with `data-workspace-theme="dark"`. Never force the user into dark mode from `prefers-color-scheme`; persist an explicit product preference when theme switching is implemented.

## Tokens

### Color

| Role | Token |
| --- | --- |
| Brand / hover / subtle / border | `--lp-color-brand`, `--lp-color-brand-hover`, `--lp-color-brand-subtle`, `--lp-color-brand-border` |
| Secondary accent | `--lp-color-accent` |
| Page / surface / elevated surface | `--lp-color-page`, `--lp-color-surface`, `--lp-color-surface-elevated` |
| Primary / secondary / muted / disabled text | `--lp-color-text`, `--lp-color-text-secondary`, `--lp-color-text-muted`, `--lp-color-text-disabled` |
| Default / strong border | `--lp-color-border`, `--lp-color-border-strong` |
| Status | `--lp-color-success`, `--lp-color-warning`, `--lp-color-danger`, `--lp-color-info` plus each `-subtle` partner |

Brand red is an attention signal: use it for the primary action, active navigation or filter state, links, focus, and small highlights. Do not use it as a large page surface, decorate every icon with it, or add gradients merely to make a section feel branded. Status colors describe status only and always require a text label or icon.

### Typography

The workspace retains DM Sans through `--lp-font-sans`. Roles are `--lp-type-page-title`, `--lp-type-section-title`, `--lp-type-card-title`, `--lp-type-kpi`, `--lp-type-body`, `--lp-type-body-small`, `--lp-type-caption`, `--lp-type-label`, and `--lp-type-micro`. Use `--lp-leading-tight` for headings, `--lp-leading-body` for readable copy, and `--lp-leading-caption` for compact metadata.

Keep one `h1` per page, then use `h2` for sections and `h3` for cards within those sections. Visual size never substitutes for semantic heading order. Body content should normally use body or small-body size; reserve caption and microcopy for short supplementary content, never critical instructions.

### Spacing

The scale is named by its pixel multiple: `--lp-space-1` (4px), `-2` (8px), `-3` (12px), `-4` (16px), `-5` (20px), `-6` (24px), `-8` (32px), `-10` (40px), and `-12` (48px). Compose layouts from this scale. Do not add a one-off margin to repair a component; first correct the parent grid, stack, or component spacing.

### Shape, elevation, and motion

- Radii: `--lp-radius-sm` for compact controls, `--lp-radius-md` for standard controls/cards, `--lp-radius-lg` for large panels, and `--lp-radius-pill` only for pills.
- Shadows: `--lp-shadow-subtle` for separation, `--lp-shadow-standard` for cards, and `--lp-shadow-elevated` for overlays or floating UI. A border plus subtle shadow is the default; never apply elevated shadow to every card.
- Interaction: use `--lp-transition-duration` and `--lp-transition-easing`. Motion must remain optional; the foundation neutralizes nonessential animation under `prefers-reduced-motion`.
- Focus: use `--lp-focus-ring` with a visible outline. Never remove focus styling without supplying an equally visible replacement.

## Layout conventions

- `.lp-container` is the standard readable page wrapper (1280px); add `.lp-container--wide` only for data-heavy tables, timelines, or dense analytics (1480px).
- `.lp-page-header` contains `.lp-page-heading` (`.lp-page-title` and `.lp-page-description`) plus `.lp-header-actions`.
- `.lp-section-header` introduces a content section. `.lp-dashboard-grid` and `.lp-card-grid` provide responsive 12-column grids; `.lp-full-width` spans every column.
- `.lp-content-sidebar` provides a two-column main/sidebar layout and stacks on tablet. All header, card-grid, and two-column primitives stack for small screens.
- Prefer semantic `header`, `main`, `section`, `aside`, `article`, `nav`, and real `button`/`a` elements. Classes supply appearance, not semantics.

## Accessibility baseline

- Every interactive element needs a visible keyboard focus state and a practical target of at least 44px where the control type permits.
- Provide a visible text label or an accessible name for icon-only controls. Decorative icons use `aria-hidden="true"`.
- Do not communicate action, selection, error, or status through color alone. Pair color with text, shape, icon, or state copy.
- Maintain the page’s skip link and logical heading order. Dynamic feedback belongs in an appropriate `aria-live` region; errors use `role="alert"` when immediate announcement is necessary.
- Validate contrast in every supported theme. Muted and disabled colors are not suitable for primary copy.
- Respect reduced motion and do not add auto-playing or essential animation.

## Rules for future work

1. Search for an existing token, primitive, or component before writing CSS.
2. Never place inline presentational styles in templates or invent a near-duplicate card, button, badge, table, form, page header, or empty state.
3. If a pattern repeats on two pages, promote it to a shared `lp-` primitive or a workspace component include; keep business data and URLs in the calling template/view.
4. Use Bootstrap utilities only when they express the tokenized intent without overrides. Bootstrap 5, Bootstrap Icons, and the existing vanilla JavaScript are the supported stack; do not introduce another framework for presentation.
5. Keep feature selectors shallow and component-scoped. Avoid `!important`, element-wide overrides, arbitrary pixels, and styling coupled to backend identifiers.

## Shared components

The reusable includes live in `templates/photographer_workspace/components/`, their token-only presentation lives in `workspace_design_system.css`, and overlay behavior lives in `workspace_components.js`. Includes receive display data from the caller; they contain no dashboard values or business decisions. Django's `{% include ... with ... %}` is the supported composition API. For rich body/legend/menu slots, prepare safe rendered markup in a parent include or use the component classes directly around semantic template markup.

| Component | Include | Supported options |
| --- | --- | --- |
| Button | `button.html` | `primary`, `secondary`, `outline`, `subtle`, `destructive`, `ghost`, and `icon`; `sm`, `md`, `lg`; icons, loading, disabled, full width |
| Card | `card.html` | `standard`, `elevated`, `interactive`, `muted`, `alert`, `flush`; header, action, body, footer, loading, empty |
| KPI | `kpi_card.html` | icon, value, increase/decrease/neutral comparison, sparkline slot, footer, loading, unavailable |
| Badge | `badge.html` | `neutral`, `brand`, `success`, `warning`, `danger`, `info`; dot and icon |
| Empty state | `empty_state.html` | full/compact, icon, explanation, primary and secondary actions |
| Section header | `section_header.html` | title, description, badge, action |
| Quick action | `quick_action.html` | icon, title, supporting copy, shortcut/metadata, disabled state |
| Activity item | `activity_item.html` | icon/avatar, description, entity, semantic time, status, destination; group items beneath a dated heading in the caller |
| Progress | `progress.html` | accessible native progress value, maximum, display value, description |
| Chart | `chart_container.html` | title, description, controls, legend, body, loading, empty, insight |
| Skeleton | `skeleton.html` | `kpi`, `list`, `activity`, `chart`, `card` |
| Dropdown | `dropdown_menu.html` | trigger label/tooltip and menu-items slot; Escape and arrow/Home/End navigation |
| Tooltip | `data-tooltip` attribute | hover and focus activation, viewport-aware placement, automatic accessible description |

### Examples

```django
{% include "photographer_workspace/components/button.html" with variant="primary" label="Create gallery" leading_icon="bi-plus-lg" href=create_url %}
{% include "photographer_workspace/components/kpi_card.html" with label="Outstanding payments" value=outstanding_total icon="bi-receipt" change=payment_change trend="decrease" comparison="from last month" %}
{% include "photographer_workspace/components/badge.html" with label="Processing" variant="info" dot=True %}
{% include "photographer_workspace/components/progress.html" with label="Storage used" value=storage_percent value_text=storage_display %}
{% include "photographer_workspace/components/empty_state.html" with icon="bi-calendar2-plus" title="No bookings yet" description="Create your first booking to reserve time and keep the client informed." primary_url=create_booking_url primary_label="Create booking" %}
```

Activity groups should use a heading and list around the repeated include:

```django
<section aria-labelledby="activity-today"><h3 id="activity-today">Today</h3><ol class="lp-activity-list">
  {% for event in today_events %}{% include "photographer_workspace/components/activity_item.html" with description=event.description entity=event.entity timestamp=event.timestamp datetime=event.iso_time icon=event.icon %}{% endfor %}
</ol></section>
```

Dropdown item markup must use menu semantics and clearly label destructive actions:

```django
<a role="menuitem" href="{{ edit_url }}"><i class="bi bi-pencil" aria-hidden="true"></i>Edit gallery</a>
<button role="menuitem" class="is-destructive" type="submit"><i class="bi bi-trash" aria-hidden="true"></i>Delete gallery</button>
```

### Correct and incorrect usage

- **Do** place one primary button beside supporting outline, subtle, or ghost actions. **Do not** render a row of equally dominant red actions or add gradients.
- **Do** give icon buttons `accessible_label` and a concise tooltip. **Do not** rely on an icon's visual meaning or Bootstrap class name as its label.
- **Do** let cards group a meaningful unit and use flush cards for charts/tables. **Do not** nest each sentence, control, or statistic in another card.
- **Do** pass human-readable status text alongside the semantic badge variant. **Do not** expose a status as an unlabelled colored dot.
- **Do** explain why a collection is empty and offer the most useful next step. **Do not** use “No data” as the complete empty state.
- **Do** use a real `href` for navigation and a `button` for an in-page action. **Do not** attach click behavior to a non-interactive card or disabled link.
- **Do** provide the chart's textual title, useful empty state, and an accessible summary/table when the graphic contains unique information. **Do not** make canvas color the only way to read a series.
- **Do** show skeletons only while content is genuinely pending. **Do not** use them as permanent decoration or announce every skeleton shape.

### Accessibility requirements

- Icon-only buttons require `accessible_label`; their tooltip repeats or clarifies it. Decorative icons remain `aria-hidden`.
- Loading buttons expose `aria-busy`, preserve their dimensions, and include screen-reader loading text. Disabled links use `aria-disabled` and leave the tab order; JavaScript callers must also suppress activation when applicable.
- Status badges always include visible text. Trends include arrow/dash shape plus a value, while progress uses the native `progress` element with a visible numeric value.
- Dropdown triggers expose `aria-haspopup`, `aria-expanded`, and a label. Menus restore focus on Escape, close on outside click, and support arrow, Home, and End keys. Callers give every item `role="menuitem"`.
- Tooltips supplement rather than replace accessible names, appear on both focus and hover, and disappear on blur, pointer exit, scroll, or resize.
- Skeleton shapes are hidden from assistive technology while a single “Loading content” label remains available. Motion is disabled under reduced-motion preferences.

### Dashboard adoption guidance

The next dashboard pass should compose KPI includes in the existing responsive card grid, follow with a restrained quick-action row, then use chart/card containers for analytics and the activity include inside date-grouped lists. Use an actionable empty state wherever a dashboard collection has no records and a skeleton matching the final component while asynchronous content loads. Preserve one dominant page-level primary action; secondary module actions belong in section headers. Do not copy the include markup into the dashboard.

Good incremental migration candidates are the legacy dashboard metric, workspace-card, checklist, and empty-state includes; analytics KPI and insight cards; financial metric and recent-activity partials; gallery status chips and dashboard cards; and the top-bar/profile action menus. Migrate each feature when it is already being changed rather than globally aliasing every historical class.

### Guidance for future Codex work

1. Import these includes before creating a feature-local equivalent, and expand an existing component API only for a repeatable product need.
2. Pass view-provided data through the include; never query, calculate financial values, or encode permissions in a presentation component.
3. Keep new states tokenized and add light/dark semantic token pairs before adding a color. Test mouse, keyboard, narrow viewport, long translated copy, empty, loading, disabled, and error states.
4. When migrating old markup, retain compatibility classes until all callers are verified, then remove them in a dedicated cleanup with visual regression coverage.

## Current technical debt

- `photographer_workspace.css` is a large, single-file component layer with many compressed rule blocks and repeated hardcoded colors, radii, shadows, buttons, cards, tables, forms, headers, badges, and empty states.
- The workspace inherits `main.css`, which imports Bootstrap and multiple public-marketing styles/plugins. This increases cascade risk and downloads assets the authenticated shell may not need.
- Several feature areas define local visual systems (notably growth, CRM, gallery, financial, and team screens), and some templates contain inline custom-property values. These should be migrated incrementally rather than changed globally in Phase One.
- Existing components mix square controls and 8–20px card radii, and use several near-identical reds and neutral palettes. Compatibility aliases preserve current rendering while future work converges on the new tokens.
- The workspace has no active theme preference today. The opt-in dark token set preserves a migration path but existing hardcoded component colors require an audit before dark mode can be enabled product-wide.
