# FormFlow — design system

## Direction
FormFlow is an **operational tool**, not a marketing page. Its interface is inspired by the visual language of [Centralny Ośrodek Informatyki](https://www.coi.gov.pl/): deep navy, confident typography, white working surfaces and restrained expressive magenta/violet accents. It is not an official COI product; do not use COI logos or imply endorsement.

The user performs three tasks: **upload a source document → inspect and correct generated questions → export a validated COI JSON**. The original document and manual verification remain central to user trust.

## Colors
Central source of truth: \`apps/api/app/static/style.css\` (\`:root\`).

| Role | Token | Value |
| --- | --- | --- |
| Deep navigation background | \`--navy-deep\` | \`#06112a\` |
| Primary heading/background | \`--navy\` | \`#091735\` |
| Reading text | \`--ink\` | \`#13264d\` |
| Supporting copy | \`--muted\` | \`#52617c\` |
| Primary action | \`--blue\` | \`#3157e9\` |
| Action hover | \`--blue-hover\` | \`#2444c6\` |
| Distinctive brand detail | \`--pink\` | \`#d84b9e\` |
| Canvas | \`--canvas\` | \`#f5f7fc\` |
| Card | \`--surface\` | \`#ffffff\` |
| Border | \`--border\` | \`#dde4f0\` |

Keep warning and error states semantically distinct (amber/red); do not use blue for dangerous destructive actions.

## Type, spacing and surfaces
- System sans stack; no remote font or tracking dependencies.
- Desktop left rail (~254px), white content header, centered 3-step progress and up to 1020px review workspace.
- Clear page title (34–52px), concise description (14–16px), 14px+ operative controls.
- Consistent 9–14px radius controls; 20px radius main cards; restrained shadows and 1px borders.
- Upload action is fully keyboard operable; focus ring is visible. Headings are programmatically focusable on wizard transitions.
- The <760px view becomes a slim header instead of hiding the product identity.
- Keep reduced-motion support and preserve all underlying API/React editor wiring.

## Source files
- \`apps/api/app/static/index.html\`: semantic wizard and wording.
- \`apps/api/app/static/style.css\`: application layout and tokens.
- \`apps/frontend/preview.css\`: scoped review, form, editor visuals. Built into \`apps/api/app/static/preview.bundle.css\` by \`npm run build\`.
- \`apps/frontend/preview.jsx\`: existing application behavior; redesign does not alter conversion or validation.

## Quality gate
Run frontend build/tests, Impeccable detector, render desktop/mobile and verify stage one, demo/review and export states. If the AI pipeline is unavailable, use the synthetic demo to exercise the review editor.