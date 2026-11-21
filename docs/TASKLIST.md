# FormFlow AI — aktualna lista zadań

**Data przeglądu:** 2026-11-21; wersja v1.1.0. Decyzja obowiązująca: [zgłoszenie z API](DECISION_API_SUBMISSION.md).
**Aplikacja:** https://vibe.tail075c6f.ts.net:9466/ — tylko Tailnet.  
**Legenda:** [x] ukończone, [ ] do zrobienia; **P0** = obowiązkowe/krytyczne, **P1** = dodatkowe punkty.  
**Pełny pierwotny plan:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Oznaczenia ukończenia poniżej są weryfikowane względem kodu i działającego API, a nie aspiracyjnego planu.

## Decyzja nadrzędna — API na konkurs

- [x] **Na hackathon dostarczamy wersję z OpenRouter/Qwen API.** Nie wdrażamy lokalnego modelu ani nie wykonujemy offline inference na ten konkurs.
- [x] Kod Ollama pozostaje wyłącznie **opcjonalnym backlogiem po konkursie**, nie P0.
- [ ] **Otwarte ryzyko regulaminowe:** zakaz zewnętrznych API w zadaniu COI; wersja OpenRouter **nie spełnia tego wymogu**. Ewentualnie uzyskać pisemne stanowisko organizatora.
- [ ] Opisać jawnie korzystanie z API i zgodę użytkownika w materiałach zgłoszeniowych; nie reklamować produktu jako zgodnego z zakazem API.

Pełny zapis: [DECISION_API_SUBMISSION.md](DECISION_API_SUBMISSION.md).

## Stan obecny

