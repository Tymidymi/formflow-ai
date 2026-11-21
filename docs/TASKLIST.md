# FormFlow AI — aktualna lista zadań

**Data przeglądu:** 2026-11-21, stan VPS `f22ab19` (przed zapisem tej checklisty).  
**Aplikacja:** https://vibe.tail075c6f.ts.net:9466/ — tylko Tailnet.  
**Legenda:** [x] ukończone, [ ] do zrobienia; **P0** = obowiązkowe/krytyczne, **P1** = dodatkowe punkty.  
**Pełny pierwotny plan:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Oznaczenia ukończenia poniżej są weryfikowane względem kodu i działającego API, a nie aspiracyjnego planu.

## Stan obecny

- ✅ FastAPI 0.3.0 na VPS; Docker Compose, nie-root, ograniczony RAM, port tylko `127.0.0.1:18171`; Tailscale Serve na porcie 9466.
- ✅ UI do uploadu, inspekcja pliku i świadoma zgoda na zewnętrzne AI.
- ✅ Lokalny, lekki parser tekstu PDF/DOCX/XLSX; JPG/PNG i skan PDF przez obraz wysłany do modelu.
- ✅ **Development only:** OpenRouter + Qwen3-VL-8B-Instruct. Potwierdzony HTTP 200 na **syntetycznym** DOCX: 5 stron, 15 elementów (w tym sekcje), 0 błędów wstępnej walidacji. To NIE oznacza zgodności z oficjalnym schematem COI.
- ✅ Prototyp `semantic JSON -> tabs/questions/flow`, wstępny walidator strukturalny i testy: **13/13**.
- ⚠️ Pełne `JSON Schema` COI jest dostępne w przekazanych materiałach, ale **nie jest jeszcze wpięte** do działającego walidatora.
- ✅ Prywatne repo GitHub [Tymidymi/formflow-ai](https://github.com/Tymidymi/formflow-ai) utworzone; `main` opublikowany i zgodny z lokalnym Git.
- ❌ Brak Docling, obsługi `.doc`/`.ods` w konwersji, JSON Forms, słowników COI, walidacji reguł i rozwiązania lokalnego LLM dla konkursu.

## Kolejność prac i checklista

### Etap A — Repozytorium + materiały konkursowe · P0
- [x] Repozytorium lokalne, Dockerfile, Compose, `.gitignore`, README, dokumentacja wstępna.
- [x] Materiały konkursowe COI przekazane w rozmowie: referencyjne JSON #1 i #5, schemat, słowniki, formularze #2–4 i #6–9.
- [x] Utworzyć **prywatne** `Tymidymi/formflow-ai` i wykonać `git push -u origin main` (plik .env jest ignorowany).
- [ ] Zintegrować bezpieczny zestaw fixture COI i oficjalny schemat z repo; potwierdzić prawa do publikowania otrzymanych materiałów, w razie potrzeby trzymać prywatnie.
- [ ] Dodać CI (testy + walidacja JSON + podstawowy skan zależności).
- [ ] Uzupełnić `THIRD_PARTY_LICENSES.md` i przypiąć wszystkie wersje zależności.

### Etap B — Eksport JSON COI zgodny z wymaganiami · P0 — NASTĘPNY CHUNK
- [x] Prototyp `SemanticForm -> COI JSON` (`tabs`, `questions`, sekcje `SECTION`, `flow.links`, strona `FINISH`).
- [x] Podstawowa kontrola struktury i linkowania.
- [ ] Wpiąć rzeczywisty `importowanyPlikJsonSchemat.json` do walidatora (`jsonschema`).
- [ ] Zestawić mapowanie pól, `options`, `validation`, `states`, `grid`, `techName`, `questionOrder` z JSON-ami referencyjnymi #1 i #5.
- [ ] Rozwiązać udokumentowane rozbieżności wzorców/standardów (ostrzeżenia vs błędy blokujące).
- [ ] Endpoint konkursowy ma zwracać **bezpośrednio** wynikowy JSON COI, nie otoczkę `{status,form,validation}`; szczegóły diagnostyczne osobno.
- [ ] Automatyczne testy: referencyjne schematy, brakujące pola, błędne typy, błędne linki, niestabilne identyfikatory.
- [ ] Pomiar zgodności pól na **oryginalnych** formularzach COI #3 i #4 (a nie tylko na syntetycznym teście).

### Etap C — Ekstrakcja Docling i pełne wejście · P0
- [x] Podstawowe wydobycie treści z PDF/DOCX/XLSX, obsługa JPG/PNG i obrazów skanowanego PDF w trybie developerskim.
- [ ] Osobna usługa/worker Docling z limitami czasu, pamięci i rozmiaru dokumentu.
- [ ] Zachować tabele, kolejność bloków, strony, współrzędne i źródła pól.
- [ ] Lokalny adapter `.doc` (konwersja) oraz `.ods` — dołączyć audyt licencji i zabezpieczenie przed makrami.
- [ ] OCR i fallback dla obrazów/skanów (w trybie konkursowym bez żadnego zewnętrznego API).
- [ ] Testy wszystkich wymaganych rozszerzeń na materiałach COI.

### Etap D — Model semantyczny i generowanie · P0
- [x] Wstępny prompt Qwen, JSON mode, ustrukturyzowany pośredni wynik.
- [x] Adapter OpenRouter w **oddzielnym** `compose.dev.yaml`, zgoda użytkownika przed przekazaniem dokumentu poza VPS.
- [ ] Modele Pydantic dla `CanonicalForm`, schemat pośredni i walidacja typów.
- [ ] Usunąć halucynowane pola, wykrywać duplikaty, niepewność i pochodzenie z oryginału.
- [ ] Przetwarzanie dokumentów wielostronicowych z łączeniem wyników, retry i limitami.
- [ ] **Wersja konkursowa:** uruchomić lokalny model z otwartymi wagami (Ollama/Qwen lub inny) i przejść test całkowicie bez OpenRouter; potrzebny odpowiedni sprzęt z RAM/VRAM.
- [ ] Testy na niewidzianych wcześniej formularzach.

### Etap E — Reguły i słowniki · P1
- [ ] Zaimportować słowniki i dane inicjalne COI, powiązać je z polami.
- [ ] PESEL, NIP, REGON, e-mail, telefon, daty, długość pól i obowiązkowość.
- [ ] Zależności `states`, dynamiczna widoczność/warunki między sekcjami i stronami.
- [ ] Propozycje nowych słowników; oznaczyć sugestie wymagające akceptacji.
- [ ] Testy walidacji i przepływów na #8 (odpady) i #9 (połączone wnioski sportowe).

### Etap F — Frontend i podgląd JSON Forms · P1
- [x] Statyczny interfejs uploadu i pobierania wygenerowanego JSON.
- [ ] Adapter do **oddzielnych** `JSON Schema + UI Schema` na potrzeby JSON Forms.
- [ ] React + JSON Forms: formularz z wizualizacją, strony/sekcje, walidacje.
- [ ] Widok porównawczy: oryginał / COI JSON / interaktywny formularz.
- [ ] Edycja i akceptacja pól, wskazanie źródła i poziomu pewności.

### Etap G — Jakość, bezpieczeństwo i submission · P0
- [x] Podstawowe ograniczenia uploadu, weryfikacja nazw i formatów, Tailscale-only.
- [x] Testy automatyczne na działającym kodzie: 13/13; syntetyczny smoke test OpenRouter pomyślny.
- [ ] Pełne testy MIME, ZIP-bomb, makr, limitu stron, cleanup, timeoutów, bezpieczeństwa wysyłki.
- [ ] Konfiguracja JWT (wymagania konkursowe) i poprawa semantyki `readyz`: samo wyłączenie API NIE oznacza zgodności konkursowej.
- [ ] Test Docker z czystego klona, test offline, brak wyjściowych zależności SaaS.
- [ ] Benchmark: wszystkie formaty, trafność pól i typów, zgodność COI JSON, czas mediany/p95.
- [ ] Wygenerować komplet JSON-ów dla wszystkich siedmiu formularzy konkursowych (#2–4, #6–9).
- [ ] README, architektura, audyt licencji, prezentacja PDF ≤10 slajdów, film ≤3 minut, dostępne repozytorium, opis projektu.
- [ ] Próba demonstracji na **nowym** formularzu i weryfikacja gotowości submission.

## Najbliższa sekwencja bez zbędnych prac

1. **GitHub:** ✅ Repo utworzone, push zakończony; utrzymywać synchronizację `origin/main`.
2. **P0:** pobrać oficjalny COI JSON Schema do projektu i naprawić exporter tak, by generował poprawny JSON, a nie tylko przechodził nasze uproszczone sprawdzenie.
3. **P0:** test na jednym prawdziwym formularzu COI (np. #3), wykaz brakujących i nadmiarowych pól, poprawki promptu/adaptera.
4. **P0:** Docling i obsługa DOC/ODS; dopiero potem P1 słowniki oraz JSON Forms.
5. **P0:** rozstrzygnąć konkursowy runtime bez zewnętrznego API; OpenRouter pozostaje wyłącznie narzędziem developerskim.

**Definicja sukcesu MVP:** `POST /api/v1/forms/convert` przyjmuje **każdy wymagany format** i zwraca bezpośrednio **JSON zgodny ze schematem COI**, potwierdzony testem na nowych materiałach, działając **bez zewnętrznych API**.
