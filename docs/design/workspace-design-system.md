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

## Current technical debt

- `photographer_workspace.css` is a large, single-file component layer with many compressed rule blocks and repeated hardcoded colors, radii, shadows, buttons, cards, tables, forms, headers, badges, and empty states.
- The workspace inherits `main.css`, which imports Bootstrap and multiple public-marketing styles/plugins. This increases cascade risk and downloads assets the authenticated shell may not need.
- Several feature areas define local visual systems (notably growth, CRM, gallery, financial, and team screens), and some templates contain inline custom-property values. These should be migrated incrementally rather than changed globally in Phase One.
- Existing components mix square controls and 8–20px card radii, and use several near-identical reds and neutral palettes. Compatibility aliases preserve current rendering while future work converges on the new tokens.
- The workspace has no active theme preference today. The opt-in dark token set preserves a migration path but existing hardcoded component colors require an audit before dark mode can be enabled product-wide.