- ✅ FastAPI 1.1.0 na VPS; Docker Compose, nie-root, ograniczony RAM, port tylko `127.0.0.1:18171`; Tailscale Serve na porcie 9466.
- ✅ UI do uploadu, inspekcja pliku i świadoma zgoda na zewnętrzne AI.
- ✅ Lokalny, lekki parser tekstu PDF/DOCX/ODS/XLSX; JPG/PNG i skan PDF przez obraz wysłany do modelu.
- ✅ **Używane w development i planowane do zgłoszenia:** OpenRouter + Qwen3-VL-30B-A3B-Instruct. Potwierdzony HTTP 200 na **syntetycznym** DOCX: 5 stron, 15 elementów (w tym sekcje), 0 błędów wstępnej walidacji. Pierwotny test poprzedzał włączenie oficjalnego schematu COI.
- ✅ Prototyp `semantic JSON -> tabs/questions/flow`, UUID5, walidacja strukturalna i oficjalny JSON Schema COI; testy: **70/70**.
- ✅ Oryginalny `JSON Schema` COI podłączony bez zmian bajtów; uwaga: schemat jest liberalny i nie zastępuje testu importera.
- ✅ Prywatne repo GitHub [Tymidymi/formflow-ai](https://github.com/Tymidymi/formflow-ai) utworzone; `main` opublikowany i zgodny z lokalnym Git.
- ✅ Lokalny PDF layout/OCR działa (pypdf/Tesseract). ❌ Pozostają pełny Docling PDF, stary `.doc`, zaawansowane funkcje JSON Forms i część słowników COI. Lokalny LLM jest poza zakresem hackathonu.

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
- [x] Test Qwen na tekstach wyciągniętych z oryginalnych PDF-ów COI #3 i #4; [ ] test binarnych oryginałów i ręczna ocena kompletności.

### Etap C — Ekstrakcja Docling i pełne wejście · P0
- [x] Podstawowe wydobycie treści z PDF/DOCX/XLSX, obsługa JPG/PNG i obrazów skanowanego PDF w trybie developerskim.
- [x] Izolowany Docling Office dla DOCX/XLSX/ODS, 384 MiB, HTTP 200; [ ] ciężki Docling PDF/OCR.
- [x] Docling Office zachowuje tabele w Markdown; [ ] pełne współrzędne, numery stron i pochodzenie pól.
- [x] Lekki parser `.ods` bez dodatkowych zależności, testy XML; [ ] adapter starego `.doc` i audyt konwersji.
- [x] Lokalny OCR Tesseract pol+eng dla PDF/JPG/PNG, limit stron i pamięci; [ ] pełny Docling PDF z modelami.
- [ ] Testy wszystkich wymaganych rozszerzeń na materiałach COI.

### Etap D — Model semantyczny i generowanie · P0
- [x] Wstępny prompt Qwen, JSON mode, ustrukturyzowany pośredni wynik.
- [x] Adapter OpenRouter w `compose.dev.yaml` (konfiguracja demo i planowanego zgłoszenia), zgoda przed przekazaniem dokumentu poza VPS.
- [ ] Modele Pydantic dla `CanonicalForm`, schemat pośredni i walidacja typów.
- [x] Quality gate wykrywa potencjalnie brakujące etykiety; [ ] pełna detekcja halucynacji i pochodzenia pól.
- [x] Lokalna ekstrakcja PDF do 25 stron, OCR do 4, limit wejścia 18 tys. znaków z blokadą niekompletnego eksportu; [ ] modelowe chunking/retry dla długich dokumentów.
- [x] **Decyzja konkursowa:** używamy OpenRouter API, mimo że nie spełnia zakazu zewnętrznych API. Lokalny LLM: **opcjonalnie po konkursie**.
- [ ] Testy na niewidzianych wcześniej formularzach.

### Etap E — Reguły i słowniki · P1
- [ ] Zaimportować słowniki i dane inicjalne COI, powiązać je z polami.
- [x] Podstawowa detekcja walidatorów PESEL, NIP, REGON, ZIP_CODE, EMAIL i REQUIRED; [ ] telefon, daty, długości i testy rzeczywistych przykładów.
- [ ] Zależności `states`, dynamiczna widoczność/warunki między sekcjami i stronami.
- [ ] Propozycje nowych słowników; oznaczyć sugestie wymagające akceptacji.
- [ ] Testy walidacji i przepływów na #8 (odpady) i #9 (połączone wnioski sportowe).

### Etap F — Frontend i podgląd JSON Forms · P1
- [x] Statyczny interfejs uploadu i pobierania wygenerowanego JSON.
- [x] Adapter do **oddzielnych** `JSON Schema + UI Schema` na potrzeby JSON Forms.
- [x] React + JSON Forms: podgląd stron/sekcji/pól, walidacje po polsku, SHOW i podsumowanie; [ ] pełna weryfikacja w oficjalnym importerze COI.
- [x] Widok porównawczy: oryginał PDF/obraz lub tekst Office / COI JSON / interaktywny formularz.
- [x] Edycja **definicji** pól COI przez urzędnika: nazwa, typ, required, opcje, walidacja, dodawanie/usuwanie/przestawianie, sekcje, cofanie i walidowany eksport. [ ] Trwałe zatwierdzanie wersji w bazie, źródła i poziomy pewności.

### Etap G — Jakość, bezpieczeństwo i submission · P0
- [x] Podstawowe ograniczenia uploadu, weryfikacja nazw i formatów, Tailscale-only.
- [x] Testy automatyczne v0.8.0: **50/50 backend + 7/7 frontend** oraz Chromium na desktopie i mobile; syntetyczny smoke test OpenRouter z wcześniejszego etapu pomyślny.
- [ ] Pełne testy MIME, ZIP-bomb, makr, limitu stron, cleanup, timeoutów, bezpieczeństwa wysyłki.
- [ ] Konfiguracja JWT (wymagania konkursowe); [x] `readyz.competition_compliant=false` również przy wyłączonym AI.
- [ ] Test Docker z czystego klona z OpenRouter API; test inferencji offline **poza aktualnym zakresem**. Ryzyko niezgodności z regulaminem pozostaje otwarte.
- [ ] Benchmark: wszystkie formaty, trafność pól i typów, zgodność COI JSON, czas mediany/p95.
- [ ] Wygenerować komplet JSON-ów dla wszystkich siedmiu formularzy konkursowych (#2–4, #6–9).
- [ ] README, architektura, audyt licencji, prezentacja PDF ≤10 slajdów, film ≤3 minut, dostępne repozytorium, opis projektu.
- [ ] Próba demonstracji na **nowym** formularzu i weryfikacja gotowości submission.

## Najbliższa sekwencja bez zbędnych prac

1. **GitHub:** ✅ Repo utworzone, push zakończony; utrzymywać synchronizację `origin/main`.
2. **P0:** ✅ Schemat COI, bezpośredni eksport i quality gate. **Dalej:** porównanie rzeczywistych referencji i poprawa mapowania.
3. **P0:** test na jednym prawdziwym formularzu COI (np. #3), wykaz brakujących i nadmiarowych pól, poprawki promptu/adaptera.
4. **P0:** Docling Office już działa; pozostały pełny Docling PDF/OCR i stary DOC. Potem słowniki i pełny benchmark oryginalnych dokumentów; React JSON Forms już działa, lokalny Qwen wyłącznie po hackathonie.
5. **Decyzja zamknięta:** zgłoszenie korzysta z OpenRouter API. **Ryzyko regulaminowe otwarte**, ale nie planujemy lokalnego LLM na ten hackathon.

**Definicja sukcesu MVP:** `POST /api/v1/forms/convert` przyjmuje **każdy wymagany format** i zwraca bezpośrednio **JSON zgodny ze schematem COI**, potwierdzony testem na nowych materiałach, działając z OpenRouter API (**niezgodność z wymogiem COI zakazującym zewnętrznych API jest jawnie udokumentowana**).


## Weryfikacja chunku v0.5.0

- [x] Docker Docling Office: DOCX, XLSX, ODS — REST HTTP 200 i zachowane tabele.
- [x] Główne API łączy się z Docling Office po prywatnej sieci Dockera; brak publicznych portów workera.
- [x] Bezpieczny fallback ekstraktora przy niedostępności workera.
- [x] Test syntetyczny DOCX → Docling → Qwen → JSON COI (schema_valid=true).
- [x] Pierwszy benchmark na tekstach wyciągniętych z oryginalnych PDF COI #3 i #4.
- [x] Próba długiego promptu i wycofanie po regresji liczby pól.
- [ ] Benchmark na oryginalnych plikach binarnych wszystkich formatów.
- [ ] Pełny Docling PDF/OCR, legacy DOC, słowniki/dynamika, zaawansowane funkcje JSON Forms. Lokalny LLM: po konkursie.


## Etap v0.6.0 — PDF Layout i OCR

- [x] Oddzielny PDF/OCR worker: pypdf layout + pypdfium2 + Tesseract pol+eng, prywatna sieć i 384 MiB RAM.
- [x] Lokalny podgląd ekstrakcji z PDF/PNG/JPG bez OpenRouter.
- [x] Testy workera: tekst PDF, OCR PDF skan, OCR PNG, uszkodzony PDF i limit 25 stron — 5/5.
- [x] Testy API: 46/46 (mock bez zewnętrznych zapytań).
- [x] Syntetyczny PDF skanowany przeszedł OCR → Qwen → JSON COI (HTTP 200, schema_valid=true).
- [x] Reguły odzyskujące jawnie obecne pola, korekty typów i filtrowanie podpisu papierowego; sprawdzone na poprzednich wynikach COI #3/#4.
- [x] Lokalna ekstrakcja binarnych oryginalnych PDF-ów/PNG COI #3/#4.
- [ ] **Pełny benchmark binarnych oryginalnych dokumentów przez VPS + LLM** i ręczny scoring recall/precision/types; obecne testy są częściowe.
- [ ] Pełny Docling PDF/layout z modelami, jeśli zasoby pozwolą.
- [ ] Legacy DOC, słowniki, warunki, zaawansowane funkcje JSON Forms i audyt licencji. Lokalny Qwen: po konkursie.

Szczegóły: [PDF_ENGINE.md](PDF_ENGINE.md).

## Etap v0.7.0 — Quality Engine (Ollama jako opcja przyszła)

- [x] Ręczna lista referencyjnych pól dla COI #3/#4 i benchmark etykiet oraz typów.
- [x] Replay na zapisanych wynikach Qwen: #3 10/11 → 11/11; #4 15/18 → 18/18 etykiet.
- [x] JSONata SHOW dla danych innej osoby odpowiedzialnej oraz warunkowego oświadczenia w #4.
- [x] Obsługa dictionaryName — słownik Kraje dla SELECT; [ ] pełne słowniki TERYT.
- [x] Eksperymentalny adapter Ollama/Qwen i testy mock. Realna inferencja: opcjonalny backlog po hackathonie.
- [x] Testy FastAPI 46/46; PDF/OCR worker 5/5.
- [ ] Full E2E na oryginalnych binarnych PDF #3/#4 i statystyczny benchmark recall/precision.
- [ ] Test wykonywania stanów JSONata w docelowym rendererze COI.
- [ ] Audyt licencji; wersji bez API nie planujemy na konkurs. **Niezgodność z zakazem API pozostaje nieusunięta.**

Szczegóły: V07_QUALITY_REPORT.md i LOCAL_QWEN.md.


## Etap v0.8.0 — Interaktywny formularz i porównanie

- [x] React 18.3.1 + JSON Forms 3.8.0, frontend pakowany do lokalnych plików JS/CSS (bez CDN).
- [x] JSON COI -> JSON Schema + UI Schema; komponenty TEXT_FIELD, TEXTAREA, NUMBER, DATEPICKER, RADIO, CHECKBOX, SELECT i podgląd FILE_UPLOADER.
- [x] Reguły SHOW uruchamiane w podglądzie na podstawie wąskiego, bezpiecznie parsowanego wzorca COI; dla 'Inna osoba' odsłaniają się dwa pola.
- [x] Zakładki: Formularz cyfrowy / Oryginał / JSON COI; podgląd PDF/PNG/JPG z lokalnego pliku.
- [x] Polskie komunikaty podstawowych walidacji po kliknięciu 'Sprawdź pola', formularz stronicowany, podsumowanie, eksport COI JSON.
- [x] Syntetyczny i bezpłatny formularz demonstracyjny: GET /api/v1/demo/convert (bez OpenRouter).
- [x] Testy: 50/50 backend, 7/7 adapter, desktop/mobile Chromium (reguły, zakładki, brak błędów i poziomego scrolla).
- [x] **E2E z SYNTHETYCZNYM zeskanowanym PDF**: upload -> OCR -> OpenRouter/Qwen -> JSON COI -> React + podgląd oryginału; oficjalny schemat i quality gate OK.
- [ ] Pełny benchmark **oryginalnych binarnych** plików COI #3/#4 na VPS z ręcznym scoringiem recall/precision/types — nadal wymagany.
- [ ] Załączniki jako rzeczywisty upload, edytor definicji pól i zależności, TERYT oraz pozostałe słowniki.
- [ ] Osobny origin / sandbox dla renderera, ponieważ JSON Forms / Ajv wymagają dynamicznej kompilacji; obecny CSP zawiera 'unsafe-eval'.
- [ ] Weryfikacja JSONata w **docelowym** rendererze COI; test JSON Forms nie jest równoważny importerowi COI.

Zobacz [V08_INTERACTIVE.md](V08_INTERACTIVE.md) i [DECISION_API_SUBMISSION.md](DECISION_API_SUBMISSION.md).


## Hotfix v0.8.1 — Referencyjny JPEG COI #1 / problem RODO

- [x] **Naprawiono:** zamiast 10 akapitów RODO w TEXTAREA generujemy faktyczne pola wniosku.
- [x] OCR pionowo sklejonych stron — osobna ekstrakcja obydwu części obrazu.
- [x] Separacja części operacyjnej od klauzuli; model widzi przede wszystkim właściwy wniosek.
- [x] Informacje prawne → **TEXT_BLOCK tylko do odczytu**, oznaczenie tekstu OCR jako niezweryfikowanego.
- [x] Ogólny odzysk pól z jawnych etykiet; dla rozpoznanego COI #1 wąski fallback z referencji na przekręcone przez OCR podpisy.
- [x] Usunięcie wymyślonych pól adresowych Qwen dla COI #1, gdy nie występują w formularzu papierowym.
- [x] Quality gate: zero pól wejściowych nie może przejść jako poprawny formularz.
- [x] Test regresji na **rzeczywistym tekście OCR z przesłanego JPEG-u**: 9 pól wejściowych, 0 edytowalnych pól RODO, 1 legal TEXT_BLOCK, schema_valid=true.
- [x] Test przeglądarkowy na odtworzonym JSON COI: 9 kontrolek na stronie wniosku; strona RODO bez kontrolek/textarea.
- [x] Test modelu OpenRouter na rzeczywistym odczycie OCR (bez obrazu): wykazał wymyślone dodatkowe pola, które następnie objęto filtrem.
- [x] Testy: **58/58 backend**, **8/8 frontend**, **6/6 silnik PDF/OCR**.
- [ ] Powtórzyć **binarny upload dokładnie tego JPEG-u do VPS** i sprawdzić rezultat Qwen z obrazem; dotychczasowy test pełnego JPEG E2E nie jest potwierdzony.
- [ ] Potwierdzić 1:1 zgodność z rozbudowanym COI JSON #1 w oficjalnym importerze; obecny fallback rekonstruuje **podstawowe pola źródłowego papierowego wniosku**, nie pełny zestaw wariantów formularza.

Szczegóły: [COI1_JPEG_FIX.md](COI1_JPEG_FIX.md).


## Etap v0.9.0 — Edytor definicji formularzy COI

- [x] Przycisk **Edytuj formularz** bezpośrednio w sekcji „Podgląd wygenerowanej eUsługi”.
- [x] Edytor właściwości pytania: etykieta, typ (8 rodzajów), wymagane, opcje wyboru, walidacja PESEL/NIP/REGON/e-mail/kod, podpowiedź.
- [x] Dodawanie/usuwanie/przestawianie pól w sekcji, tworzenie/usuwanie sekcji, zmiana nazwy sekcji/strony i tytułu formularza.
- [x] Cofanie do 40 ostatnich zmian w danej sesji edycji; przycisk Anuluj edycję przywraca stan z jej początku.
- [x] Edycje modyfikują **oryginalną strukturę COI JSON**, zachowując UUID, techName, states i kolejność/siatkę.
- [x] Ochrona `SHOW`: brak możliwości usunięcia źródła lub używanej opcji; zmiana nazwy strony naprawia znane referencje JSONata.
- [x] Strony `FINISH` i klauzule `TEXT_BLOCK` pozostają tylko do odczytu.
- [x] **Zapisz poprawki** sprawdza definicję w `POST /api/v1/forms/validate-json` (własny VPS, bez AI); **Pobierz JSON COI** eksportuje rzeczywiście poprawiony plik i ponownie sprawdza walidację.
- [x] Ostrzeżenia przed utratą edycji przy ponownym uploadzie/generowaniu, zamknięciu karty lub uruchomieniu nowego demo.
- [x] Testy: **16/16 frontend**, **58/58 backend**, Chromium (edycja+undo+RADIO+download+JSON valid), ekran 390 px bez overflow.
- [x] Drugi test Chromium: korekta pola numeru działki w COI #1, ochrona strony RODO, JSON schema_valid=true.
- [ ] Trwała baza danych wersji i zatwierdzania przez urzędnika, komentarze, źródła/prawdopodobieństwa, edycja reguł `SHOW`, edycja stron MAIN.
- [ ] Pełny test importu do rzeczywistego systemu COI oraz benchmark na nowych oryginalnych formularzach.

Dokumentacja: [V09_FIELD_EDITOR.md](V09_FIELD_EDITOR.md).


## Etap v1.0.0 — Prosty kreator trzyetapowy (21.11.2026)

- [x] **Krok 1: Dodaj dokument** — duży wybór pliku, potwierdzenie inspekcji, zgoda na AI i jeden przycisk „Przygotuj formularz”.
- [x] **Krok 2: Sprawdź i popraw** — widoczny dopiero po analizie lub po uruchomieniu syntetycznego demo. „Popraw pytania” + „Wszystko się zgadza — dalej”.
- [x] **Krok 3: Pobierz formularz** — osobny ekran z nazwą, liczbą pól i dużym przyciskiem pobierania walidowanego COI JSON.
- [x] Pasek postępu 1/2/3, duże przyciski i czytelniejsze instrukcje dla nietechnicznych użytkowników.
- [x] Opcje OCR i diagnostyka schowane w „Opcje dla administratora”; JSON COI nie jest zakładką podstawowego podglądu.
- [x] Powrót między etapami, ochrona przed utratą ręcznych poprawek; powrót do już wygenerowanego formularza bez kolejnego wywołania OpenRouter.
- [x] Własny upload i inspekcja działają na rzeczywistym syntetycznym PNG; symulowana odpowiedź AI otwiera podgląd.
- [x] CSP: zezwolenie na własne adresy obrazów `blob:` w podglądzie oryginalnego zdjęcia.
- [x] Testy: **58/58 backend**, **16/16 frontend**, Chromium E2E kompletnej trasy, 390 px bez overflow, zero błędów JS i konsoli.
- [ ] Testy użyteczności z urzędnikami oraz dostępności (klawiatura, powiększenie 200%, czytniki ekranu), trwałe wersjonowanie, test importu w oficjalnym COI.

Szczegóły: [V10_GUIDED_WIZARD.md](V10_GUIDED_WIZARD.md).


## Etap v1.1.0 — Multimodal PDF i source grounding

- [x] PDF worker generuje obrazy maksymalnie **3 pierwszych stron** i raportuje numery stron.
- [x] Włączona domyślnie analiza **PDF: OCR/layout + Vision Qwen**; dla JPG/PNG Vision działa jak wcześniej.
- [x] Przełącznik diagnostyczny `vision=off|on|auto` umożliwia A/B na identycznych plikach.
- [x] Raport `grounding`: tekstowe potwierdzenia pól z OCR, najlepsze cytaty i numery stron, lista do ręcznej weryfikacji. Brak dopasowania nie usuwa automatycznie wizualnie wykrytego pola.
- [x] Jawna lista obejrzanych stron i ostrzeżenie, gdy obrazowo nie przeanalizowano wszystkich stron PDF; zachowane świadome zgody na OpenRouter.
- [x] Rozdzielenie `INFORMACJE / POUCZENIE / OBJAŚNIENIA` od pytań: nieedytowalny `TEXT_BLOCK` zamiast pól z opłatami.
- [x] Usuwanie podpisów papierowych i odzyskiwanie poszczególnych numerowanych oświadczeń z OCR, również po zawinięciu wierszy.
- [x] Benchmark OCR-only vs OCR+Vision na dwóch **syntetycznie wyrenderowanych skanach** na podstawie oryginalnego OCR COI #3/#4. Wizja nie była jednoznacznie lepsza — oba tryby miały wady, stąd dodatkowe reguły.
- [x] Testy backend, worker PDF/OCR, frontend — wyniki w [V11_MULTIMODAL_QUALITY.md](V11_MULTIMODAL_QUALITY.md).
- [ ] **P0:** benchmark jakości na **oryginalnych binarnych** formularzach #2–#9; human-labeled recall/precision/types oraz raporty pomyłek.
- [ ] **P0:** Vision wszystkich stron dłuższych PDF przez chunking; obecnie 3 strony obrazowo i OCR skanów do 4 stron.
- [ ] **P1:** render Office (DOCX/XLSX/ODS) do obrazu; obecnie Docling tekst i tabele.
- [ ] **P1:** source grounding w postaci współrzędnych pól i podświetlenia w oryginale; obecny raport jest tekstowy.

Status regulaminowy OpenRouter: **bez zmian — zgłoszenie planowane z API, mimo zakazu zewnętrznych API**.
