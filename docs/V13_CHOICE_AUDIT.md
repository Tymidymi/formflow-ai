# FormFlow AI v1.3.0 — universal choice-control audit hotfix

**Date:** 2026-11-21  
**Goal:** preserve checkbox/radio groups and their attached writable blanks in arbitrary forms, without sample-specific field or topic dictionaries.

## Root cause

The first-pass Qwen inventory can identify a subset of individual checkboxes but omit an entire question's options. The previous visual-table audit only reconstructed repeated multi-row/column tables, not a one-row choice group. Blank-place completeness could also pass when choices were missing or when multiple physical options were counted as one question.

## Implementation

- `apps/api/app/visual_choices.py`: independent visual Qwen choice inventory, one option per visible printed mark, evidence markers, and attached text-blank detection. The geometric estimator locates small square outlines **only as a completeness hint**, never as a source of invented questions.
- If the initial choice inventory is smaller than the independently estimated physical square count, re-check overlapping top/bottom page crops and merge mutually compatible option lists.
- Before focused reconciliation, collapse standalone checkboxes with the same explicit printed group prefix and source evidence; preserve independent checkboxes outside that group.
- Visual inventory merges into the existing form in place. A group with options and two writable companion blanks becomes **one choice question plus two text inputs**, not three standalone checkbox fields plus an added duplicate group.
- Conditional SHOW states for companion inputs use internal per-group references, not ambiguous printed titles. Identical group names on different source pages remain separate.
- `response_slot_count` and quality checks count individual printed options in an answer group rather than just the parent question. An incomplete independent audit is reported rather than silently counted as successful.
- The prompts specifically audit choice marks in both horizontal and vertical arrangements. Source domain vocabulary is never used in production recovery rules.

## Tests

- 85 passing backend tests on 2026-11-21.
- New synthetic tests include equipment registration, delivery options, multiple pages with identical group captions, image-region recovery, and a missing-model-audit failure.
- Independent OpenRouter/Qwen live test: **5 physical choices in 2 groups**, with **2 text details** linked to applicable options. Valid COI JSON, no duplicate input questions, no EMPTY_CHOICES warnings, HTTP 200. This is an unrelated synthetic equipment form, **not** the user's dog application.
- This fixes the demonstrated failure modes; it is **not** evidence that arbitrary documents will convert perfectly.

## Limitations and next work

- The original dog application binary was not supplied in this run; only comparison screenshots were provided. A full binary PDF/JPG replay is still needed.
- Poor image contrast, partially printed boxes, huge tables, and tightly repeated forms on the same page may still need human review.
- The geometric square detector is a heuristic; it triggers reinspection, never generates a field by itself.
- Office conversion still lacks rendered-page visual auditing. Checkboxes that are only graphical in Office may therefore be missed.
- The submission uses OpenRouter, notwithstanding the COI challenge restriction on external API dependencies. See `docs/DECISION_API_SUBMISSION.md`.