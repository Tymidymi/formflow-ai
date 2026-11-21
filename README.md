# FormFlow AI · HackNation 2026 · COI

Prywatny prototyp systemu cyfryzacji urzędowych formularzy. Projekt docelowo użyje **Docling → lokalny Ollama / Qwen2.5-VL → JSON COI** i **JSON Forms** do podglądu. **Etap 1** dostarcza działającą, zabezpieczoną warstwę uploadu i interfejs webowy – jeszcze **nie** generuje JSON COI.

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

This mode sends documents to an external API and is **not suitable for the COI submission**.
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
- `compose.dev.yaml` is **development only**; never publish it as an offline competition runner.
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
in the extraction pipeline. The separate OpenRouter model remains DEV-only.

Enable (with the existing Office worker):

```bash
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml \
  -f compose.pdf.yaml --profile docling --profile pdf up -d --build
```

The local extraction preview `POST /api/v1/forms/extract-preview` does not use
OpenRouter. The UI has a button to inspect the OCR text before consenting to AI.

See [PDF engine](docs/PDF_ENGINE.md) for limits, tests and open gaps.
