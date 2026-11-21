# Ekstrakcja dokumentów — architektura

## Co działa

- FastAPI 0.4.0: lokalna ekstrakcja PDF przez pypdf, DOCX przez python-docx, XLSX przez openpyxl, ODS przez bezpieczny parser ZIP/XML.
- Obrazy i skanowane PDF: przekazywanie maksymalnie 2 stron jako render JPEG do lokalnie skonfigurowanego silnika multimodalnego (w trybie developerskim jest to OpenRouter). **OCR offline nie jest jeszcze zaimplementowany.**
- Opcjonalny `Docling Office Worker` w osobnym obrazie Docker: `docling-slim==2.151.1`, obsługa DOCX/XLSX/ODS, eksport do Markdown z zachowaniem tabel.
- Router ekstrakcji preferuje izolowany worker, jeżeli `FORMFLOW_DOCLING_URL` jest dokładnie `http://docling-office:8001`; w innym przypadku działa parser lokalny.
- Worker bez publikowanego portu, w sieci `internal: true`, kontener nie-root/read-only, pamięć 384 MiB, limity procesów.
- Jeśli worker jest niedostępny, API odzyskuje funkcjonalność przez lokalny parser, a diagnostyka podaje `local-fallback`.

## Uruchamianie

**Standardowy tryb developerski (bez Docling)**:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

**Opcjonalnie Docling Office (wymaga dodatkowego RAM)**:

```bash
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml --profile docling up -d --build
```

**Zatrzymanie workera Docling**:

```bash
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml --profile docling stop docling-office
```

Nie uruchamiać pełnego Docling PDF/OCR na tym VPS bez sprawdzenia zasobów. Podczas prac było od około 440 do 900 MiB dostępnego RAM-u. Model OCR/layout wymaga znacznie więcej zasobów niż parser Office.

## Pozostało

- [x] Test workera Docling (HTTP 200): DOCX/XLSX/ODS, zachowanie tabeli i end-to-end syntetyczny DOCX przez API.
- [ ] Full-stack konwersja na binarnych formularzach COI (z zachowanym układem).
- [ ] Stary .doc: lokalna konwersja (np. LibreOffice w izolacji), uprzedni audyt licencji.
- [ ] Docling PDF/table/layout w osobnym workerze o odpowiednich zasobach.
- [ ] Offline OCR oraz lokalny Qwen na maszynie z GPU.
- [ ] Sprawdzenie pełnego łańcucha licencji wszystkich zależności, zanim projekt zostanie publiczny.

**VPS:** aktualnie worker Docling Office działa jako oddzielny proces w prywatnej sieci Dockera; ma limit 384 MiB. Ciężki Docling PDF/OCR nie jest uruchamiany.


## v0.6 PDF + OCR

A separate offline worker \`pdf-engine\` (pypdf + pypdfium2 + Tesseract pol+eng)
is added in \`compose.pdf.yaml\`. It runs inside the same isolated internal network
and never publishes a host port. See [PDF_ENGINE.md](PDF_ENGINE.md).
Full Docling PDF with layout models remains out of scope on the current VPS.
