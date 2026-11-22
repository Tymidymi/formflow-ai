# FormFlow AI

**FormFlow** przekształca papierowe i biurowe blankiety urzędowe w konfigurowalne formularze elektroniczne, eksportowane jako JSON zgodny z kontraktem COI. Strona projektu: [FormFlow — HackNation 2026](https://vibe.tail075c6f.ts.net:9466/projekt/) (demo w prywatnej sieci Tailscale). Prototyp przygotowany na HackNation 2026 — wyzwanie **Cyfryzacja Formularzy**.

Praca urzędnika odbywa się w trzech krokach: **Dodaj dokument → Sprawdź i popraw → Pobierz formularz**. Automatyczna analiza dostarcza projekt, a przed eksportem użytkownik porównuje go ze źródłem i może poprawić pytania, opcje oraz typy pól.

## Funkcje

- Import `PDF`, `DOC`, `DOCX`, `ODS`, `XLSX`, `JPG`, `JPEG` i `PNG`; weryfikacja formatu pliku, MIME, nazwy i konfigurowalnego limitu rozmiaru.
- Normalizacja dokumentów Office do stron PDF w izolowanym kontenerze, odczyt struktury komórek przez Docling Slim, ekstrakcja tekstu i OCR przez Tesseract, podgląd obrazów stron.
- Model multimodalny open-weight Qwen3-VL interpretuje strukturę stron; deterministyczny moduł mapuje wynik na format COI.
- Walidacja schematu JSON COI, reguły pól (m.in. PESEL, NIP, REGON, telefon i e-mail), opcje wyboru, warunki wyświetlania, sekcje oraz informacje do odczytu.
- Podgląd wygenerowanego e-formularza, edytor i ręczne potwierdzenie zgodności ze źródłem.
- Wybór do 5 dokumentów, przetwarzanie kolejno przez REST API, przegląd każdego wyniku i wspólny eksport zatwierdzonych JSON-ów do ZIP.
- Rozpoznawanie numerowanych podsekcji źródła (np. 2.1, 2.2, 2.3) z ostrożnym przypisaniem pól; ręczne przenoszenie pól między sekcjami bez zmiany identyfikatorów i zależności.
- Walidacja odpowiedzi w podglądzie: wymagane wartości, formaty, sumy kontrolne PESEL/NIP/REGON, telefon i kod pocztowy.
- Landing projektu: `/projekt/`, link do demonstracji i repo oraz oznaczone miejsca na prezentację i film.
- REST API z dokumentacją OpenAPI, kontenery Docker, testy backendu i frontendu.

**Ważne:** poprawny schemat JSON nie oznacza kompletnej i bezbłędnej konwersji. Użytkownik musi zweryfikować rezultat. Automatyczna interpretacja tabel, podpisów, pól wyboru i warunków bywa niepełna.

## Architektura

```text
Przeglądarka (formularz, weryfikacja, edytor)
        │ HTTPS (Tailscale Serve)
        ▼
Caddy :18171 — HTTP Basic Auth (jedyny opublikowany port)
        │ wewnętrzna sieć Docker
        ▼
FastAPI :8000 — upload, kontrola wejścia, orkiestracja
        ├── Office Worker: LibreOffice + Docling Slim
        ├── PDF Worker: pypdf + PDFium + Tesseract
        └── VLM: Qwen3-VL (OpenRouter w trybie developerskim
                     lub adapter Ollama na odpowiednim sprzęcie)
        ▼
CanonicalForm → builder COI → walidator → JSON + podgląd
```

Komponenty Office/PDF są w prywatnej sieci Dockera, nie publikują portów, a bramka Caddy domyślnie nasłuchuje na `127.0.0.1:18171`.

Szczegóły: [dokumentacja techniczna](docs/TECHNICAL.md), [API](docs/API.md), [wdrożenie](docs/DEPLOYMENT.md), [testowanie i ograniczenia](docs/TESTING.md), [zależności i licencje](THIRD_PARTY_LICENSES.md).

Dokumentacja w aplikacji: `/documentation/` (samodzielna strona HTML, bez CDN). Zmiany w Markdown eksportuje `python scripts/build_docs.py`; CI sprawdza zgodność przez `python scripts/build_docs.py --check`.

## Dostęp dla jury — Caddy Basic Auth

Dostęp do **każdej** strony i metody API (demo, landing, dokumentacja,
OpenAPI, uploady, eksport, zasoby statyczne i `/healthz`) wymaga hasła
HTTP Basic Auth sprawdzanego przez **Caddy**. Przeglądarka wyświetla własne
okno logowania. Nie ma własnego kodu sesji, bazy użytkowników ani formularza
logowania. Hasło jest hashowane przez oficjalne CLI Caddy (`bcrypt`),
a plik `data/private/caddy/jury-users.caddy` (uprawnienia `0600`)
pozostaje **poza Git**.

**Kluczowy warunek:** API FastAPI nie publikuje żadnego portu hosta — dostęp
wyłącznie przez kontener Caddy w `compose.auth.yaml`. Jedyny port hosta
to `127.0.0.1:${FORMFLOW_HOST_PORT:-18171}` na bramce; Tailscale Serve 9466
kieruje ruch właśnie tam. Caddy usuwa nagłówek `Authorization` przed
przekazaniem żądania do API.

Konfiguracja konta (wprowadź hasło bez wyświetlania w terminalu):

```bash
python3 scripts/setup_gateway.py --username jury
# Aby zmienić hasło: python3 scripts/setup_gateway.py --username jury --rotate
```

Zobacz [DEPLOYMENT.md](docs/DEPLOYMENT.md) przed publikacją publicznego HTTPS.
HTTP Basic **nie ma własnego wylogowania ani limitera prób logowania** — hasło
musi być długie i losowe. Korzystaj wyłącznie przez HTTPS.


## Szybki start (Docker, tryb developerski)

Wymagane: Docker + Compose v2, RAM na kontenery i dostęp do modelu skonfigurowany w pliku `.env`.

```bash
cp .env.example .env
# Uzupełnij OPENROUTER_API_KEY w .env (plik jest ignorowany przez Git).
python3 scripts/setup_gateway.py --username jury

docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  --profile docling --profile pdf up -d --build

# Caddy chroni także /healthz (bez hasła otrzymasz 401).
curl -si http://127.0.0.1:18171/ | head -n 12
# Po włączeniu HTTPS: curl --user jury https://HOST/readyz
```

Otwórz aplikację przez prywatne HTTPS/Tailscale Serve; Caddy wymaga HTTP Basic Auth również lokalnie. Nie używaj zwykłego HTTP do przekazywania haseł spoza serwera. **Sam `compose.yaml` nie włącza AI ani workerów.** Plik `compose.dev.yaml` świadomie uruchamia wariant z OpenRouter. Opcjonalna konfiguracja lokalnego modelu znajduje się w `compose.ollama.yaml`, ale wymaga odpowiedniego sprzętu i niezależnej walidacji jakości.

## API — przykład

```bash
# Analiza i diagnostyka, w tym JSON do przeglądu i korekty
# Opcja --user jury spowoduje interaktywną prośbę o hasło.
curl --user jury -sS -X POST \
  -H 'X-External-AI-Consent: true' \
  -F 'file=@wniosek.pdf' \
  'https://HOST/api/v1/forms/convert?mode=diagnostic'

# Podgląd OCR bez wywołania modelu zewnętrznego
curl --user jury -sS -F 'file=@wniosek.pdf' \
  'https://HOST/api/v1/forms/extract-preview'
```

Dokumentacja REST API: `/api/docs`; specyfikacja OpenAPI: `/api/openapi.json`. Domyślny tryb `/api/v1/forms/convert` zwraca sam JSON COI **tylko wtedy, gdy przejdzie walidację strukturalną i automatyczne kontrole jakości**; w przeciwnym razie zwraca `422 COI_REVIEW_REQUIRED`. UI używa trybu diagnostycznego i wymaga ręcznej kontroli także przy pomyślnym wyniku automatycznym.

## Testy

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api python -m pytest -q apps/api/tests

npm --prefix apps/frontend ci
npm --prefix apps/frontend test
npm --prefix apps/frontend run build
```

CI: `.github/workflows/ci.yml`. Testy jednostkowe/integracyjne **nie są** testem pełnej dokładności na dowolnych formularzach. Dodatkowe testy porównawcze: `scripts/evaluate_independent.py`, `scripts/validate_forms.py`.

## Struktura repozytorium

```text
apps/api/       FastAPI, model formularza, konwersja, walidacja, UI statyczne
apps/extractor/ Izolowany renderer Office i struktura Docling Slim
apps/pdf_engine/ PDF, obrazy i OCR
apps/frontend/  React/JSON Forms, edytor, build i testy
compose*.yaml   Profile uruchomieniowe
docs/           Dokumentacja techniczna i instrukcje
scripts/        Narzędzia walidacyjne
```

## Stan i ograniczenia prototypu

- Silnik wykorzystuje jedno wywołanie multimodalnego modelu na fizyczną stronę. Wierność wyników zależy od jakości źródła i odpowiedzi modelu; UI wymaga sprawdzenia dokumentu przed eksportem.
- Model dostępny przez OpenRouter jest skonfigurowany **wyłącznie w developerskim overlayu**. Konfiguracja Ollama istnieje jako wariant offline, bez potwierdzonych testów jakości na tym serwerze.
- Schemat COI jest sprawdzany formalnie, jednak **import w rzeczywistej aplikacji COI nie został potwierdzony**.
- Nie dołączamy prywatnych danych źródłowych, kluczy API ani plików wynikowych z testów do repozytorium.
- Szczegółowe granice i scenariusze awaryjne są opisane w [TESTING.md](docs/TESTING.md).

## Autorstwo i zależności

Projekt wykonany na HackNation 2026. Opis użytych komponentów i kwestii licencyjnych: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Brak deklaracji, że integracja spełnia wymagania produkcyjnej dostępności, bezpieczeństwa lub dokładności bez dalszych testów.
