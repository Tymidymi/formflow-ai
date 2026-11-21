# FormFlow AI — stan wdrożenia (21.11.2026)

## Wdrożone na VPS

- [x] FastAPI 0.5.0 i Docker Compose z portem 127.0.0.1:18171
- [x] Prywatny Tailscale Serve: https://vibe.tail075c6f.ts.net:9466/
- [x] Przesyłanie dokumentów, weryfikacja formatu, rozmiaru i nazwy
- [x] Oddzielny dev-only adapter OpenRouter Qwen3-VL-8B-Instruct
- [x] Rzeczywisty test wywołania API, HTTP 200: 5 stron, 15 pól (łącznie z sekcjami), 0 błędów walidacji strukturalnej
- [x] Lekka ekstrakcja tekstu z PDF/DOCX/XLSX; vision dla JPG/PNG i skanowanych PDF (do 2 stron)
- [x] Mapowanie z prostego JSON semantycznego na format tabs/sections/flow COI
- [x] Wymagana jawna zgoda na wysyłkę dokumentu do OpenRouter

## Ograniczenia

- [ ] Docling nie jest jeszcze uruchomiony
- [x] Parser ODS dodany; [ ] stary DOC nadal nieobsługiwany (501)
- [x] Oryginalny JSON Schema COI podłączony; [ ] nadal brak testu importu w systemie docelowym
- [ ] Wersja konkursowa musi działać bez zewnętrznego API; compose.yaml nie zawiera OpenRouter, compose.dev.yaml służy wyłącznie do rozwoju
- [ ] JSON Forms (renderer) nie jest jeszcze podłączony
- [ ] Nie zmierzono jeszcze jakości na prawdziwych formularzach konkursowych
- [x] GitHub: prywatne repo https://github.com/Tymidymi/formflow-ai; origin/main opublikowany

## Komendy operacyjne

```bash
cd /home/tymot/projects/formflow-ai
# Development — używa lokalnego pliku .env, który nie trafia do Git.
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
# Konkurs / offline — bez OpenRouter
docker compose -f compose.yaml -f compose.dev.yaml down
docker compose -f compose.yaml up -d --build
```

## Następny krok

Przenieść pełny schemat COI z materiałów konkursowych, wdrożyć Docling/ODS/DOC,
zbudować renderer i przeprowadzić pomiary jakości JSON na rzeczywistych formularzach.

## Chunk v0.4.0

- Wpięty oficjalny JSON Schema COI, checksum SHA-256, dwuwarstwowa walidacja.
- `/convert` zwraca bezpośrednio JSON COI, `?mode=diagnostic` zachowuje UI.
- Deterministyczne identyfikatory, walidatory pól i lekki parser ODS.
- Nowe testy: 26/26 w obrazie dockerowym.
- Szczegóły: [COI_SCHEMA_INTEGRATION.md](COI_SCHEMA_INTEGRATION.md).

- Dodano quality gate: niepełny wynik AI jest oznaczany jako wymagający weryfikacji; surowy eksport zwraca 422.
- Test na tekście odtworzonym z prawdziwego formularza COI #3: model 8B wykrył tylko podpis, model 30B-A3B wykrył 9 pól. Test nie używał oryginalnego pliku z zachowanym układem strony.

- Szablon CI jest w docs/CI_WORKFLOW_TEMPLATE.yml; plik .github/workflows NIE jest aktywny, bo OAuth nie ma scope workflow.

## Chunk v0.5.0

- Docling-slim Office 2.151.1 w osobnym kontenerze, private Docker network, limit RAM 384 MiB; DOCX/XLSX/ODS przetestowane HTTP 200.
- API używa Docling przez prywatną sieć z fallbackiem do parsera lokalnego.
- End-to-end syntetyczny DOCX z tabelą -> Docling -> Qwen -> JSON COI: HTTP 200, schema_valid=true, quality=true.
- Benchmark na tekstach z oryginalnych PDF COI #3 i #4, przed poprawkami promptu: 11 i 17 pól.
- Długi prompt pogorszył liczby pól (11→5 w COI #3 i 17→12 w COI #4), więc został cofnięty; quality gate rozszerzono o terminy, uczestników i odpowiedzialność.
- 32/32 testy automatyczne.
- Niewykonane: pełny Docling PDF/OCR, starszy DOC, test pełnych oryginalnych plików i lokalny LLM konkursowy.


## Etap v0.6.0 — 21 listopada 2026

- FastAPI v0.6.0, lokalny PDF layout + OCR Tesseract pol+eng w osobnym kontenerze.
- PDF OCR worker offline, prywatna sieć, 384 MiB, brak publicznego portu.
- 5/5 testów workera i 40/40 testów API.
- Syntetyczny skan PDF → lokalny OCR → Qwen3-VL-30B-A3B → JSON COI: HTTP 200, schema_valid=true, quality=true.
- `/api/v1/forms/extract-preview` i przycisk UI: ekstrakcja bez OpenRouter.
- Normalizacja semantyczna: usunięcie podpisu papierowego, odzysk daty, pola podania, rozdzielenie miejscowości i daty, wynajem/użyczenie, poprawa liczby uczestników.
- Oryginalne pliki COI #3/#4 sprawdzone lokalnie pod kątem PDF tekstowego i OCR, ale pełny binarny end-to-end na VPS nadal jest niezrobiony.
- OpenRouter nadal DEV; brak konkursowej inferencji offline. Szczegóły: [PDF_ENGINE.md](PDF_ENGINE.md).
