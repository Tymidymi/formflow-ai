# FormFlow — kontrolowany eksperyment: jeden przebieg Qwena (22.11.2026)

## Decyzja

**Wyłączono drugi, modelowy przebieg weryfikacji na każdej stronie.** Został jeden Qwen3-VL z wymuszonym kontraktem JSON, bez zmian modelu ani zależności. Następnie działają dotychczasowe **deterministyczne** korekty podpisu, źródłowych opcji, warunków i kopiowania tekstu, kontrola regionów, spójność ze źródłem, grounding oraz walidacja COI.

To **ograniczona poprawka zmierzonego defektu**, nie zapewnienie perfekcyjnej konwersji wszystkich formularzy.

## Metoda

Trzy z góry ustalone źródła: fikcyjny `service.docx`, rzeczywisty XLSX „Wniosek o wydanie zaświadczenia” (grupa 3), rzeczywisty PNG „Wniosek o wynajęcie świetlicy” (grupa 4). Na prywatnym kandydacie v1.4.0 przechwycono **raw JSON** pierwszej inwentaryzacji i drugiej weryfikacji w ramach **jednego** żądania przetwarzania danego dokumentu. Ten sam obraz i tekst strony, Qwen `qwen/qwen3-vl-30b-a3b-instruct`, temperatura `0`, bez GPT. Nie ufano listom zmian `audit.changes`; porównywano realne pola w JSON.

Pierwsze odpowiedzi odtworzono potem **offline**, przy użyciu dokładnie tych samych istniejących funkcji `page_inventory` / `canonical_form` / `coi_builder` / `coi_validation`, zastępując odpowiedź modelu zapamiętanym surowym JSON, bez dodatkowych płatnych zapytań.

## Wyniki A/B

| Dokument | Pierwszy Qwen (raw input) | Verifier (raw input) | Pierwszy + istniejące korekty (COI) | Ocena po korektach |
|---|---:|---:|---:|---|
| `service.docx` | 10 | **0** | **9** | PASS, 9/9, typy i warunek poprawne, COI schema valid |
| `Wniosek o wydanie zaświadczenia.xlsx` | 7 | 7 | 7 | COI schema valid; **needs_review**: brakuje instrukcji podpisu |
| `Wniosek o wynajęcie świetlicy.png` | 11 | **0** | 10 | COI schema valid; **needs_review**: nieodtworzony wybór „wynajem/użyczenie” |

W `service.docx` surowe 10 = 9 poprawnych wejść + podpis błędnie oznaczony jako edytowalny. **Już istniejący** normalizer prawidłowo konwertuje podpis na `INFO_BLOCK`, stąd wynik 9. Niezależny skrypt `scripts/evaluate_independent.py` nie znalazł niezgodności. W PNG pierwsza analiza podobnie wykryła 11, a detekcja podpisu pozostawiła 10.

**Verifier ani razu nie zwiększył liczby prawidłowych kontrolek** w badanych trzech przypadkach; w dwóch usunął wszystkie pola. W przypadku XLSX nie poprawił ani brakującego podpisu, ani innych danych. Nie jest to dowód, że drugi przebieg nigdy nie pomaga na innych źródłach; jest dowodem, że **w tej implementacji nie można mu ufać jako bezpiecznej rewizji**.

### Zużycie modelu

| Dokument | 1. przebieg: czas / tokeny | 2. przebieg: czas / tokeny |
|---|---:|---:|
| `service.docx` | 36,84 s / 3 856 | 59,76 s / 5 360 |
| XLSX | 35,98 s / 4 561 | 42,25 s / 5 795 |
| PNG | 74,62 s / 8 344 | 71,91 s / 11 051 |

Łącznie w tej próbce drugi przebieg zużył **22 206 z 38 967 tokenów (57,0%)** i **173,92 s** czasu inferencji. Jednoprzebiegowy pipeline usuwa ten koszt, ale end-to-end dochodzi jeszcze renderowanie i ekstrakcja.

## Wdrożona zmiana

- `apps/api/app/page_inventory.py`: jedno `generate(..., response_schema=INVENTORY_SCHEMA)` na fizyczną stronę; usunięto `VERIFIED_SCHEMA`, prompt `VERIFY` i drugi `generate`. Zero fallbacków i nowych bibliotek.
- Nie ruszano normalizacji Office, Tesseract, Docling, źródłowej weryfikacji, konwersji ani budowy COI.
- `rechecked_pages=0` oraz `independently_checked_pages=0` są **uczciwymi wartościami** (modelowy recheck nie zachodzi). `audit_changes` zawiera tylko korekty deterministyczne.
- Testy dostosowano do jednoetapowej analizy, bez usuwania kontroli brakujących regionów, źródłowych duplikatów, wyraźnej selekcji i brakujących podpisów.

