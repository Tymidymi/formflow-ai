# FormFlow AI · HackNation 2026 · COI

Prywatny prototyp cyfryzacji urzędowych formularzy: PDF/OCR i Docling → **OpenRouter API / Qwen3-VL** → JSON COI. **Na konkurs dostarczamy wersję z API; nie stawiamy lokalnego LLM.** Ollama to opcjonalna możliwość na przyszłość. **Uwaga: wersja z OpenRouter nie spełnia dosłownego zakazu zależności od zewnętrznych API w zadaniu COI.** Zobacz [decyzję i ryzyko](docs/DECISION_API_SUBMISSION.md).

## Uruchomienie

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:18171/healthz
```

Adres HTTP widoczny tylko na VPS: `http://127.0.0.1:18171`. Przykładowe prywatne udostępnienie przez **Tailscale Serve** (nie Funnel):

```bash
tailscale serve --bg --https=9466 http://127.0.0.1:18171
# W razie potrzeby wyłącz tylko ten nowy port:
tailscale serve --https=9466 off
```

## API

- `GET /healthz` – status API.
- `GET /readyz` – etap gotowości (konwersja nieaktywna).
- `GET /api/v1/capabilities` – lista formatów i aktualnych możliwości.
- `POST /api/v1/forms/inspect` – `multipart/form-data` (`file`) → JSON: rozmiar i MIME, bez trwałego zapisu.
- `POST /api/v1/forms/convert` – zarezerwowany endpoint. W etapie 1 zawsze zwraca `501`.
- `/api/docs` – dokumentacja OpenAPI.

## Testy

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api pytest -q apps/api/tests
```

## Polityka przechowywania danych

Nie zapisujemy wgrywanych dokumentów na dysku aplikacyjnym ani do repozytorium. Framework może korzystać z tymczasowego dysku podczas odczytu multipart; kontener ma wydzielony tmpfs czyszczony wraz z kontenerem. W tym etapie żaden dokument nie jest wysyłany do zewnętrznych usług.

## Aktualny status wdrożenia

- [Raport statusowy](docs/STATUS.md)
- [Plan realizacji — aktualizowany](docs/IMPLEMENTATION_PLAN.md)
- [Raport z pierwszego etapu](docs/STAGE_1_REPORT.md)

## Status / dalszy plan

Zobacz [architekturę](docs/ARCHITECTURE.md). Materiały konkursowe z Discorda są konieczne przed implementacją adaptera eksportującego JSON COI.

## Development AI (OpenRouter)

This mode sends documents to an external API. **The team has chosen to use it in the competition submission.** The resulting dependency is **not compliant with the COI external-API ban**; see [the documented decision](docs/DECISION_API_SUBMISSION.md).
The default compose.yaml does NOT enable external AI. To enable development mode,
put a key and model in the ignored .env file and run:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

Current development features: PDF/DOCX/ODS/XLSX text, JPG/PNG and scanned PDF vision,
semantic extraction with Qwen3-VL, deterministic COI JSON mapping, preliminary structure validation.

Limitations: the official COI JSON Schema is integrated, but it is permissive and does not guarantee importer compatibility. Docling is not integrated; old DOC unsupported for conversion;
real competition dataset benchmarking pending.

## Project status / roadmap

[Aktualna lista zadań](docs/TASKLIST.md) · [Pełny plan](docs/IMPLEMENTATION_PLAN.md) · [Status wdrożenia](docs/STATUS.md)


## COI contract (v0.4)

- Official supplied COI JSON Schema is bundled in `apps/api/app/contracts/coi_form_schema.json` for local validation. Its redistribution rights outside the private challenge repository have not yet been confirmed.
- `POST /api/v1/forms/validate-json` checks the official schema plus supplementary business rules. It returns `schema_valid` separately from `valid`.
- `POST /api/v1/forms/convert` returns **only COI JSON** when successful (requires configured provider). To receive the debug envelope, specify `?mode=diagnostic`.
- `compose.dev.yaml` currently runs OpenRouter and is planned for the API-based contest submission. **This is not an offline or rules-compliant configuration.**
- `POST /api/v1/forms/convert` requires header `X-External-AI-Consent: true` when using OpenRouter.
- IDs are deterministic for identical semantic inputs, basic PESEL/NIP/REGON/email/ZIP_CODE validators are inferred from exact field names.

### Completeness heuristic

Sparse model outputs are flagged needs_review; the raw COI JSON endpoint rejects severely incomplete outputs with HTTP 422. This is a heuristic, not a real-document coverage benchmark.

## v0.5 Docling Office

Office documents DOCX, XLSX and ODS can be processed by a separate Docling-slim 2.151.1 Docker worker. It has no public port, uses an internal Docker network, and has a 384 MiB memory limit. The API falls back to built-in parsers if the worker fails. Enable via compose.docling.yaml and --profile docling. Full PDF layout/OCR and legacy DOC are pending.

See docs/COI_BENCHMARKS.md and docs/EXTRACTION.md for test findings and limitations.


## v0.6 — Offline PDF Layout + Polish OCR

A separate PDF Engine processes text PDFs with pypdf's layout extraction and
scans/images with local PDFium + Tesseract pol+eng. There is **no external API**
in the extraction pipeline. OpenRouter powers development **and is planned for the contest submission**, despite the external-API prohibition.

Enable (with the existing Office worker):

```bash
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml \
  -f compose.pdf.yaml --profile docling --profile pdf up -d --build
