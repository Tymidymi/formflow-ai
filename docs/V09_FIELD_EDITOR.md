# FormFlow AI v0.9.0 — edytor definicji pól COI

**Data:** 21 listopada 2026
**Stan:** wdrożony na VPS pod prywatnym Tailscale Serve: https://vibe.tail075c6f.ts.net:9466/
**Wersja repozytorium:** `main`.

## Cel

Umożliwić urzędnikowi ręczną korektę błędów AI w istniejącej sekcji **PODGLĄD WYGENEROWANEJ E-USŁUGI**. W przeciwieństwie do wypełniania pól, edycja zmienia **definicję formularza** i końcowy plik **JSON COI**.

## Jak używać

1. Wygeneruj eUsługę z dokumentu przez OpenRouter/Qwen lub użyj **Wypróbuj formularz demonstracyjny**.
2. W sekcji **Podgląd wygenerowanej eUsługi** kliknij **Edytuj formularz**.
3. Wybierz istniejące pole z listy pytań. Panel po prawej stronie pozwoli zmienić etykietę, typ odpowiedzi, obowiązkowość, opcje i podstawową walidację danych.
4. Możesz **dodać pole**, **usunąć pole**, przestawić kolejność strzałkami ↑ ↓, dodać lub usunąć sekcję, zmienić jej nazwę, a także tytuł strony i formularza.
5. Kliknij **Zastosuj zmianę** w panelu pola. Jeśli się pomylisz, użyj **Cofnij ostatnią zmianę**.
6. Kliknij **Zapisz poprawki**. Aplikacja wyśle samą definicję JSON COI do **własnego FastAPI** (lokalne `POST /api/v1/forms/validate-json`) i zweryfikuje ją oficjalnym COI JSON Schema oraz regułami dodatkowymi.
7. Po pozytywnej weryfikacji wróć do **Formularz cyfrowy**, żeby zobaczyć poprawiony układ, lub wybierz **JSON COI**, żeby podejrzeć definicję.
8. Kliknij **Pobierz JSON COI**, żeby zapisać **zmodyfikowaną** wersję do pliku `formflow-coi-poprawiony.json`.

## Zakres edycji

- Nazwa pola; typ: `TEXT_FIELD`, `TEXTAREA`, `NUMBER`, `DATEPICKER`, `RADIO`, `SELECT`, `CHECKBOX`, `FILE_UPLOADER`.
- Pola obowiązkowe (`REQUIRED`) oraz standardowe walidatory `EMAIL`, `PESEL`, `NIP`, `REGON`, `ZIP_CODE` dla odpowiednich pól tekstowych.
- Lista opcji dla pól wyboru (do 20 opcji, maksymalnie 160 znaków każda) i opcjonalna podpowiedź `tooltipMessage`.
- Dodawanie, usuwanie i zmiana kolejności pytań w sekcji; dodawanie i usuwanie sekcji; zmiana tytułu formularza, strony i sekcji.
- Cofnięcie ostatnich 40 zmian w bieżącej sesji edycji.
- Prawdziwa zmiana eksportowanego JSON-a, a nie tylko kosmetyczna zmiana widoku.

## Bezpieczeństwo struktury i istniejących reguł

- Zachowane są oryginalne `id` (UUID), `techName` i `states` pól, gdy zmieniana jest etykieta lub typ — dzięki temu nie zrywamy referencji.
- Nowe pola dostają unikatowe identyfikatory techniczne i UUID. Po dodaniu/usunięciu/przestawieniu aktualizowane są współrzędne `x/y/rows/cols` i `questionOrder`.
- Nie pozwalamy usunąć pola, od którego zależy `SHOW` innego pytania, ani usunąć opcji użytej w takim warunku.
- Zmiana nazwy strony aktualizuje rozpoznawane referencje JSONata `tabs['...' in title]`, a nierozpoznane zależności blokują ryzykowną operację.
- Klauzule RODO w `TEXT_BLOCK` nie są edytowalnymi odpowiedziami. Sekcja z treścią informacyjną jest chroniona przed usunięciem i przed dodawaniem pól wejściowych.
- Nie można edytować `FINISH` ani usunąć ostatniej sekcji na stronie.
- Przed pobraniem pliku powtarzamy walidację COI i blokujemy eksport, jeśli konfiguracja jest nieprawidłowa.
- Przed zastąpieniem ręcznie poprawionego formularza przez nowy upload, demonstrację lub kolejne wywołanie Qwen aplikacja prosi o potwierdzenie.