## Ograniczenia i kryterium dalszej decyzji

**Nie robić kolejnego szerokiego refaktoru.** 122/122 testów backendowych oraz 20/20 frontendowych to potwierdzenie integralności kodu, nie dokładności 32 formularzy. Brak podpisu XLSX, brak wyboru przez skreślenie PNG, błędy tabel, 240 s timeout PDF oraz uszkodzony renderer złożonego DOCX to osobne otwarte problemy.

Kolejny eksperyment tylko jeśli potrzeba: jeden cel (np. wykrycie pustych wizualnych pól), maks. dwa porównywalne warianty z niezależnym scoringiem względem oryginału. Nie dodawać kolejnych warstw ratunkowych ani modeli bez dowodu poprawy.

## Prywatne dane testowe

Wyniki raw Qwen: `/tmp/formflow-ab-{service,xlsx,png}-raw.json`, replay końcowego COI: `/tmp/formflow-ab-{service,xlsx,png}-draft-coi.json`, logi: `/tmp/formflow-ab-{service,xlsx,png}.log`. Pliki na VPS, **nie commitować** oryginalnych dokumentów i rezultatów zawierających ich treść.

## Końcowy test API po zmianie

Trzy zwykłe wywołania `POST /api/v1/forms/convert?mode=diagnostic` na review **bez** modelowego rechecku:

| Plik | HTTP | Czas | Pola COI | Ocena |
|---|---:|---:|---:|---|
| `service.docx` | 200 | **40,03 s** | **9/9** | Niezależny checker **PASS**, JSON valid |
| `Wniosek o wydanie zaświadczenia.xlsx` | 200 | 67,77 s | **2 / ok. 7** | FAIL, dane wnioskodawcy jako INFO_BLOCK |
| `Wniosek o wynajęcie świetlicy.png` | 200 | 23,83 s | **0 / ok. 11** | FAIL, wszystkie kontrolki jako INFO_BLOCK |

**Interpretacja:** pierwotny weryfikator rzeczywiście niszczył dwa z trzech testowanych inwentarzy, ale **pierwszy przebieg Qwena również jest niestabilny**. Przy tym samym modelu, temp. 0 i tych samych źródłach XLSX i PNG ponownie zwróciły odpowiednio 2 i 0 kontrolek. Uproszczenie zmniejsza koszt i poprawiło service.docx, lecz **nie gwarantuje semantycznej poprawności**. Nie wdrażać na produkcję.

Ślady: `/tmp/formflow-singlepass-live/results/summary.json` i prywatne pliki odpowiedzi.

## Drugi i ostatni wariant: krótszy prompt po polsku

Wypróbowano **jeden** krótszy, bezpośredni prompt zamiast obecnego, na tym samym Qwenie, schemacie JSON i obrazach. Prompt zawierał ogólne przykłady pustej linii, daty, checkboxów, wyboru przez skreślenie, podpisu i statycznych informacji. Zmiana była uruchomiona **wyłącznie w procesie eksperymentalnym poza repo** — nie wdrożono jej do FormFlow.

| Plik | Liczba raw kontrolek | Błędy semantyczne |
|---|---:|---|
| XLSX | 11 | Cztery drukowane warianty zostały rozbite na **cztery jednoelementowe checkboxy** zamiast jednej grupy. Pole „Inne” utraciło warunek; podpis stał się edytowalny. |
| PNG | 11 | Cztery punkty podpisywanego oświadczenia zamieniono w fałszywą grupę CHECKBOX. Nadal pominięto miejscowość/datę i prawidłowe odwzorowanie wyboru „wynajem/użyczenie”. |

**Wariant odrzucono:** liczba pól wzrosła, lecz ocena znaczenia nadal jest nieprawidłowa. Nie poprawiano tego kolejnymi promptami ani wyjątkami. Wyniki: `/tmp/formflow-alt-{xlsx,png}.log` i wewnątrz izolowanego kontenera `/tmp/formflow-alt-in-container`; żadne treści źródłowe nie trafiły do Git.

### Ostateczna decyzja

**Zachować jeden przebieg Qwena z oryginalnym promptem** jako uproszczenie (usunięcie udokumentowanego destrukcyjnego rechecku), ale **nie uznawać go za rozwiązanie problemu jakości**. W trzech zwykłych testach API tylko jeden przypadek (`service.docx`) przeszedł pełną niezależną ocenę. Dwa pozostałe wykazały istotną niestabilność już w pierwszym przebiegu. Zatrzymać eksperymenty na tym etapie, nie wdrażać `main`/produkcji. Dalsze decyzje wymagają niezależnego benchmarku i rozstrzygnięcia ograniczeń Qwen/VLM zamiast kolejnych niekontrolowanych promptów.
