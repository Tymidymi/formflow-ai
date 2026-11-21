# FormFlow 1.4 — status weryfikacji jakości (21.11.2026)

**Decyzja: NIE WDRAŻAĆ na produkcję.** Wersja z gałęzi `refactor/source-page-pipeline` jest kandydatem testowym na porcie 18172. Produkcja na 18171 pozostaje poprzednią wersją z modelem Qwen. Zmiany są niezacommitowane. Ten dokument oddziela wyniki potwierdzone od poprawek oczekujących na walidację.

## Model i zakres

- Obowiązujący model: OpenRouter `qwen/qwen3-vl-30b-a3b-instruct`. Przywrócono go również w `.env.example` i `compose.review.yaml`; brak reasoning override.
- Nie używać GPT do automatycznego testowania zamiast Qwena bez zgody. Wcześniejszy pełny test 32 plików na **GPT-4.1** wykazał 32 HTTP200, ale istotne błędy, więc nie jest wynikiem jakości 32/32.
- Testy są jawne i płatne, brak automatycznej eskalacji liczby prób. Źródła i logi pozostają w `/tmp/formflow-refactor-validation` i `/tmp/formflow-qwen-*`, poza repo.

## Potwierdzone defekty źródłowe i zabezpieczenia

1. Złożony DOCX z grupy 2 zawiera treść drugiej strony w OOXML, ale LibreOffice ją pomija. Pokrycie czterowyrazowych okien pomiędzy OOXML a renderowanym PDF ~22%. **NOWE:** `source_fidelity.py` sprawdza utratę większej części treści i zwraca 422 zamiast fałszywego `generated`. To zabezpieczenie, **nie** poprawne renderowanie; DOCX nadal jest nieobsługiwany w tym wariancie.
2. XLSX grupy 3 eksportuje się do dwóch stron o ~97,8% podobieństwie OCR; Qwen odczytuje wówczas drugi raz te same pola. **NIE NAPRAWIONE**. W eksperymencie `SinglePageSheets` XLSX utracił górną część dokumentu (PDF miał tylko ~593 znaków), a zmiany samych ustawień strony w XML nie usunęły duplikatu. Nie wprowadzono tych obejść do aplikacji.
3. Dotychczasowa sekwencyjna analiza stron przekroczyła 240 sekund dla 2-stronicowego PDF i JPEG. **NOWE:** ograniczona równoległość stron (2 strony na konwersję) z zachowaniem kolejności i anulowaniem przy błędach. Test jednostkowy przeszedł; test produkcyjny Qwena tej zmiany trwa lub wymaga weryfikacji.
4. Pseudopoprawny wynik mógł zawierać podpis jako edytowalne pole, CHECKBOX zamiast RADIO dla dokładnie jednego wyboru, oraz czytelne pola odpowiedzi zamienione na INFO_BLOCK. **NOWE:** korekty oparte wyłącznie na tekście i geometrii tego samego dokumentu w `source_semantics.py`.
5. Modele spłaszczały rzeczywiste tabele; 11 poprawnie policzonych pól nie oznaczało poprawnej siatki. **NOWE:** `source_layout.py` odtwarza wiersze i kolumny tylko przy powtarzalnym, potwierdzonym geometrycznie układzie; `CanonicalField` zachowuje box `region`.
6. Wybory oznaczone slash+gwiazdką i niespójne warunki `show_when` są zgłaszane przez `source_consistency_issues` jako problemy jakości zamiast cicho przechodzić. Pola bez potwierdzenia OCR blokują automatyczny status `ok`. Na stronach z widocznymi pustymi miejscami, ale zerową liczbą rozpoznanych pól, wymagany jest przegląd.

## Realne testy Qwena po pierwszych poprawkach (przed równoległością i geometrią)

Ślady: `/tmp/formflow-qwen-target/summary.json`, odpowiedzi JSON obok, manifest `/tmp/formflow-qwen-target-manifest.json`.

