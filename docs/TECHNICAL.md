# FormFlow AI — dokumentacja techniczna

**Wersja:** 1.4.0 · **Data:** 22 listopada 2026 · **Status:** prototyp demonstracyjny HackNation / COI.

## 1. Cel i zakres

Usługa przyjmuje **pojedynczy pusty formularz** z zasobów urzędu i wyprowadza konfigurowalny formularz elektroniczny w formacie JSON COI. Odbiorcą jest urzędnik odpowiedzialny za digitalizację formularzy; narzędzie nie składa wniosków w imieniu obywateli.

Obsługiwane wejścia: `.pdf`, `.doc`, `.docx`, `.ods`, `.xlsx`, `.jpg`, `.jpeg`, `.png`. Wyjścia: obiekt COI JSON (tryb `coi`), obiekt diagnostyczny zawierający `form`, `validation`, `quality`, `grounding`, `inventory` i informacje o zużyciu modelu (tryb `diagnostic`). Frontend zapewnia wizualizację, edycję i ręczną weryfikację.

## 2. Architektura i granice zaufania

```text
                         ┌───────────────────────────────┐
                         │ Przeglądarka: HTML, JS, React │
                         │ Wizard / JSON Forms / editor  │
                         └──────────────┬────────────────┘
                                        │
                  POST multipart/JSON   ▼
                         ┌───────────────────────────────┐
                         │ FastAPI :8000 (loopback 18171)│
                         │ walidacja, timeout, audyt     │
                         └───────┬───────────┬───────────┘
                                 │           │
                       Office    │           │ PDF/scan
                                 ▼           ▼
                         ┌────────────┐ ┌───────────────┐
                         │ LibreOffice│ │ PDFium, pypdf │
                         │ Docling Slim│ │ Tesseract     │
                         │ port 8001  │ │ port 8002     │
                         └──────┬─────┘ └───────┬───────┘
                                └───────┬───────┘
                                        ▼
                              tekst + obraz strony
                                        │
                                        ▼
                             open-weight Qwen3-VL
                       (OpenRouter DEV lub Ollama lokalnie)
                                        │
                                        ▼
                       CanonicalForm / source page inventory
                                        │
                                        ▼
                    builder COI + warunki + walidator JSON
                                        │
                                        ▼
                         ręczny przegląd → eksport
```

Kontenery Office i PDF komunikują się z API w `extractor_private` — wewnętrznej sieci Docker bez publikowanych portów. Pliki Office są renderowane przez procesy z oddzielnymi profilami i limitami. API przyjmuje dane ze świata zewnętrznego jako **niezaufane**. Tekst OCR i dokument nie są instrukcjami dla modelu.

### Odpowiedzialność modułów

| Moduł | Zakres |
|---|---|
| `apps/api/app/main.py` | REST, orkiestracja, consent, limit konwersji, status, błędy |
| `uploads.py`, `settings.py` | Limity plików, MIME, nazwy i rozszerzenia |
| `extraction_router.py` | Normalizacja formatów do stron, kontrola wierności, metadane |
| `apps/extractor/app.py` | Konwersja Office do PDF, izolowany LibreOffice |
| `apps/extractor/{office_structure,xlsx_print,ods_print}.py` | Źródłowa struktura i metadane wydruku |
| `apps/pdf_engine/` | PDF, render stron, OCR Tesseract pol/eng |
| `source_pages.py`, `render_fidelity.py`, `source_fidelity.py` | Spójność stron oraz utrata widocznych danych |
| `ai_provider.py`, `ollama_provider.py` | Multimodalne żądanie i structured output |
| `page_inventory.py`, `source_semantics.py` | Inwentaryzacja pól, opcje, regiony, kontrole źródłowe |
| `canonical_form.py` | Typowany pośredni kontrakt Pydantic |
| `coi_builder.py`, `coi_conditions.py` | Mapowanie na COI, deterministyczne identyfikatory, warunki |
| `coi_validation.py`, `contracts/coi_form_schema.json` | Kontrola schematu i reguł strukturalnych COI |
| `field_grounding.py`, `conversion_audit.py` | Heurystyczne pokrycie OCR i audyt techniczny |
| `apps/frontend/` | JSON Forms, adapter, edytor i testy JS |

