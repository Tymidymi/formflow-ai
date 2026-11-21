# FormFlow AI v1.0.0 — kreator dla urzędnika, krok po kroku

**Data wdrożenia:** 21 listopada 2026
**Środowisko:** prywatny VPS i Tailscale Serve `https://vibe.tail075c6f.ts.net:9466/`
**Cel UX:** użytkownik nietechniczny widzi jeden cel naraz, a nie formularz AI, narzędzia OCR, diagnostykę, edytor i eksport jednocześnie.

## Nowy proces: dokładnie 3 kroki

### Krok 1 — Dodaj dokument

- Jeden duży, wyraźny obszar wyboru dokumentu (kliknięcie lub przeciągnięcie).
- Obsługiwane PDF, DOCX, XLSX, ODS, JPG, JPEG, PNG. Limit uploadu zależy od backendu (obecnie 15 MB).
- Najpierw weryfikacja pliku; dopiero po pozytywnym sprawdzeniu pojawia się wyraźna informacja „Plik jest gotowy” i zgoda na wysłanie do zewnętrznego AI OpenRouter.
- Jeden główny przycisk: **Przygotuj formularz**.
- W czasie konwersji widoczny jest komunikat „Przygotowujemy formularz…” oraz spinner.
- Opcjonalne **Wypróbuj na przykładzie** działa bez klucza AI / bez wysyłania dokumentu.
- Lokalna diagnostyka OCR i informacja o serwerze są schowane w `<details>` **Opcje dla administratora**, niewymaganym do wykonania zadania.

### Krok 2 — Sprawdź i popraw

- Ekran importu znika; dopiero teraz renderowany jest formularz i edytor COI.
- Pasek postępu informuje: **Krok 2 z 3**.
- Obok formularza widoczne są tylko dwa główne działania:
  - **Popraw pytania** — otwiera edytor definicji COI (etykiety, typy, wymagane, opcje, sekcje).
  - **Wszystko się zgadza — dalej** — weryfikuje strukturę COI na własnym backendzie i przechodzi do kroku 3.
- W trybie edycji użytkownik wybiera pole i **Zapisz poprawki** przed przejściem do kolejnego kroku.
- Dostępne są dwie zakładki: **Przygotowany formularz** i **Oryginalny dokument**. Zakładka JSON COI nie jest pokazywana w głównym procesie.
- Można wrócić do kroku 1 oraz **wrócić do już przygotowanego formularza bez ponownego wywołania Qwen**.
- Reguły SHOW, ochrona klauzul RODO i walidatory COI z v0.9 są zachowane.

### Krok 3 — Pobierz formularz

- Pokazuje nazwę, liczbę pól do wypełnienia i stron.
- Jeden wyróżniony przycisk: **Pobierz gotowy formularz**.
- Przycisk deleguje do aktualnego podglądu React; przed eksportem ponawia lokalną walidację COI. Pobiera `formflow-coi-poprawiony.json` zawierający **wszystkie ręczne korekty**.
- Wyświetla komunikat po pobraniu; wyjaśnia, że zapis pliku **nie jest wysłaniem wniosku do urzędu**.
- Dostępne są **Wróć i popraw formularz** oraz **Utwórz kolejny formularz**.

## Dostępność i ograniczenie bodźców

- Duże przyciski (min. 48–58 px), czytelniejsze teksty i kontrast, jasne etykiety.
- Pasek z trzema etapami wskazuje aktualny krok i już wykonane etapy.
- Późniejsze ekrany są fizycznie ukryte `hidden`; nie wystarczy do nich przewinąć.
- Na starcie zgoda na API, edytor i eksport są schowane do właściwego momentu.
- Błędy są wyświetlane przy aktualnym działaniu; nie ma konieczności przeglądania logów.
- Wersja mobilna 390 px nie ma poziomego przewijania.

## Implementacja

- `apps/api/app/static/index.html` — struktura kreatora, trzy odrębne sekcje.
- `apps/api/app/static/style.css` — style kreatora, responsywność, kontrast.
- `apps/api/app/static/app.js` — zarządzanie przejściami, zgoda i inspekcja pliku, spinner, demo, powrót, końcowy eksport.
- `apps/frontend/preview.jsx` — `wizardMode`, ograniczenie widoków, kontynuacja po walidacji, integracja z `window.FormFlowWizard.showFinal`.
- `apps/api/app/main.py` — poprawka CSP `img-src 'self' data: blob:`, umożliwiająca lokalny podgląd JPG/PNG (wciąż bez zewnętrznych źródeł obrazu).

## Testy

- **58/58** testów backendu w Dockerze. Zmieniono test UI tak, aby wymagał ukrycia kroków 2–3 i zgody przed wyborem pliku.
- **16/16** testów frontendu — adapter, edycje COI, reguły SHOW.
- Przeglądarkowy E2E (Chromium) pokrywa:
  - start tylko z krokiem 1, ukryta zgoda na API, ukryte narzędzia administratora;
  - demonstrację bez wywołania AI oraz przejście do kroku 2;
  - ręczną zmianę nazwy pola, zapis, walidację i przejście do kroku 3;
  - pobranie rzeczywiście poprawionego JSON COI;
  - cofanie etapów i powrót do istniejącego formularza bez regeneracji;
  - przesłanie syntetycznego PNG do rzeczywistego endpointu inspekcji, zgodę na OpenRouter, **symulowaną odpowiedź AI** i przejście do podglądu;
  - podgląd oryginalnego PNG przez przeglądarkowy URL `blob:` po korekcie CSP;
  - ekran 390 px na każdym z 3 kroków bez poziomego przewijania;
  - **0 błędów JavaScript i 0 błędów przeglądarki** po końcowej korekcie CSP.

**Ważne:** żądanie konwersji w powyższym teście UI było **zamockowane**; nie oznacza dodatkowego testu dokładności Qwen na nowym pliku. Test dotyczył interakcji użytkownika i poprawności integracji. Wcześniejsze testy właściwej inferencji Qwen pozostają odrębnym zestawem.

## Nadal do zrobienia

- Testy z udziałem nietechnicznych użytkowników (najlepiej urzędników), w tym nawigacja klawiaturą, czytelność ekranów przy skalowaniu 200% i komunikaty błędów.
- Dalsza edycja warunków i słowników COI, trwały zapis wersji w DB i audyt zatwierdzeń.
- Test importu JSON do rzeczywistego, oficjalnego importera COI.
- **Regulamin:** aktualna wersja API OpenRouter nie spełnia wymogu konkursowego zabraniającego zewnętrznych API; decyzja zespołu i ryzyko bez zmian. Zobacz `docs/DECISION_API_SUBMISSION.md`.
