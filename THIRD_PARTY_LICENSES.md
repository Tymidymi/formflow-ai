# FormFlow AI — komponenty zewnętrzne i licencje

Stan: 22.11.2026. **Inwentaryzacja zależności bezpośrednich**, nie certyfikat zgodności licencyjnej. Pełne sprawdzenie zależności pośrednich i dystrybucji obrazów jest konieczne przed produkcyjnym wdrożeniem.

| Komponent | Wersja / źródło | Informacja licencyjna |
|---|---|---|
| Caddy (bramka HTTP Basic Auth) | 2.11.9-alpine (oficjalny Docker) | Apache-2.0 |
| Python (obrazy API i workerów) | 3.13.9 | PSF |
| FastAPI | 0.115.12 | MIT (sprawdzić metadane obrazu) |
| Uvicorn | 0.34.3 | BSD-3-Clause |
| Pydantic | 2.11.7 | MIT |
| jsonschema | 4.25.1 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| pypdf | 6.1.3 | BSD-3-Clause |
| pypdfium2 | 5.2.0 | Apache-2.0/BSD-3-Clause + zależności PDFium |
| Pillow | 12.0.0 | HPND/MIT-CMU (zweryfikować z dystrybucją) |
| python-docx | 1.2.0 | MIT |
| openpyxl | 3.1.5 | MIT |
| Docling Slim | 2.151.1 | MIT (plus zależności format-office) |
| Tesseract OCR | pakiet Debian, języki pol/eng | Apache-2.0 |
| React / React DOM | 18.3.1 | MIT |
| JSON Forms | 3.8.0 | MIT |
| esbuild | 0.25.12 | MIT |
| LibreOffice Writer i Calc | pakiet Debian Trixie | **różne licencje, w tym MPL/LGPL** — wymaga oceny zakresu dystrybucji i obowiązków licencyjnych |
| DejaVu Fonts | pakiet Debian | sprawdzić w metadanych pakietu |
| Ollama (opcjonalny overlay) | 0.12.7 | sprawdzić licencję oraz warunki wag modelu |

Prawidłowe wersje pakietów Python są przypięte w plikach `apps/{api,extractor,pdf_engine}/requirements*.txt`; Node w `apps/frontend/package-lock.json`. Obrazy Dockera używają konkretnych tagów, bez `latest`.

## Elementy, których nie wolno przeoczyć

- Komponenty systemowe LibreOffice i transytywne zależności Pythona/Node mogą nakładać dodatkowe obowiązki. Nie stwierdzamy, że zbadano wszystkie licencje lub że dowolna wersja projektu spełnia szczególne zasady konkursu.
- Model Qwen3-VL jest modelem open-weight; licencję konkretnego checkpointu i warunki hostingu trzeba sprawdzić osobno.
- Oryginalny kontrakt JSON COI w `apps/api/app/contracts/coi_form_schema.json` został dostarczony w materiałach zadania. **Przed upublicznieniem repo trzeba potwierdzić prawo do jego redystrybucji.**
- Klucze API, źródłowe formularze testowe oraz wyniki mogące zawierać dane nie są publikowane w Git.

Szczegóły architektury i wdrożenia: [dokumentacja techniczna](docs/TECHNICAL.md).