## 3. Przepływ przetwarzania

1. **Walidacja pliku.** `validate_filename` sprawdza nazwę (do 250 znaków, zakazane znaki), `detect_mime` sprawdza magic bytes/strukturę Office, a `MAX_UPLOAD_MB` określa limit (domyślnie 15 MB). Pliki ZIP Office mają limity liczby wpisów i rozpakowanego rozmiaru.
2. **Normalizacja.** DOC/DOCX i arkusze są przetwarzane w oddzielnym workerze LibreOffice. XLSX/ODS otrzymują znormalizowane **wyłącznie ustawienia wydruku w kopii**. Docling Slim odczytuje unikatowe komórki źródłowe i tekst, a wynik wizualny jest reprezentowany jako PDF.
3. **Wierność renderowania.** PDFium kontroluje, czy tekst nie wyszedł poza widoczny obszar PDF; dla DOCX dodatkowo sprawdzana jest zgodność tekstu źródłowego. Materialna utrata danych kończy się błędem zamiast cichą konwersją.
4. **Ekstrakcja stron.** PDF Worker korzysta z pypdf, pypdfium2 i Tesseract (polski/angielski); skany mogą wymagać OCR. Obrazy stron i tekst są wiązane numerem fizycznej strony.
5. **Analiza multimodalna.** Na każdą stronę przypada **jedno** żądanie VLM z tekstem, obrazem i kontraktem JSON; typy obejmują TEXT_FIELD, TEXTAREA, NUMBER, DATEPICKER, RADIO, CHECKBOX, SELECT, FILE_UPLOADER i INFO_BLOCK. Bez modelowego drugiego przebiegu lub nieograniczonych retry.
6. **Normalizacja deterministyczna.** Odrębnie analizowane są podpisy (informacja, nie pole tekstowe), teksty informacyjne, zgodność opcji, regiony, warunki oraz odniesienia do oryginału. System **nie** dodaje ręcznie zakodowanych pól konkretnych formularzy.
7. **Kanoniczny model i COI.** Pydantic `CanonicalForm` odrzuca nieprawidłowe struktury. Builder tworzy strony MAIN, sekcje, pola, identyfikatory i FINISH; możliwe stany SHOW są budowane tylko z jawnych odniesień i wartości.
8. **Kontrola wyniku.** Schemat i reguły COI oraz heurystyki wierności źródłu podają niezależne wyniki. Brak automatycznego błędu **nie** stanowi gwarancji poprawności — frontend wymaga od użytkownika przeglądu przed eksportem.

### COI JSON

Eksport ma postać `title`, `tabs` i `flow` z polami `repeatingSectionGrid` w sekcjach MAIN. Ostatnia strona to FINISH. Odwzorowujemy m.in. TEXT_FIELD, DATEPICKER, CHECKBOX, RADIO, NUMBER, SELECT i read-only TEXT_BLOCK. Builder obsługuje słowniki `Kraje`, `TERYT_DOWODOWY`, `TERYT_4G_DOWODOWY` na wskazanych polach. Reguły walidacyjne są dobierane tylko tam, gdzie wynikają z etykiet i typu pytania (np. PESEL, e-mail, numer telefonu).

Wzorcowy kontrakt organizatora przechowywany jest w `apps/api/app/contracts/coi_form_schema.json`; walidator sprawdza również dodatkowe reguły strukturalne. **Nie potwierdzono importu wygenerowanego JSON w rzeczywistym środowisku COI**.

## 4. REST API i scenariusze błędów

Dokumentacja API: `GET /api/docs`, specyfikacja OpenAPI: `GET /api/openapi.json`.

| Endpoint | Funkcja |
|---|---|
| `GET /` | Frontend |
| `GET /healthz` | Liveness |
| `GET /readyz` | Gotowość konfiguracji analizy |
| `GET /api/v1/capabilities` | Format wejścia, limit i model |
| `POST /api/v1/forms/inspect` | Weryfikacja wejścia |
| `POST /api/v1/forms/extract-preview` | Tekst/metadata OCR bez wywołania modelu |
| `POST /api/v1/forms/convert` | JSON COI lub raport diagnostyczny |
| `POST /api/v1/forms/validate-json` | Zgodność JSON COI i ostrzeżenia |
| `GET /api/v1/demo/convert` | Syntetyczna demonstracja offline |

