# LumisPixel workspace implementation rules

For authenticated workspace work, treat `docs/design/workspace-design-system.md` as the canonical specification.

- Inspect existing `lp-` components and patterns before adding markup, CSS, JavaScript, selectors, or services.
- Reuse templates in `templates/photographer_workspace/components/` and `--lp-*` design tokens; avoid one-off CSS and inline presentation.
- Preserve studio/workspace queryset isolation and server-side permission controls. Presentation must never reveal unauthorized values.
- Use real persisted data. Never ship fabricated production metrics, trends, activity, dates, or placeholder records.
- Implement applicable loading, empty, error, disabled, and permission states.
- Test narrow and wide responsive layouts, keyboard operation, focus visibility, names, landmarks, headings, and reduced motion.
- In completion reports, list changed files and the exact checks/tests run.

Do not weaken broader repository instructions or replace feature-specific conventions in a more deeply nested `AGENTS.md`.
