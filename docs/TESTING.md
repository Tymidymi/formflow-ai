# FormFlow — testowanie i znane ograniczenia

## Automatyczne testy kodu

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api python -m pytest -q -p no:cacheprovider apps/api/tests

npm --prefix apps/frontend ci
npm --prefix apps/frontend test
npm --prefix apps/frontend run build
```

Weryfikacja 22.11.2026 (kandydat v1.4, nowszy interfejs): **testy Python i JavaScript przeszły**, **frontend zbudowany**. To weryfikuje kontrakty, przypadki brzegowe i zgodność kodu; nie jest dowodem dokładnego odwzorowania dowolnego dokumentu źródłowego.

## Test integracyjny

1. `GET /healthz`, `GET /readyz` i `GET /api/v1/capabilities`.
2. `GET /api/v1/demo/convert` — fikcyjny formularz, bez zewnętrznych wywołań.
3. `POST /api/v1/forms/extract-preview` — plik DOCX, kontrola liczby stron i tekstu PDF.
4. `POST /api/v1/forms/convert?mode=diagnostic` — ten sam plik, kontrola `form`, `validation`, `grounding`, `quality`.
5. Porównanie pól, typów, etykiet, opcji i warunków ze źródłem, a nie tylko liczby pól.
6. Edycja w UI, potwierdzenie weryfikacji, pobranie JSON, test `POST /api/v1/forms/validate-json`.
7. Test formatów PDF, skan JPG/PNG, DOC/DOCX oraz XLSX/ODS, w tym dokumentów wielostronicowych. Przetwarzanie nowych formularzy jest częścią demonstracji jury.

Niezależna kontrola `service.docx`: `scripts/evaluate_independent.py`. Powtarzalne serię diagnostyczne: `scripts/validate_forms.py`. Dane wejściowe konkursowe i wynikowe zawierające treść dokumentów **nie** powinny trafić do publicznego GitHub.

## Znane ograniczenia i problemy

- Multimodalne Qwen3-VL potrafi nie rozpoznać pola, zmienić je w blok statyczny albo błędnie zinterpretować wybór przez skreślenie. Przy temperaturze 0 wyniki mogą być różne.
- Drugi modelowy weryfikator został usunięty: w testach potrafił skasować prawidłowo rozpoznane pola. Aktualny pipeline opiera się na jednym przebiegu i kontrolach deterministycznych.
- Tabele, rysunki i układ dokumentów Office mogą nie przetrwać renderowania w 100%; materialna utrata tekstu powoduje błąd 422.
- Warunki `SHOW` wymagają istniejącego pola i opcji. Formalnie poprawny JSON COI nie gwarantuje poprawnej logiki formularza.
- `quality.ok` i `schema_valid` są heurystykami/strukturą. **Nie są** pomiarem accuracy względem ground truth.
- Wersja demonstracyjna nie została sprawdzona z rzeczywistym importerem COI. Dostępność importerów i rzeczywiste API pozostają poza zakresem.
- Port Tailscale jest prywatny; sama aplikacja nie ma wieloużytkownikowego uwierzytelnienia. Wymaga kontroli dostępu na poziomie infrastruktury.
- Lokalny model Ollama może działać na mocniejszym hoście, ale nie ma potwierdzonego wyniku e2e na obecnej maszynie.

## Kryteria gotowości do konkursu

- Kompletny plik README, instrukcja uruchomienia Docker, opis REST API i architektury.
- Działające `/healthz` oraz **faktyczna** analiza jednego kontrolnego dokumentu, nie tylko gotowość.
- Schemat COI przechodzi walidację; wynik jest weryfikowany z oryginałem.
- Frontend pokazuje źródło, podgląd eUsługi, edycję i eksport.
- Materiały konkursowe (PDF prezentacji do 10 slajdów, JSON wynikowe, film do 3 minut i kod) są osobnymi składnikami zgłoszenia; nie stanowią części danych testowych repozytorium.

## Ocena jakości modeli

Przeprowadzono mały benchmark kilku otwartych modeli VLM, także Qwen3-VL-30B/235B, Mistral Small i Nemotron. **Żaden nie wygrał bezbłędnie na wszystkich rzeczywistych formularzach**. Nie zmieniać produkcyjnego modelu bez nowej, niezależnie zweryfikowanej próby. Historyczne pliki przebiegów i dokumenty źródłowe pozostają poza repozytorium.

**Dalsza praca:** zwiększać reprezentatywny zestaw testowy z poprawnymi odpowiedziami (pola, opcje, warunki, strony), nie tworzyć wyjątku w kodzie dla konkretnego formularza.


## Testy nowych funkcji

- `apps/api/tests/test_source_sections.py`: rozdzielenie podpunktów, powtórzone etykiety, brak dzielenia dla niepewnego źródła.
- `apps/frontend/tests/editor.test.mjs`: przeniesienie pola pomiędzy sekcjami, utrzymanie zależności SHOW, identyfikatorów i siatki.
- `apps/frontend/tests/adapter.test.mjs`: sumy kontrolne PESEL/NIP/REGON i format telefonu.
- `apps/api/tests/test_batch_export.py`: ZIP 1–10 poprawnych formularzy, odrzucenie niepoprawnych oraz sanitizacja nazw plików.
- `apps/api/tests/test_api.py`: landing `/projekt/`, linki, dokumentacja lokalna oraz najważniejsze endpointy.

Przetwarzanie wsadowe nie jest gwarancją trafności AI: każdy wygenerowany JSON pozostaje szkicem i wymaga ręcznej kontroli przed eksportem.

## Obsługa błędów odpowiedzi HTTP (PDF i inne formaty)

Interfejs nie zakłada, że każda odpowiedź API zawiera JSON. W razie pustego body,
odpowiedzi HTML od proxy albo przerwanego odczytu wyświetla bezpieczny komunikat
z kodem HTTP i numerem żądania, jeżeli został zwrócony w nagłówku
`X-Request-ID`. Konwersja nie jest automatycznie ponawiana, by uniknąć
podwójnych kosztów modelu AI.

Backend `POST /api/v1/forms/convert` zwraca kontrolowany JSON HTTP 500 z kodem
`CONVERSION_INTERNAL_ERROR` dla nieobsłużonych błędów wykonania, zachowując
dotychczasowe jawne odpowiedzi 422/502/504. Stosowny wyjątek rejestrowany jest
w logu audytowym bez ujawniania treści dokumentów.

Test regresji: `apps/frontend/tests/http.test.mjs` oraz
`test_unexpected_conversion_exception_returns_structured_json` w
`apps/api/tests/test_api.py`.

Rzeczywisty dwustronicowy PDF z zestawu regresyjnego przeszedł pełną analizę
przez Tailscale Serve `9466`: status 200, JSON COI poprawny strukturalnie,
ocena semantyczna `needs_review`. Nie jest to gwarancja dla wszystkich PDF.


## Bezpieczeństwo Caddy — test wdrożeniowy

Konfiguracja jest sprawdzana przez oficjalne CLI Caddy:
`docker run --rm ... caddy:2.11.9-alpine caddy validate --config /etc/caddy/Caddyfile`.

Test przeprowadzony na docelowym VPS: anonimowy GET do `/`,
`/projekt/`, `/documentation/`, `/api/docs`, `/api/openapi.json`,
`/api/v1/demo/convert`, `/static/app.js`, `/static/preview.bundle.js`
oraz `/healthz` otrzymuje HTTP 401 przez prywatne HTTPS Tailscale Serve
9466. Również POST bez hasła jest odrzucany przez Caddy.
`compose.auth.yaml` publikuje tylko kontener gateway na
`127.0.0.1:18171`; API, Office i PDF są niewystawione na hosta.
Backend zachowuje testy blokady POST z `Origin` obcej domeny.

**Ważne:** logowanie jest natywnym HTTP Basic, nie własną sesją cookie.
Przed publikacją publiczną sprawdź całą ścieżkę przez docelowy HTTPS
i ograniczenie ryzyka brute-force. Nie publikuj pliku z hashem bcrypt.


## Przetwarzanie równoległe: 10 plików, 3 aktywne

`apps/frontend/tests/batch.test.mjs` testuje 10 zadań z kontrolowanymi
opóźnieniami: w żadnym momencie nie działa więcej niż 3, kolejne startuje
po zwolnieniu slotu, a błąd jednego zadania nie zatrzymuje dziewięciu innych.
Backend udostępnia spójne `batch_max_files: 10` i
`max_parallel_conversions: 3` w `GET /api/v1/capabilities`;
`CONVERSION_SLOTS` ogranicza rzeczywiste przetwarzanie do 3 instancji.
Wspólny eksport przyjmuje do 10 poprawnych formularzy i do 10 MiB JSON.
Testy backendu obejmują dokładnie 10, odmowę dla 11 i poprawność ZIP.

Limit 3 wynika z dostępnej pamięci demonstracyjnego VPS (RAM dostępny ok.
1,3 GiB, bez SWAP w chwili wdrożenia). Dziesięć OCR + multimodalnych
wywołań AI jednocześnie mogłoby przekroczyć limity RAM lub czas odpowiedzi.
Kolejne dokumenty czekają w przeglądarce, a nie jako wiszące żądania
API. Nie uruchamiano 10 płatnych testów modelu w ramach tego testu kodu.
