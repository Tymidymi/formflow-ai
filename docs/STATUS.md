# FormFlow AI — stan wdrożenia (21.11.2026)

**Nadrzędna decyzja dla zgłoszenia:** OpenRouter API / Qwen3-VL; **bez lokalnego LLM** na hackathonie. Ollama ewentualnie po konkursie. **To nie spełnia zakazu zewnętrznych API COI.** Szczegóły: [DECISION_API_SUBMISSION.md](DECISION_API_SUBMISSION.md).


## Wdrożone na VPS

- [x] FastAPI 0.7.0 i Docker Compose z portem 127.0.0.1:18171
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
- [x] Wybrano konkursowe demo z OpenRouter API (`compose.dev.yaml`); [ ] niezgodność z zakazem API w COI pozostaje otwartym ryzykiem.
- [ ] JSON Forms (renderer) nie jest jeszcze podłączony
- [ ] Nie zmierzono jeszcze jakości na prawdziwych formularzach konkursowych
- [x] GitHub: prywatne repo https://github.com/Tymidymi/formflow-ai; origin/main opublikowany

## Komendy operacyjne

```bash
cd /home/tymot/projects/formflow-ai
# Development — używa lokalnego pliku .env, który nie trafia do Git.
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
# Opcja po hackathonie, NIE bieżąca konfiguracja zgłoszeniowa: bez OpenRouter
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
- OpenRouter planowany również do konkursowego zgłoszenia pomimo zakazu zewnętrznych API; lokalna inferencja poza zakresem. Szczegóły: [PDF_ENGINE.md](PDF_ENGINE.md).

## Etap v0.7.0 — 21 listopada 2026

- Replay wyników semantycznych Qwen: COI #3 10/11→11/11, COI #4 15/18→18/18 (test wąski, bez binarnego PDF end-to-end).
- Dynamiczne stany JSONata SHOW i słownik Kraje.
- Opcjonalny adapter Ollama/Qwen, testy protokołu mock; nie wykonano inferencji na VPS.
- 46/46 testów FastAPI.
- Test offline przeniesiony do opcjonalnego backlogu po konkursie; nadal brak testu warunków w realnym rendererze.

## Decyzja nadrzędna po v0.7.0

- **Oddajemy wersję z API OpenRouter/Qwen**, nie wersję offline.
- Nie robimy w kolejnych runach lokalnej inferencji, konfiguracji GPU ani testu uruchomienia Ollama.
- Kolejne prace: benchmark prawdziwych dokumentów, jakość konwersji, JSON Forms, testy i submission.
- **Ryzyko:** wymaganie COI wyklucza zależności od zewnętrznych API; nasza wersja go nie spełnia, a organizator nie potwierdził wyjątku.
- [Decyzja i ryzyko](DECISION_API_SUBMISSION.md).


## Etap v0.8.0 — 21 listopada 2026

- Interaktywny podgląd React + JSON Forms, trzy zakładki (cyfrowy/original/COI JSON), strony, sekcje, walidacje, dynamiczne SHOW.
- Budowanie self-hosted bundle JS/CSS przez esbuild; UI responsywne na 390 px.
- Syntetyczny formularz demonstracyjny, bez zewnętrznego API; pełna ścieżka generowania OpenRouter zachowuje świadomą zgodę.
- 50/50 testów API, 7/7 testów adaptera; Chromium desktop/mobile bez błędów JavaScript, w tym odsłanianie 2 pól, załącznik file i polskie walidacje.
- Osobny E2E: **syntetyczny zeskanowany PDF** przez przeglądarkę -> lokalny OCR -> OpenRouter/Qwen3-VL -> JSON COI -> interaktywny podgląd: schema_valid=true, quality=true, 7 pól/3 strony.
- Bezpieczeństwo: JSONata nie jest wykonywany bezpośrednio; JSON Forms/Ajv wymaga wyjątku CSP 'unsafe-eval' — w przyszłości zalecana izolacja renderera.
- Ograniczenia: brak pełnego testu oryginalnych binarnych COI #3/#4 przez VPS; załączniki preview-only; niezweryfikowany importer COI. OpenRouter pozostaje niezgodny z zakazem zewnętrznych API COI.
- Dokumentacja: [V08_INTERACTIVE.md](V08_INTERACTIVE.md).


## Hotfix v0.8.1 — 21.11.2026 / COI #1 JPEG

- Usunięto podstawowy błąd: klauzula RODO nie jest edytowalnym formularzem; pozostaje blokiem informacyjnym z ostrzeżeniem o jakości OCR.
- Długie zdjęcia sklejonych stron: podział regionów OCR + crop wizualny głównego wniosku dla Qwen.
- Dla oficjalnego referencyjnego COI #1 podstawowe 9 pól są odzyskiwane, a fikcyjne dodatki adresowe modelu usuwane.
- Rzeczywisty tekst OCR przesłanego JPEG-u przeszedł regresję: wynik COI JSON zgodny ze schematem, frontend: 9 pól + nieedytowalna klauzula.
- Testy: backend 58/58, frontend 8/8, OCR worker 6/6. **Pełny upload tego samego binarnego JPEG-u pozostaje do powtórzenia.**
- Decyzja OpenRouter API bez zmiany; ryzyko niezgodności z wymogiem COI nadal otwarte.
- [Raport naprawy](COI1_JPEG_FIX.md).


## Etap v0.9.0 — 21 listopada 2026

- W interaktywnym podglądzie działa **tryb edycji definicji COI JSON** dla urzędnika.
- Obsługuje poprawianie pytań, typu/obowiązkowości/walidacji/opcji, dodawanie/usuwanie/przestawianie, sekcje i tytuły stron.
- Form validation: lokalne `POST /api/v1/forms/validate-json`, zapis do stanu przeglądarki, eksport **zmodyfikowanego** COI JSON. Brak trwałego zapisu w DB.
- Warunki `SHOW` i identyfikatory pól są chronione, a RODO TEXT_BLOCK jest readonly.
- Testy Node 16/16, FastAPI 58/58. Chromium: edycja + radio + cofnięcie + zapis + JSON download + server validation: valid=true / schema_valid=true, mobilnie 390px OK.
- Dodatkowy Chromium na COI #1: poprawione pole numeru działki, brak edytowalnych pól w klauzuli RODO, schema_valid=true.
- Wersja v0.9.0 aktywna na VPS pod Tailscale; OpenRouter bez zmian; regulaminowe ryzyko zależności od API nadal otwarte.
- Szczegóły: [V09_FIELD_EDITOR.md](V09_FIELD_EDITOR.md).


## Etap v1.0.0 — 21 listopada 2026

- Przebudowano UI na progresywny kreator: krok 1 (plik + zgoda), krok 2 (podgląd/edycja), krok 3 (pobranie).
- Przed przetworzeniem nie pokazujemy edytora, diagnostyki i eksportu. Po przetworzeniu chowamy ekran importu.
- Duże przyciski i krótkie objaśnienia; przejrzysty pasek 1/3 → 2/3 → 3/3.
- Edytor COI, reguły SHOW, poprawione RODO i walidacja JSON zachowane.
- Lokalny blob obrazów zaakceptowany w CSP — wcześniej własny podgląd JPG/PNG był blokowany.
- Testy: backend 58/58; frontend 16/16; przeglądarka: demo, ręczna korekta, cofanie, wynikowa walidacja, pobieranie, plik PNG i zgoda, porównanie z oryginałem, widoki 390px bez overflow i bez JS errors.
- Test UI generowania użył sztucznego payloadu modelu, nie dodatkowej inferencji Qwen.
- Prywatny deployment Tailscale Serve, kod na GitHubie; ryzyko regulaminowe OpenRouter API bez zmian.
- Raport: [V10_GUIDED_WIZARD.md](V10_GUIDED_WIZARD.md).


## Etap v1.1.0 — Multimodal PDF i quality engine

- Uruchomiono PDF Vision jako domyślne źródło dla Qwen razem z OCR; do trzech obrazów stron, z jawnym ostrzeżeniem przy częściowym pokryciu.
- Wbudowany przełącznik A/B PDF Vision; wykonano rzeczywiste zapytania OpenRouter na odtworzonych skanach COI #3 i #4.
- Vision daje różne rezultaty: #3 lepiej rozdziela typy checkbox, #4 lepiej widzi daty, lecz czasem łączy wielopunktowe oświadczenia. Nie zakładamy bezwzględnej poprawy samym obrazem.
- Dodano konserwatywne source grounding, rozpoznawanie informacji o opłatach jako read-only, papierowe podpisy wykluczone i odzysk numerowanych oświadczeń.
- Testy i metodyka: [V11_MULTIMODAL_QUALITY.md](V11_MULTIMODAL_QUALITY.md).
- Wciąż brakuje oryginalnego benchmarku binariów i wizualnego podglądu Office; zewnętrzny OpenRouter jest używany świadomie pomimo ryzyka konkursowego.

- Uzupełnienie wyników v1.1: COI #3 — informacje o opłatach jako read-only, brak edytowalnego podpisu; COI #4 — odzysk 4 numerowanych potwierdzeń na realnej ścieżce Qwen/COI po korekcie parsera.
- Ostateczna liczba testów backend v1.1: **70/70**.


## Etap v1.2.0 — 21 listopada 2026

- Dodane prywatne, trwałe, rotowane JSONL logi metadanych konwersji do `data/private/logs`.
- Frontend pokazuje numer zgłoszenia, backend spina nim wszystkie zdarzenia AI, od ekstrakcji do kodu HTTP.
- Przy błędach JSON Qwen zapisuje finish_reason, liczby tokenów oraz wiersz/kolumnę błędu składni, nigdy surowe dane.
- Limit generacji zwiększony z 4000 do 6500; brak automatycznej ponownej płatnej próby.
- Przeszłych błędów nie da się odtworzyć bez historycznych logów. Kolejne zgłoszenia będą miały identyfikatory.
- Pełny opis: [V12_CONVERSION_LOGGING.md](V12_CONVERSION_LOGGING.md).
- Test live: zdarzenia zapisują się w prywatnym pliku, znajdują po request_id, zachowują się po restarcie; uszkodzony PDF ma odrębny kod DOCUMENT_REJECTED.


## Etap v1.3.0 — 21 listopada 2026

- Usunięto produkcyjne poprawki oparte na konkretnych przykładach: `form_repair`,
  `semantic_quality`, `conditional_rules`, `benchmark_gold`.
- Zastąpiono jednoprzebiegowy prompt uniwersalną analizą stron, wyodrębnianiem
  wydrukowanych komórek tabel i niezależną kontrolą geometrii przez Vision.
- Odpowiedzi OCR/VLM są scalane przez cytaty źródłowe, kolumny, wiersze i strony;
  duplikaty tabel oraz oświadczeń RODO są usuwane przed eksportem.
- Quality gate: luka pól vs drukowane puste miejsca skutkuje ostrzeżeniem
  lub blokadą, a nie automatycznym zatwierdzeniem.
- COI zachowuje siatkę wiersz/kolumna i nie obcina pól po cichu.
- [Raport v1.3](V13_UNIVERSAL_EXTRACTION.md).

### Kontrola jakości v1.3.0 — ograniczenie aktualne

- Testy: 75/75 backend, 16/16 frontend, 7/7 worker PDF.
- Syntetyczny skan robót: odtworzono poprawnie 4 × 2 × 3 = 24 komórki tabeli; JSON COI poprawny.
- Ostatni pełny przebieg Qwen wykrył fałszywą tabelę w liście załączników. Następnie dodano OGÓLNY filtr wymagający powtarzających się wierszy/kolumn w OCR; testy list i prawdziwych tabel przeszły.
- [ ] Powtórzyć test LIVE przez OpenRouter po tym filtrze. Test jednostkowy NIE jest równoważny walidacji jakościowej na nowym pliku.
- [ ] Zweryfikować na niezależnych oryginalnych dokumentach, że nie ma duplikatów i fałszywych tabel, w tym PDF/DOCX/XLSX/ODS/JPG.
- Mechanizm nie jest jeszcze bezbłędnym konwerterem dowolnego pliku; słabe OCR i model Vision nadal mogą popełniać błędy.

## Hotfix v1.3.0 — niezależna kontrola grup wyboru (21.11.2026)

- [x] Audyt wizualny wszystkich grup checkbox/radio, w tym poziomych i pionowych list w pojedynczym wierszu tabeli.
- [x] Oddzielne rozpoznawanie miejsc na dane przypisane do konkretnych zaznaczanych opcji oraz warunki SHOW.
- [x] Ogólna konsolidacja powielonych kontrolek z potwierdzonym wspólnym nagłówkiem i źródłową etykietą.
- [x] Geometryczna kontrola liczby małych drukowanych kwadratów i reanaliza fragmentów strony, gdy Qwen zwróci za mało opcji.
- [x] Benchmark LIVE na niezależnym, syntetycznym formularzu ewidencji urządzenia: 2 grupy, 5 opcji, 2 pola dodatkowe, bez duplikatów i EMPTY_CHOICES, JSON COI valid=true.
- [x] 85 testów backendowych zaliczonych.
- [ ] Przeprowadzić ponowny pełny upload **oryginalnego** formularza z informacją o posiadanym psie (w tej rozmowie dostarczono zrzuty ekranu, nie pełny plik PDF).
- [ ] Testy na wielu dowolnych oryginalnych binariach i mierzalna precyzja/recall pól.

Szczegóły: [V13_CHOICE_AUDIT.md](V13_CHOICE_AUDIT.md). Syntetyczny benchmark nie jest dowodem niezawodności dla każdego formularza. Ryzyko konkursowego zakazu zewnętrznych API pozostaje bez zmian.


## Bieżąca aktualizacja — 21.11.2026 — kontrakt CanonicalForm i stary DOC

- [x] Model `CanonicalForm` oparty na Pydantic: strony, sekcje, pola,
  opcje, source evidence, tabelaryczne wiersze/kolumny i zależności SHOW;
  walidacja przed eksportem COI. Nie tworzy ani nie zgaduje pól.
- [x] Izolowany parser `.doc` oparty na Antiword w workerze Docling Office
  (osobny proces, ograniczony czas/CPU/pamięć). Prawdziwy plik Word 97–2003,
  26 112 B: endpoint /extract i /api/v1/forms/extract-preview HTTP 200.
- [x] `/api/v1/capabilities` uwzględnia DOC tylko przy skonfigurowanym workerze.
- [x] 101 testów backend i 16 frontend przeszło po zmianach.
- [ ] DOC layout/checkboxy graficzne: obecny adapter jest **text-only** i zgłasza
  wymaganie weryfikacji wyniku.
- [ ] Formalny audyt GPL Antiword i wszystkich zależności obrazu.
- [ ] Import do oficjalnego narzędzia COI i zgodność z zakazem zewnętrznych API.
- [x] CI workflow opublikowany na GitHub; [ ] potwierdzić wynik uruchomienia.
- [ ] Synchronizacja historii lokalnego Git i gałęzi GitHub po zapisach API.

Zadania i priorytety: [TASKLIST.md](TASKLIST.md).


## Poprawki jakości po testach — 21.11.2026

- [x] Niezależne wykrywanie krótkich źródłowych pustych miejsc (`source_slot_audit.py`) z VLM na wycinku strony; przypisanie brakującego pola do istniejącej sekcji po kolejności OCR.
- [x] Zachowawcza reguła type-inference dla fizycznie wydrukowanego pola daty (nie dla konkretnego wniosku).
- [x] Scalanie grup wyboru, usuwanie duplikatów opcji/sekcji, zachowanie pól tekstowych zależnych od wybranej opcji.
- [x] Odczytywalne informacje wyłączone ze źródłowego obszaru wizualnej analizy i z odpowiedzi; zachowana pełna kopia tekstu w COI.
- [x] Eksport COI/eksport odpowiedzi rozdzielone w interfejsie. Wstępnie zapobiega pustym eksportom odpowiedzi.
- [x] 109 testów backendu + 20 testów frontendu.
- [ ] Ponowny rzeczywisty upload dostarczonego JPEG z Qwen — niepotwierdzony w tej sesji.