| Źródło | HTTP | Rzeczywista ocena |
|---|---:|---|
| niezależny `service.docx` | 200 | **PASS** kontrola semantyczna: 9 wejść, właściwe RADIO/CHECKBOX, podpis nieedytowalny |
| niezależny `roles.docx` | 200 | **FAIL:** 5 zamiast 6 wejść, zagubiono `Miejscowość i data`; mimo tego `generated` |
| niezależny `table.docx` | 200 | **FAIL:** 11 pól, ale siatka 3x3 spłaszczona; mimo tego `generated` |
| źródłowy PDF grupy 2 | 504 | **FAIL:** timeout 240 s |
| źródłowy JPEG grupy 2 | 504 | **FAIL:** timeout 240 s |
| źródłowy PNG grupy 4 | 200 | **REVIEW:** 11 pól; brak wyboru przez skreślenie, wykryty przez nową kontrolę |
| źródłowy XLSX grupy 3 | 200 | **FAIL/REVIEW:** 16 pól w dużej części powielonych przez zdublowany render źródłowych stron |

Wynik **1/3 niezależnych formularzy** spełniał wszystkie niezależne wymagania. Status HTTP200, `schema_valid` i `quality.ok` nie są miarą zgodności wizualnej. Poprawki po tej serii (tabela, źródłowy obszar odpowiedzi, równoległość) nie są jeszcze dowodem rozwiązania bez nowych prób.

## Narzędzia i testy

- `scripts/validate_forms.py`: manifest, SHA256, pojedynczy zapis odpowiedzi, limit współbieżności, bez niekontrolowanych retry.
- `scripts/evaluate_independent.py /tmp/formflow-refactor-validation/independent <result-dir>`: niezależne sprawdzanie liczby i typu pól, opcji, warunków, podpisów, statycznego tekstu i układu tabel (oczekiwania wyłącznie w fixture, nie w kodzie konwersji).
- 113 testów backendowych zaliczone po najnowszych zmianach; frontend: 20 testów, build przechodził. Testy nie zastępują walidacji rzeczywistych dokumentów.
- Oryginały audytu: `/tmp/formflow-audit-20261121/inputs/{1,2,3,4}/`. Wyniki bazowe: `/tmp/formflow-audit-20261121/results/`. Stary wynik GPT refaktoru: `/tmp/formflow-refactor-validation/matrix-v2/`.
- Prywatna instancja kandydująca: `http://127.0.0.1:18172`. Produkcja: `http://127.0.0.1:18171`.

## Kryteria ukończenia

- [ ] Naprawiona lub jawnie bezpiecznie nieobsługiwana utrata renderowania skomplikowanych DOCX (obecnie tylko odrzucanie).
- [ ] Brak duplikacji logicznych formularzy przy konwersji XLSX/ODS oraz brak zgubionych danych przy normalizacji.
- [ ] Brak timeoutów 240 s na problematycznych dokumentach przy rozsądnych kosztach.
- [ ] Niezależne fixture: 3/3 zgodne z oczekiwanymi polami, typami, opcjami, tabelą i warunkami.
- [ ] Pełna macierz 32 źródeł Qwen, porównanie semantyczne **każdego** wyniku z **jego własnym** źródłem, raport rozjazdów. Nie porównywać XLSX do DOCX jako oczekiwań.
- [ ] Stabilność przy kilku powtórzeniach i test nowych, nieznanych formularzy.
- [ ] Zielone testy backend, frontend, build, `git diff --check`, test importu do docelowego systemu COI.
- [ ] Dopiero po pozytywnych testach przegląd zmian, commit/PR i wdrożenie na 18171; zachować wcześniejsze limity RAM i prywatny Tailscale Serve.

**Uwaga:** nie przyjmować planu „przyspieszmy przez ucinanie OCR, pominięcie stron lub rekonstruowanie pól z innych wariantów”; takie obejście pozornie poprawia statystyki, ale psuje kompletność.

## Dalsze wyniki kontrolne i bezpieczeństwo (aktualizacja 23:18 CET)

