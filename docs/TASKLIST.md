# FormFlow AI — aktualna lista zadań

**Data przeglądu:** 2026-11-21; stan wdrożenia v0.4.0 (commit w repozytorium).
**Aplikacja:** https://vibe.tail075c6f.ts.net:9466/ — tylko Tailnet.  
**Legenda:** [x] ukończone, [ ] do zrobienia; **P0** = obowiązkowe/krytyczne, **P1** = dodatkowe punkty.  
**Pełny pierwotny plan:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Oznaczenia ukończenia poniżej są weryfikowane względem kodu i działającego API, a nie aspiracyjnego planu.

## Stan obecny

- ✅ FastAPI 0.4.0 na VPS; Docker Compose, nie-root, ograniczony RAM, port tylko `127.0.0.1:18171`; Tailscale Serve na porcie 9466.
- ✅ UI do uploadu, inspekcja pliku i świadoma zgoda na zewnętrzne AI.
- ✅ Lokalny, lekki parser tekstu PDF/DOCX/ODS/XLSX; JPG/PNG i skan PDF przez obraz wysłany do modelu.
- ✅ **Development only:** OpenRouter + Qwen3-VL-8B-Instruct. Potwierdzony HTTP 200 na **syntetycznym** DOCX: 5 stron, 15 elementów (w tym sekcje), 0 błędów wstępnej walidacji. Pierwotny test poprzedzał włączenie oficjalnego schematu COI.
- ✅ Prototyp `semantic JSON -> tabs/questions/flow`, UUID5, walidacja strukturalna i oficjalny JSON Schema COI; testy: **29/29**.
- ✅ Oryginalny `JSON Schema` COI podłączony bez zmian bajtów; uwaga: schemat jest liberalny i nie zastępuje testu importera.
- ✅ Prywatne repo GitHub [Tymidymi/formflow-ai](https://github.com/Tymidymi/formflow-ai) utworzone; `main` opublikowany i zgodny z lokalnym Git.
- ❌ Brak Docling i obsługi starego `.doc` w konwersji, JSON Forms, słowników COI, walidacji reguł i rozwiązania lokalnego LLM dla konkursu.

## Kolejność prac i checklista

### Etap A — Repozytorium + materiały konkursowe · P0
- [x] Repozytorium lokalne, Dockerfile, Compose, `.gitignore`, README, dokumentacja wstępna.
- [x] Materiały konkursowe COI przekazane w rozmowie: referencyjne JSON #1 i #5, schemat, słowniki, formularze #2–4 i #6–9.
- [x] Utworzyć **prywatne** `Tymidymi/formflow-ai` i wykonać `git push -u origin main` (plik .env jest ignorowany).
- [x] Wpiąć oryginalny JSON Schema COI (prywatne repo); [ ] dodać autoryzowane referencyjne fixture i potwierdzić prawa do publikacji.
- [ ] Włączyć GitHub Actions CI: szablon w docs/CI_WORKFLOW_TEMPLATE.yml; zapis workflow przez OAuth wymaga uprawnienia workflow.
- [ ] Uzupełnić `THIRD_PARTY_LICENSES.md` i przypiąć wszystkie wersje zależności.

### Etap B — Eksport JSON COI zgodny z wymaganiami · P0 — W TRAKCIE
- [x] Prototyp `SemanticForm -> COI JSON` (`tabs`, `questions`, sekcje `SECTION`, `flow.links`, strona `FINISH`).
- [x] Podstawowa kontrola struktury i linkowania.
- [x] Wpiąć rzeczywisty COI JSON Schema (Draft 2020-12) do walidatora (`jsonschema`).
- [ ] Zestawić mapowanie pól, `options`, `validation`, `states`, `grid`, `techName`, `questionOrder` z JSON-ami referencyjnymi #1 i #5.
- [x] Ująć udokumentowane rozbieżności jako ostrzeżenia (np. FINISH SECTION, linki bez UUID); [ ] sprawdzić pełny importer COI.
- [x] Endpoint `/convert` zwraca bezpośrednio JSON COI, a `?mode=diagnostic` podaje metryki dla UI.
- [x] Testy: oryginalny schemat po sumie SHA, brakujące pola, błędny typ, przepływ, stabilne UUID; [ ] porównanie semantyczne obu rzeczywistych referencji #1/#5.
- [ ] Pomiar zgodności pól na **oryginalnych** formularzach COI #3 i #4 (a nie tylko na syntetycznym teście).

### Etap C — Ekstrakcja Docling i pełne wejście · P0
- [x] Podstawowe wydobycie treści z PDF/DOCX/XLSX, obsługa JPG/PNG i obrazów skanowanego PDF w trybie developerskim.
- [ ] Osobna usługa/worker Docling z limitami czasu, pamięci i rozmiaru dokumentu.
- [ ] Zachować tabele, kolejność bloków, strony, współrzędne i źródła pól.
- [x] Lekki parser `.ods` bez dodatkowych zależności, testy XML; [ ] adapter starego `.doc` i audyt konwersji.
- [ ] OCR i fallback dla obrazów/skanów (w trybie konkursowym bez żadnego zewnętrznego API).
- [ ] Testy wszystkich wymaganych rozszerzeń na materiałach COI.

### Etap D — Model semantyczny i generowanie · P0
- [x] Wstępny prompt Qwen, JSON mode, ustrukturyzowany pośredni wynik.
- [x] Adapter OpenRouter w **oddzielnym** `compose.dev.yaml`, zgoda użytkownika przed przekazaniem dokumentu poza VPS.
- [ ] Modele Pydantic dla `CanonicalForm`, schemat pośredni i walidacja typów.
- [x] Quality gate wykrywa potencjalnie brakujące etykiety; [ ] pełna detekcja halucynacji i pochodzenia pól.
- [ ] Przetwarzanie dokumentów wielostronicowych z łączeniem wyników, retry i limitami.
- [ ] **Wersja konkursowa:** uruchomić lokalny model z otwartymi wagami (Ollama/Qwen lub inny) i przejść test całkowicie bez OpenRouter; potrzebny odpowiedni sprzęt z RAM/VRAM.
- [ ] Testy na niewidzianych wcześniej formularzach.

### Etap E — Reguły i słowniki · P1
- [ ] Zaimportować słowniki i dane inicjalne COI, powiązać je z polami.
- [x] Podstawowa detekcja walidatorów PESEL, NIP, REGON, ZIP_CODE, EMAIL i REQUIRED; [ ] telefon, daty, długości i testy rzeczywistych przykładów.
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
- [x] Testy automatyczne nowego kodu: 29/29; syntetyczny smoke test OpenRouter z wcześniejszego etapu pomyślny.
- [ ] Pełne testy MIME, ZIP-bomb, makr, limitu stron, cleanup, timeoutów, bezpieczeństwa wysyłki.
- [ ] Konfiguracja JWT (wymagania konkursowe); [x] `readyz.competition_compliant=false` również przy wyłączonym AI.
- [ ] Test Docker z czystego klona, test offline, brak wyjściowych zależności SaaS.
- [ ] Benchmark: wszystkie formaty, trafność pól i typów, zgodność COI JSON, czas mediany/p95.
- [ ] Wygenerować komplet JSON-ów dla wszystkich siedmiu formularzy konkursowych (#2–4, #6–9).
- [ ] README, architektura, audyt licencji, prezentacja PDF ≤10 slajdów, film ≤3 minut, dostępne repozytorium, opis projektu.
- [ ] Próba demonstracji na **nowym** formularzu i weryfikacja gotowości submission.

## Najbliższa sekwencja bez zbędnych prac

1. **GitHub:** ✅ Repo utworzone, push zakończony; utrzymywać synchronizację `origin/main`.
2. **P0:** ✅ Schemat COI, bezpośredni eksport i quality gate. **Dalej:** porównanie rzeczywistych referencji i poprawa mapowania.
3. **P0:** test na jednym prawdziwym formularzu COI (np. #3), wykaz brakujących i nadmiarowych pól, poprawki promptu/adaptera.
4. **P0:** Docling i obsługa starego DOC; ODS działa jako parser tymczasowy. Potem P1 słowniki i JSON Forms.
5. **P0:** rozstrzygnąć konkursowy runtime bez zewnętrznego API; OpenRouter pozostaje wyłącznie narzędziem developerskim.

**Definicja sukcesu MVP:** `POST /api/v1/forms/convert` przyjmuje **każdy wymagany format** i zwraca bezpośrednio **JSON zgodny ze schematem COI**, potwierdzony testem na nowych materiałach, działając **bez zewnętrznych API**.