Parametry `convert`: `mode=coi|diagnostic`, `vision=auto|on|off`. Tryb OpenRouter wymaga nagłówka `X-External-AI-Consent: true`. `coi` blokuje surowy eksport, gdy `validation.valid` lub `quality.ok` jest fałszywe, i zwraca HTTP 422; `diagnostic` dostarcza dane do weryfikacji.

Możliwe odpowiedzi: 400 dla niepoprawnego JSON, 403 gdy brak zgody na zewnętrzny model, 413 dla przekroczenia limitu, 415 dla nieobsługiwanej zawartości/formatu, 422 dla błędów jakości lub dokumentu, 502 gdy ekstraktor/model nie zwrócił prawidłowej odpowiedzi, 503 gdy AI/worker niedostępny. Dokładne warianty zależą od etapu.

## 5. Wydajność i ograniczenia

- Deadline całego requestu: **240 s** (włącznie z kolejką i OCR); współbieżność maksymalnie **2 konwersje**.
- Obrazy stron do VLM: jedna analiza per strona; jednoczesna analiza najwyżej dwóch stron.
- Przestrzeń dla uploadu: `MAX_UPLOAD_MB` domyślnie 15; liczba stron i budżety OCR/VLM są ograniczone.
- Docker: API non-root 10001, Office 10002, PDF 10003, read-only filesystem, tmpfs, ograniczenia procesów, sekrety w runtime.
- Model OpenRouter jest zależnością **trybu developerskiego**; `compose.ollama.yaml` umożliwia konfigurację lokalnej inferencji na maszynie z odpowiednim RAM/GPU, ale nie przeszła ona pełnej walidacji e2e.
- Pamięć RAM i opóźnienia zależą od dokumentu, silnika OCR i przepustowości dostawcy modelu.

## 6. Bezpieczeństwo i prywatność

- Nieufne pliki: sprawdzanie MIME i sygnatur, ZIP limits, formaty jawnie dozwolone, limity zadania.
- Office i PDF: procesy non-root, bez publikowanych portów, wewnętrzna sieć oraz tymczasowe dane zamiast trwałego katalogu uploadów.
- API: odpowiednie nagłówki bezpieczeństwa, brak ekspozycji kluczy w frontendzie i brak treści dokumentów w metadanych dziennika zdarzeń.
- Dostęp zdalny: przez prywatny Tailscale Serve, **nie** przez publiczny Funnel.
- Brak warstwy JWT lub kont użytkowników w samym FormFlow: ograniczenie dostępu musi zapewnić środowisko wdrożenia.
- W trybie OpenRouter dokument (tekst i obraz) trafia do usługi zewnętrznej za jawną zgodą użytkownika. Nie używać prawdziwych danych osobowych lub dokumentów poufnych w demonstracji.

## 7. Testy i odbiór

- Python: `PYTHONPATH=apps/api python -m pytest -q apps/api/tests`.
- JS: `npm --prefix apps/frontend test` i `npm --prefix apps/frontend run build`.
- E2E: upload fikcyjnego `service.docx`, porównanie pól i typów ze wzorcem przez `scripts/evaluate_independent.py`; dodatkowe źródła przez `scripts/validate_forms.py`.
- Gotowość do prezentacji wymaga sprawdzenia `/healthz`, `/readyz`, `/api/v1/capabilities`, `/api/v1/demo/convert`, `extract-preview`, konwersji, edycji, walidacji i pobrania wyniku.
- Nie mylić formalnej walidacji schematu z trafnością semantyczną. W testach 22.11.2026 na rzeczywistych formularzach nadal występowały braki pól, wyborów i warunków; nie zakładać skuteczności 100%.

## 8. Uruchomienie i obsługa

Instrukcja wdrożenia (w tym Compose i weryfikacja portów): [DEPLOYMENT.md](DEPLOYMENT.md). API i przykłady żądań: [API.md](API.md). Granice jakości i scenariusze testów: [TESTING.md](TESTING.md). Zależności i licencje: [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
