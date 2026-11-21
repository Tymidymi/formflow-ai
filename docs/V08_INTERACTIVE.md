# FormFlow AI v0.8.0 — interaktywny podgląd eUsług

**Data:** 21.11.2026
**Wdrożenie:** prywatny VPS, Tailscale Serve: https://vibe.tail075c6f.ts.net:9466/
**Tryb generowania:** OpenRouter API / Qwen3-VL, zgodnie z aktualną decyzją zespołu. **Wersja nie spełnia zakazu zależności od zewnętrznych API w regulaminie COI.** Zob. [DECISION_API_SUBMISSION.md](DECISION_API_SUBMISSION.md).

## Co działa

- [x] React 18.3.1 + JSON Forms 3.8.0 (core/react/vanilla), spakowany lokalnie przez esbuild 0.25.12.
- [x] Adapter struktury JSON COI (`tabs`, `questions`, `SECTION`, `repeatingSectionGrid`) na oddzielny **JSON Schema + UI Schema**.
- [x] Strony MAIN/FINISH, sekcje, pola tekstowe, textarea, number, date, RADIO, CHECKBOX, SELECT, FILE_UPLOADER w trybie demonstracyjnym.
- [x] Warunki `SHOW` przetłumaczone z wąskiego, znanego wzorca JSONata COI na deklaratywne reguły JSON Forms — **bez wykonywania dowolnego JSONata**.
- [x] Walidacja `REQUIRED`, PESEL (11 cyfr — format, bez sumy kontrolnej), NIP (10 cyfr), REGON (9/14 cyfr), e-mail i kod pocztowy. Komunikaty po polsku po kliknięciu **Sprawdź pola**.
- [x] Widoki: **Formularz cyfrowy / Oryginał / JSON COI**. Podgląd PDF i obrazu pochodzi z lokalnego URL `blob:`; Office może użyć ekstrakcji lokalnej.
- [x] Pobieranie konfiguracji JSON COI i **wyłącznie demonstracyjnych** odpowiedzi bez wysyłania do urzędu.
- [x] Jawny i bezpłatny endpoint `GET /api/v1/demo/convert` — syntetyczny formularz świetlicy z dynamiczną osobą odpowiedzialną. Nie wywołuje zewnętrznego API.
- [x] Integracja z istniejącą ścieżką `POST /api/v1/forms/convert?mode=diagnostic`; po odpowiedzi modelu podgląd otwiera się automatycznie.

## Istotne ograniczenia

- `FILE_UPLOADER` w podglądzie **nie wysyła plików** — przechowuje nazwę pliku do demonstracji. Nie należy przedstawiać go jako finalnego systemu załączników.
- Obsługujemy tylko rozpoznawalne warunki `SHOW` w formacie COI ze wskazaną odpowiedzią. Pozostałe warunki są ostrzeżeniem, a nie nieweryfikowanym wykonaniem kodu.
- Dane słowników COI/TERYT nie zostały w całości zaimportowane; dla niezaładowanych słowników pojawia się ostrzeżenie.
- Interaktywna eUsługa jest **symulacją** utworzoną z konfiguracji COI, nie oficjalnym importerem ani usługą składania wniosków.
- JSON Forms / Ajv dynamicznie kompiluje walidatory. Polityka CSP strony dopuszcza `'unsafe-eval'` (wyłącznie skrypty self-hosted, nadal bez `'unsafe-inline'`). **To kompromis bezpieczeństwa do wyeliminowania przed wdrożeniem produkcyjnym** — np. przez odizolowanie renderera w sandbox/oddzielnym originie.
- Materiały COI #3 i #4 w oryginalnych binarnych PDF-ach **nie zostały jeszcze uruchomione przez cały pipeline na VPS**; wcześniejsze benchmarki dotyczą zapisanych wyników po wyciągnięciu tekstu.
- Wersja zgłoszeniowa korzysta z OpenRouter — świadomie niezgodna z wymaganiem konkursowym zabraniającym zewnętrznych API.

## Testy

| Kontrola | Wynik |
|---|---|
| Backend API i fixture demonstracyjny | 50/50 w Dockerze |
| Adapter COI → JSON Forms (Node) | 7/7 |
| Chromium: uruchomienie demo i render 3 stron | OK |
| Chromium: wybór „Inna osoba” odsłania 2 pola | OK |
| Chromium: kontrolka załącznika typu file i polskie walidacje | OK |
| Chromium: zakładki oryginał / JSON, brak błędów JS | OK |
| Chromium: responsywność 390 px, bez poziomego overflow | OK |

- [x] **Chromium E2E z syntetycznym skanem PDF:** upload pliku, zgoda na OpenRouter, OCR Tesseract, Qwen3-VL-30B-A3B, JSON COI, automatyczne uruchomienie React i podgląd oryginału. Wynik: 7 pól, 3 strony, schema_valid=true, quality=true, bez błędów JavaScript.
- [x] **Finalny test Chromium:** pliki załączników wykorzystują input type=file, polskie komunikaty walidacji ukazują się dopiero po kliknięciu „Sprawdź pola”.

**Uwaga:** Test Chromium potwierdza działanie wzorca z naszego generatora i symulacji. Nie potwierdza zachowania pełnych, złożonych warunków z oficjalnych JSON-ów COI #1/#5. Test z zeskanowanym PDF wykorzystał plik syntetyczny, **nie** oryginalny formularz konkursowy.

## Architektura frontendu

```
apps/frontend/
  adapter.mjs             # COI JSON -> JSON Schema/UI Schema
  preview.jsx             # React + JSON Forms, trzy widoki, kroki, walidacja
  preview.css             # Style interfejsu
  tests/adapter.test.mjs  # Testy mapowania i warunków
  package.json            # Przypięte wersje
  package-lock.json       # Odtwarzalny build
  build.mjs               # esbuild: bundle do aplikacji FastAPI

apps/api/app/static/
  preview.bundle.js       # Self-hosted, bez CDN
  preview.bundle.css
```

## Uruchomienie i testowanie

```bash
cd /home/tymot/projects/formflow-ai
cd apps/frontend
npm ci
npm test
npm run build

cd ../..
docker compose -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build
```

Na ekranie głównym kliknij **Wypróbuj formularz demonstracyjny** i wybierz **Inna osoba**. Aby przetestować prawdziwy dokument, użyj uploadu, zatwierdź zgodę na wysłanie do OpenRouter i kliknij **Generuj JSON COI przez Qwen**.

## Kolejny etap

1. Pełny E2E na oryginalnych, binarnych formularzach COI #3 i #4, ręczny scoring jakości.
2. Edycja proponowanych pól i warunków przez urzędnika oraz ponowny eksport JSON COI.
3. Słowniki TERYT i zależności z pozostałych formularzy (#8/#9).
4. Materiały submission, testy świeżych formularzy, polityka bezpieczeństwa i audyt licencji.

**Nie planujemy uruchomienia lokalnego LLM na obecny hackathon.**