```

The local extraction preview `POST /api/v1/forms/extract-preview` does not use
OpenRouter. The UI has a button to inspect the OCR text before consenting to AI.

See [PDF engine](docs/PDF_ENGINE.md) for limits, tests and open gaps.

## v0.7 — Quality Engine / COI conditional states

Source-grounded conditional JSONata SHOW states for the rural hall application.
Known COI dictionaryName support, reference field/type benchmark and an
optional internal Ollama Qwen adapter (mock tested only).

See docs/V07_QUALITY_REPORT.md, docs/LOCAL_QWEN.md (future option) and [API submission decision](docs/DECISION_API_SUBMISSION.md).
OpenRouter is planned for submission, **without claiming compliance with COI rules**. Local Ollama is a future-only option.


## v0.8 — Interactive COI / React JSON Forms

The v0.8 preview has a 3-tab workflow: **Digital Form / Original Document / COI JSON**.
Users can navigate MAIN/FINISH pages, fill fields with basic validation,
trigger dynamic SHOW conditions, and preview/export data. Uploads in the
interactive preview are **filename-only**; no form or attachment is submitted to
a government office.

The free synthetic demo endpoint `GET /api/v1/demo/convert` runs with **no AI API**.
For document conversion, `POST /api/v1/forms/convert?mode=diagnostic` still uses
OpenRouter/Qwen with explicit user consent.

Run the reproducible frontend build before Docker:

```bash
cd apps/frontend
npm ci
npm test
npm run build
cd ../..
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build
```

Frontend versions are pinned in `apps/frontend/package-lock.json` and bundled
for self-hosting (no external CDN). AJV uses dynamic schema compilation, so the
renderer currently needs a restricted CSP exception `'unsafe-eval'`. This is
a security trade-off; isolate it before real deployment.

Tested: 50 backend tests, 7 frontend adapter tests, Chromium desktop/mobile,
synthetic scanned PDF end-to-end with OpenRouter. Original binary COI
#3 and #4 benchmark remains pending.

See [v0.8 interactive documentation](docs/V08_INTERACTIVE.md) and
[API submission decision](docs/DECISION_API_SUBMISSION.md).


## v0.8.1 — COI #1 JPEG / RODO hotfix

Tall scans with stitched form + GDPR appendix are segmented in the local OCR
worker. The model receives only the operative part (OCR text and cropped image),
while the legal notice is preserved as a **read-only** COI `TEXT_BLOCK`.
The exporter rejects zero-input forms and reports corrections.

For the officially supplied COI #1 reference application, a narrow source/title
guard recovers core inputs when OCR misses tiny captions, and removes ungrounded
model-invented address subdivisions. OCR legal copy is visibly marked unverified.

Regression uses **the OCR text of the user's actual JPEG** and a browser replay;
the original binary-image upload on the VPS remains a separate test to repeat.
All generated/user-supplied images and benchmark JSONs remain outside Git.
See [COI #1 JPEG fix](docs/COI1_JPEG_FIX.md).


## v0.9 — COI Definition Editor (official review workspace)

After generating or loading a synthetic demo, click **Edytuj formularz** inside
**PODGLĄD WYGENEROWANEJ E-USŁUGI**. Review and correct question labels, types,
required status, available choices, basic validation rules, and help texts.
Add, remove or reorder fields; rename or add/remove sections. Each change
modifies the actual **COI form JSON**, not only the UI.

Press **Zapisz poprawki** to verify against the official COI JSON Schema and
local COI business rules on our own FastAPI (no OpenRouter call). After validation,
**Pobierz JSON COI** exports the **edited and verified** configuration.

Edits remain **browser-tab local only**, without a database/autosave. Download
the JSON to keep the corrections. Existing SHOW dependencies, technical IDs and
read-only legal text are protected. Undo is available for the current edit session.

See [v0.9 field editor](docs/V09_FIELD_EDITOR.md). Current competition submission
still plans OpenRouter API despite the COI no-external-API requirement.


## v1.0 — Guided, three-step workflow

The default interface deliberately shows **one stage at a time**:

1. **Dodaj dokument** — file upload, local inspection, explicit OpenRouter API consent, one primary conversion button.
2. **Sprawdź i popraw** — digital COI form preview with an optional definition editor; compare it with the original document and continue only after validating the COI JSON.
3. **Pobierz formularz** — summary and the verified COI JSON download.

OCR logs and provider diagnostics are collapsed under **Opcje dla administratora**.
JSON configuration is kept out of the everyday preview tabs. Going back
to the upload stage does not discard the completed form, and manual edits are
retained until the user explicitly replaces the document or closes the tab.
Edits remain in browser memory; **download JSON to preserve them**.

The demo route uses local synthetic data without OpenRouter. Actual document
conversion still requires the user's explicit consent to send it to OpenRouter
and remains contrary to the COI external-API restriction. Backend/frontend
test totals: 58/58 and 16/16. Chromium E2E verified the stages, editing,
validation, download, real synthetic PNG upload and mocked AI response,
blob image preview and responsive layout (390 px).

See [v1.0 guided wizard documentation](docs/V10_GUIDED_WIZARD.md).


## v1.1 — Multi-modal PDF understanding and OCR-grounded review

For PDF uploads the **default** is now OCR/layout text **plus up to 3 rendered
page images** sent to Qwen3-VL through OpenRouter, with explicit consent.
The endpoint supports `?mode=diagnostic&vision=off|on|auto` to reproduce A/B
tests on identical documents. The diagnostic includes actual page/image
coverage, model images sent, and an OCR-grounded evidence report per field.

The review wizard can show fields without an unambiguous OCR-line match and
warn when the visual pass did not cover all PDF pages. OCR text matching is
a conservative *review signal*, **not proof** that a field was visually read.

Informational appendices (INFORMACJE/POUCZENIE/OBJAŚNIENIA), legal-fee notes,
and paper signatures are not input fields. Numbered commitments can be
restored to individual checkbox fields if the model collapses them.

**Limits:** only the first 3 PDF pages are sent visually, OCR-heavy PDFs support
at most 4 OCR pages in the current worker, and Office documents are still
text/layout-only. The initial A/B comparison on reconstructed scanned PDFs
showed mixed model-quality changes, not universal gains. See
[vision benchmark and architecture](docs/V11_MULTIMODAL_QUALITY.md).

OpenRouter API remains contrary to the competition's external-API ban.


## v1.2 — Private persistent conversion diagnostics

Every new attempt receives a random 32-character request ID returned in
`X-Request-ID` and included in the browser error message. A private,
rotating JSONL audit log on the VPS records model, input format/size,
image count, token usage, finish reason, parser error line/column,
completion duration and HTTP outcome — **never OCR text, filenames,
uploaded files, prompt content, secret keys or model response bodies**.

Logs persist in the gitignored folder `data/private/logs` across Docker
container recreations (up to 12 MiB, size-based rotation). Read with:

`docker exec formflow-ai-api-1 sh -c 'tail -n 60 /var/log/formflow/conversions.jsonl'`

Qwen output token limit increased from 4000 to 6500. Truncated responses
(`finish_reason=length`) are distinguishable from syntax errors
(`MODEL_INVALID_JSON`). No automatic additional billable retry.

See [v1.2 conversion diagnostic documentation](docs/V12_CONVERSION_LOGGING.md).


## v1.3 — source-grounded extraction without sample-specific patches

Real user documents now flow through **generic per-page OCR + Qwen Vision**,
followed by **source-derived repeated-row table recognition**, an independent
image table-geometry audit, duplicate-cell reconciliation, and the official
COI JSON exporter. OCR source quotes/page references are available for review.
The new quality gate checks source blank counts and page coverage; a valid COI
JSON alone is not treated as proof of correct digitization.

The previous `form_repair`, `semantic_quality`, `conditional_rules` and
`benchmark_gold` sample-specific modules have been REMOVED from the production
workflow and repository. The synthetic demo is a self-contained fixture, not a
source of inference rules.

Model inference performs independent requests per source page. The system
may call the model again on a page if detected inputs seem incomplete. This
is potentially slower and more costly than previous one-shot generation.

Supported conversion inputs: PDF, JPG/JPEG, PNG, DOCX, XLSX and ODS.
Old `.doc` and other formats still require conversion before upload.
OCR-heavy PDF supports up to 12 pages; longer scans may be rejected.
Office uses Docling text/table extraction, not full-page image rendering.

See [v1.3 general extraction](docs/V13_UNIVERSAL_EXTRACTION.md).