- Aktualny zestaw: **113 testów backendowych**, **20 frontendowych** i build frontendu przeszły; `git diff --check` czysty.
- **Qwen, równoległość stron**: w `/tmp/formflow-qwen-parallel` PDF grupy 2 zakończył się HTTP200 w 107,72s zamiast timeoutu; **wynik niepoprawny**, bo cała pierwsza strona została zapisana jako bloki informacyjne (0 inputów), a na drugiej tylko 11 inputów. Pozostałe niezależne fixture: tabela 3x3 PASS (układ 2D z boksów), service 9 pól ale błędny warunek wyboru (FAIL), roles 8 zamiast 6 (FAIL). 1/3 semantycznie poprawny.
- **Niestabilność modelu bez jawnej temperatury**: w `/tmp/formflow-qwen-final-target` następnym przebiegu tego samego roles.docx uzyskano tylko 1 input, service.docx HTTP502 MODEL_OUTPUT_TRUNCATED, PDF HTTP504 CONVERSION_TIMEOUT. Dowodzi to, że same testy backendowe nie potwierdzają ani stabilności, ani kompletności.
- Dodatkowe zabezpieczenie źródła: `source_fidelity.mirrored_source_pages` powoduje HTTP422 dla niemal identycznych stron eksportu XLSX/ODS, co potwierdzono na wadliwym XLSX grupy 3 przez HTTP `/api/v1/forms/extract-preview`. Nie przywraca utraconego układu, ale eliminuje fałszywy sukces.
- Dodatkowy audyt: powtórzenia tej samej etykiety na konkretnej stronie w liczbie większej niż jej wystąpienia w OCR oznacza REVIEW, a nie automatyczną redukcję (dwie rzeczywiście odrębne osoby mogą mieć jednakowe etykiety). Warunki `show_when` otrzymują tylko jednoznaczne dopasowanie do realnie istniejącej opcji; w innym przypadku pozostają do weryfikacji.
- Przywrócono kontrolę próbkowania: `OPENROUTER_TEMPERATURE=0` w `.env.example` i kandydacie `compose.review.yaml` (tylko Qwen; nie mieszać z reasoning); test integracyjny adaptera potwierdza przesyłanie parametru 0. Jakości w OpenRouter nie wolno uznawać za poprawioną bez realnego powtarzalnego testu.
- Pełnej płatnej macierzy 32 Qwen **nie uruchamiano na wadliwym kandydacie**; byłoby to marnowaniem kredytów i nie świadczyłoby o zgodności. Produkcja na 18171 pozostaje bez zmian. Nie commitować/nie wdrażać w ramach tego raportu, dopóki główne defekty nie zostaną usunięte i zweryfikowane.

Najważniejszy blokujący problem jakości: model potrafi uznać oczywiste wizualne pola odpowiedzi za tekst statyczny, a następnie drugi audyt modelu potwierdza tę samą błędną interpretację. Następna naprawa musi ugruntować pola w rzeczywistych obszarach odpowiedzi / geometrii oryginału, nie tylko w drugim przebiegu tego samego LLM.


## Wynik testów Qwena z temperaturą 0 (23:20 CET)

W osobnych, kolejnych próbach tego samego fikcyjnego `service.docx` (`/tmp/formflow-qwen-temp0-{1,2}`) **obie konwersje HTTP200 wygenerowały 9 inputów**, bez niepowodzeń dostawcy (77,8s i 55,0s). Niezależny checker semantyczny zaliczył drugą próbę; pierwsza nie zachowała dosłownie powtórzonego słowa `ten ten` w statycznej informacji, chociaż `quality.ok=true`. Dodano `preserve_static_source`: przy mocnym dopasowaniu z OCR przywraca rzeczywiste źródłowe brzmienie (bez redakcji); potwierdzono offline na OCR **tego samego** testowego DOCX. Po wdrożeniu poprawki do kandydata **nie wykonano ponownego płatnego wywołania**.

Przy pozytywnym wyniku tylko takiego prostego dokumentu nie można stwierdzić, że Qwen działa powtarzalnie dla wszystkich typów formularzy. Źródłowy PDF 2-stronicowy, XLSX i złożony DOCX nadal nie przechodzą kryteriów. **113/113 testów backendowych**, frontend **20/20**, build OK. Nie wdrażać produkcji i nie twierdzić, że 32/32 pliki są naprawione.

## Docling Slim i naprawa wydruku Office (21.11.2026, po 23:40)

**Zakres:** kandydat 18172; produkcja 18171 (v1.3.0) pozostaje niezmieniona. Model: Qwen3-VL na OpenRouter, temperatura 0.