## Przechowywanie

**Nie ma jeszcze trwałego zapisu w bazie danych**. Zmiany pozostają w stanie React **bieżącej karty przeglądarki** i są sprawdzane przez własne FastAPI. Edycja **nie wywołuje ponownie OpenRouter ani żadnego AI**. Formularz należy pobrać jako JSON COI, inaczej po zamknięciu/odświeżeniu karty poprawki zostaną utracone.

`beforeunload` ostrzega o utracie ręcznie zmienionego formularza. Nie zapisujemy przez edytor zawartości oryginalnego skanu ani odpowiedzi wprowadzanych podczas próbnego wypełniania.

## Testy 21.11.2026

| Test | Wynik |
|---|---|
| Node.js: adapter JSON Forms i operacje edycji | **16/16** |
| Python/FastAPI: backend, struktura COI, routing | **58/58** |
| Chromium desktop: edycja etykiety, dodanie RADIO, opcje wyboru | OK |
| Chromium desktop: cofnięcie i ponowne zastosowanie zmian | OK |
| Walidacja wynikowego COI w API | **valid=true, schema_valid=true** |
| Pobranie i odczyt poprawionego JSON COI | OK; 16 pól, 3 strony |
| Responsywność na ekranie 390 px | OK; bez poziomego przewijania |
| Chromium: COI #1, korekta numeru działki | OK; schema_valid=true |
| Chromium: informacyjna sekcja RODO chroniona | OK; brak przycisku dodania pola |
| JS runtime errors w przeglądarce | 0 |

W testach użyto danych syntetycznych (demo) i odtworzonego schematu COI #1. Nie wysyłano danych urzędników ani danych osobowych do zewnętrznego API.

## Ograniczenia / dalsze prace

- **Edytujemy definicję pól, a nie reguły warunkowe JSONata.** Nie ma graficznego kreatora nowych warunków `SHOW`, zależności między stronami ani słowników TERYT.
- Dodawanie i zmiana nazwy stron MAIN, zaawansowana edycja siatek COI, wielopowtarzalne sekcje, trwała baza wersji i współdzielenie edycji są poza zakresem v0.9.0.
- Nie ma historycznych „wersji zaakceptowanych przez urzędnika” przechowywanych na VPS: tylko wyeksportowany JSON.
- Walidator COI z oficjalnym JSON Schema i regułami lokalnymi **nie potwierdza importowalności przez rzeczywisty, niedostępny importer COI**.
- Zgłoszenie z OpenRouter nadal **nie spełnia regulaminowego zakazu zależności od zewnętrznych API** (decyzja zespołu w `DECISION_API_SUBMISSION.md`); edycja nie zmienia wybranego dostawcy AI.

## Implementacja

```
apps/frontend/
├── editor.mjs                  # Czyste, niemutujące operacje na JSON COI + strażnicy states/ids
├── EditorPanel.jsx             # React UI edycji, lista pól, panel właściwości
├── preview.jsx                 # Integracja, tryb edycji, zapis, eksport, undo
├── preview.css                 # Responsywny layout edytora
└── tests/editor.test.mjs       # 8 testów zachowania edytora; z adapterem 16/16

apps/api/app/main.py            # POST /api/v1/forms/validate-json — bez zmian protokołu
```
