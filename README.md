# FormFlow AI · HackNation 2026 · COI

Konwersja formularzy PDF, skanów i dokumentów Office do interaktywnego formularza oraz JSON COI.

Gałąź `refactor/source-page-pipeline` zawiera wersję 1.4 przygotowaną po audycie 32 plików. **Trwa walidacja przed zastąpieniem wersji działającej.** Stan testów i blokady: [walidacja](docs/REFACTOR_VALIDATION.md), [audyt 8 źródeł](docs/AUDIT_END_TO_END_2026-11-22.md), [eksperyment jednej analizy](docs/SINGLE_PASS_EXPERIMENT_2026-11-22.md).

> **Do oddania/demo:** [instrukcja MVP, kryteria akceptacji i ryzyka](docs/MVP_RELEASE_CHECKLIST.md). Poprawny JSON COI nie potwierdza automatycznie kompletności pól źródłowych.

## Przepływ danych

Office → normalizacja wydruku XLSX/ODS w kopii → LibreOffice PDF + Docling Slim (źródłowe komórki i tekst) → PDFium (kontrola widoczności) → Tesseract/obrazy stron → Qwen → CanonicalForm → COI JSON.

- DOC, DOCX, XLSX i ODS korzystają z izolowanego renderera LibreOffice oraz Docling Slim 2.151.1, który odczytuje źródłowe komórki i tekst bez lokalnego AI; osobny proces z limitem czasu.
- XLSX i ODS przed wydrukiem mają normalizowane ustawienia dopasowania do szerokości jednej strony, bez przepisywania komórek, formuł, rysunków ani obiektów. Oryginalny plik pozostaje bez zmian, a PDFium kontroluje, czy znaki nie wypadły poza obraz strony. Istotna utrata tekstu DOCX nadal powoduje 422, nie fałszywy sukces.
- Długie obrazy są dzielone na strony przed OCR i analizą wizualną.
- Każda strona ma **jedno wywołanie Qwena**. Typy pól, podpisy, opcje, warunki i zgodność ze źródłem są dalej kontrolowane deterministycznie, bez drugiego przebiegu LLM, który w audycie usuwał poprawne pola. Strony analizowane są współbieżnie z limitem dwóch naraz, przy zachowaniu kolejności.
- Nie ma kaskady retry, zwiększania budżetu odpowiedzi ani odtwarzania pól z list przykładowych formularzy.
- Typy, warunki i informacje stałe mają wspólny kontrakt; regiony odpowiedzi są powiązane ze stronami.
- Limit całej konwersji: 240 sekund. Rozłączenie klienta anuluje zadanie. Jednocześnie przetwarzane są najwyżej dwie konwersje.
- Zgodność schematu COI i ocena wierności źródłu są osobnymi wynikami.

Szczegóły: [architektura](docs/ARCHITECTURE.md).

## Uruchomienie wersji developerskiej

Wymagane: Docker Compose, klucz OpenRouter w ignorowanym `.env` i model obsługujący obrazy oraz structured outputs. Domyślnym modelem jest Qwen3-VL; środowisko testowe ma temperaturę 0. Nie podmieniaj modelu bez świadomej zgody i benchmarku.

```bash
cp .env.example .env
# Uzupełnij OPENROUTER_API_KEY i OPENROUTER_MODEL.
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build
curl -fsS http://127.0.0.1:18171/healthz
```

Nazwa usługi i pliku `docling-office` / `compose.docling.yaml` pozostaje zgodna ze starszą konfiguracją. Worker wykorzystuje Docling Slim bez ciężkich modeli ML oraz LibreOffice. Nie instaluje osobnego silnika OCR.

API jest związane wyłącznie z `127.0.0.1`. Prywatny dostęp może zapewniać Tailscale Serve; konfiguracja nie wystawia go przez Funnel.

## API

| Endpoint | Działanie |
|---|---|
| `GET /healthz`, `GET /readyz` | Stan usługi i konfiguracji |
| `GET /api/v1/capabilities` | Formaty i wersja przepływu |
| `POST /api/v1/forms/inspect` | Walidacja pliku |
| `POST /api/v1/forms/extract-preview` | Lokalny odczyt bez modelu zewnętrznego |
| `POST /api/v1/forms/convert` | Eksport COI; `?mode=diagnostic` dodaje ocenę i pochodzenie pól |
| `POST /api/v1/forms/validate-json` | Schemat i reguły eksportu COI |
| `GET /api/docs` | OpenAPI |

Upload używa `multipart/form-data`, pole `file`. OpenRouter wymaga nagłówka `X-External-AI-Consent: true`.

## Testy

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api python -m pytest -q apps/api/tests
npm --prefix apps/frontend test
npm --prefix apps/frontend run build
```

Powtarzalne konwersje rzeczywistych dokumentów:

```bash
python scripts/validate_forms.py --manifest /path/to/manifest.json \
  --output data/private/validation --external-ai-consent
```

Manifest to lista obiektów `{"path":"/absolute/input.pdf","reference":false}`. Skrypt zapisuje SHA-256, odpowiedzi i podsumowanie. Zatrzymuje kolejkę po błędzie dostępu do dostawcy; nie powtarza płatnych żądań. Statusy i liczby pól nie są pomiarem dokładności OCR. Dla niezależnych syntetycznych dokumentów można wykonać
`python scripts/evaluate_independent.py /tmp/formflow-refactor-validation/independent /path/to/results`.
Nie zaleca się pełnych płatnych serii dopóki małe testy nie wykażą zgodności semantycznej z konkretnym wejściem.

## Dane i ograniczenia

Oryginały i profile Office istnieją tylko tymczasowo; worker czyści katalog po zadaniu. Dokumenty oraz wyniki testów nie trafiają do Git. Zgoda na OpenRouter oznacza wysłanie tekstu i obrazów do usługi zewnętrznej.

Regiony pól są estymowane przez model i sprawdzane pod kątem struktury oraz nakładania. Audyt modelu nie jest dowodem bezbłędnej konwersji; wymagane są porównania ze źródłami, także na dokumentach spoza zestawu dostrajania. Zgodność z docelowym importerem COI wymaga oddzielnego testu.

Wersja korzystająca z OpenRouter nie spełnia konkursowego zakazu zewnętrznych API. Decyzja projektowa: [API submission](docs/DECISION_API_SUBMISSION.md). Zależności: [inwentaryzacja](THIRD_PARTY_LICENSES.md).