- Dodano **Docling Slim 2.151.1**, z obsługą Office/OpenDocument, bez PyTorch i dodatkowego OCR. Worker izolowany, Docling uruchamiany jako subprocess z limitem 25 s.
- Bezpośredni odczyt unikatowych komórek Docling z koordynatami zamiast Markdown; eksport Markdown powielał scalone komórki i produkował do 4,5 MB tekstu.
- **XLSX:** bezstratna modyfikacja samych ustawień wydruku OOXML wewnątrz kopii ZIP; pozostałe elementy archiwum (formuły, wartości, drawing/media) pozostają bez zmian.
- **ODS:** analogicznie zmiana tylko skalowania strony w styles.xml ODF. Nigdy nie nadpisujemy źródła.
- Wykryto wcześniejszy false positive: dwie strony XLSX nr 3 były poziomymi fragmentami arkusza, a nie duplikatami. Pypdf zwracał tekst spoza widzialnych stron. Mechanizm usuwania stron przez podobieństwo tekstu został wycofany.
- Nowy test PDFium fizycznych granic stron: dla błędnego XLSX nr 3 **892/2183 (40,86%) glifów poza stronami**, po prawidłowej normalizacji **0/1119**. Pełny obraz poprawionego PDF obejrzano i zweryfikowano wizualnie.
- Realne testy grupy 3: XLSX HTTP200 / 1 strona / 22 komórki źródłowe / 0 znaków poza stroną / około 10 s. ODS HTTP200 / 1 strona / 0 znaków poza stroną / około 7 s.
- Wykrycie istotnego przycięcia PDF po Office blokuje przekazanie do Qwena, zwraca 422. Nie utożsamiać 200 na extract-preview z wiernością końcowego COI JSON.
- **Pozostały problem:** DOCX grupy 2: Docling odzyskuje ~53,6% czterowyrazowych okien z OOXML (LO→PDF ~21,5%). Nadal 422, ponieważ nie można zagwarantować wierności obrazu i wszystkich pól.
- Testy backendowe 121/121 i frontendowe 20/20. Nadal konieczne niezależne testy semantyczne COI na Qwen, bez podmiany modelu.

Ślady poza repo, tylko na VPS: /tmp/formflow-docling-benchmark.json, /tmp/formflow-docling-office-matrix-before-fit-ods.json, /tmp/formflow-office-matrix-final.log i /tmp/formflow-live-final-3-{xlsx,ods}.json.

**Nie wdrażać produkcyjnie, zanim wszystkie kryteria COI i trudne DOCX nie przejdą weryfikacji.**

### Zakończenie macierzy normalizacji Office

Pełny ponowny przebieg 16 źródeł DOC/DOCX/XLSX/ODS (4 grupy) na instancji 18172, bez wywołań modelu: **15 HTTP200 i 1 HTTP422**. Udało się poprawić XLSX i ODS z grupy 3 bez wycinania części strony. Jedyny 422: grupa 2 DOCX, w którym LibreOffice traci zawartość textboxów. To wynik normalizacji, nie semantycznej zgodności końcowego COI.

Jeden płatny test Qwen3-VL na poprawionym XLSX z grupy 3: HTTP200 w 162,2 s; model qwen/qwen3-vl-30b-a3b-instruct, 8095 prompt tokens + 2946 completion tokens = 11041. Formularz zawiera 7 pól wejściowych, wybór pięciu opcji i warunek dla 'Inne'. Automatyczne quality.ok=true okazało się fałszywie optymistyczne: brak źródłowej informacji o podpisie. Dodano **niezależną od tematu formularza** kontrolę zachowania instrukcji podpisu jako bloku informacji; test jednostkowy potwierdza zgłaszanie brakującego podpisu. Tego samego płatnego testu nie powtarzano po ostatniej zmianie.

Rzeczywiste wyniki HTTP: /tmp/formflow-docling-office-matrix.json i /tmp/formflow-qwen-after-docling-real3.json (tylko VPS, poza repo). Nadal **nie** ma 32/32 potwierdzonych konwersji COI. Produkcja nienaruszona.
