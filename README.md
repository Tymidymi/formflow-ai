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
