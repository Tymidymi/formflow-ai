# Handoff FormFlow — 21.11.2026

## Cel i autoryzacja

Użytkownik autoryzował wdrożenie planu naprawy po audycie 32 plików. Chce uniwersalnego, prostego przepływu i dobrego projektu repo, bez wyjątków dla nazw formularzy/oczekiwanych pytań. Obecnie poprosił o przerwanie i przekazanie pracy następnemu agentowi. Nie kontynuować płatnych testów w tej sesji. Konto OpenRouter zostało doładowane przez użytkownika; wcześniejsze HTTP 402 nie jest już aktualną blokadą. Nie prosić ponownie o zgodę na zwykłe prace/wdrożenie. Nie używać subagentów bez wyraźnej prośby.

## Repo i środowisko

- VPS przez Remote Desktop Commander, pojedyncze urządzenie.
- Repo `/home/tymot/projects/formflow-ai`, branch `refactor/source-page-pipeline`, origin `https://github.com/Tymidymi/formflow-ai.git`.
- Zmiany NIE są zacommitowane ani wypchnięte. Punkt wyjścia main: `b01c2264a21d1a970baca882d7e37d3c694b1978`.
- Przeczytać `/home/tymot/AGENTS.md`; polecenia jako codexremote przez `/home/tymot/run-as-codexremote.sh` zgodnie z lokalnymi instrukcjami.
- Produkcja `formflow-ai`, loopback 18171, prywatny URL `https://vibe.tail075c6f.ts.net:9466` pozostaje starą wersją; NIE podmieniono produkcji.
- Kandydat `formflow-review`, loopback 18172. Trzy usługi. Najnowszy obraz API ma 1.4.0, Office LibreOffice 25.2.3.2 na trixie. Kandydat skonfigurowany na `openai/gpt-5.2`, reasoning low. TEJ konfiguracji modelu jeszcze nie przetestowano płatnym wywołaniem.
- Przed naszą pracą były niezacommitowane limity RAM: compose.dev.yaml 384m→768m, compose.docling.yaml i compose.pdf.yaml 384m→1536m. Zachować; nie przypisywać ich sobie ani nie stage'ować przypadkowo. compose.docling ma również NASZE zmiany obrazu/tmpfs, więc stage tylko właściwe hunki.
- `.env` zawiera sekrety, nie drukować ani commitować. Nie zmieniono jego rzeczywistego klucza/modelu. Model kandydata nadpisuje compose.review.yaml.

## Co zaimplementowano

1. Jeden Office worker DOC/DOCX/XLSX/ODS→PDF przez LibreOffice, osobne profile, blokada jednego procesu, makra wyłączone, timeout75s, kill grupy procesów, sprzątanie. Docling/Antiword usunięte z obrazu.
2. `extraction_router.py`: Office i obrazy normalizowane do PDF, potem jeden PDF/OCR worker. Długie obrazy dzielone na fizyczne strony; tekst i obraz mają wspólną tożsamość. Jawne błędy workerów. Ostatnio usunięto też stary `document_text.py` i jego obcinający treść fallback; brak workera teraz503.
3. `source_pages.py`: mapowanie fizycznych stron, bez niezależnego chunkowania tekstu i powtarzania obrazu całej strony.
4. `page_inventory.py`: dokładnie dwa wywołania/stronę, draft + kompletna zweryfikowana wersja. Schematy JSON, regiony/bbox, pochodzenie, opcje, warunki, raport zmian i nierozwiązanych problemów. INFO_BLOCK ma osobny mały kontrakt. Wspólny kontrakt papier→web, podpis jest informacją, statyczne deklaracje nie są opcjami.
5. `ai_provider.py` i Ollama: jawny response_schema oraz lokalna walidacja JSON Schema. Brak automatycznego retry/zwiększania6500 tokenów po ucięciu. Żadnego dopinania nawiasów/akceptowania niepełnego JSON. Ostatnio usunięto temperature, dodano opcjonalne OPENROUTER_REASONING_EFFORT, żeby wspierać modele reasoning bez per-modelowych gałęzi.
6. `main.py`: deadline240s obejmuje całe zadanie, max2 konwersje, anulowanie po rozłączeniu. Status nie udaje sukcesu tylko dlatego, że wykonano audyt. Metadane model/provider są obecnie zbierane z adaptera (ostatnia poprawka).
7. Eksporter: telefon/e-mail jako alternatywny kontakt nie dostaje walidacji EMAIL, synonim „adres poczty elektronicznej” ją dostaje. Pozostały kontrakt COI zachowany.
8. Usunięto stare kaskady: structured_extraction, page_recovery, source_slot_audit, visual_tables, visual_choices, layout_slots, source_region_reconcile, document_zones, quality_gate, legal_actions; osobne legacy_doc i xlsx_sparse. Wycofano testy samych usuniętych algorytmów, zachowano/migrowano kontrakty.
9. `scripts/validate_forms.py`: manifest, SHA256, odpowiedzi i summary, ograniczona współbieżność, zatrzymanie kolejki po błędzie dostawcy, brak płatnych retry. Dodano sprawdzanie health PRZED kolejką i niezerowy exit dla HTTP!=200.
10. README, ARCHITECTURE, licencje, CI, przykładowa konfiguracja zaktualizowane. `REFACTOR_VALIDATION.md` NADAL ma nieaktualny tekst o blokadzie402 i wymaga przepisania na aktualne wyniki.

## Testy i dowody

- Ostatni wykonany backend: **81 passed**, log `/tmp/formflow-refactor-tests.log`. Po ostatnich drobnych zmianach reasoning/prompt należy uruchomić ponownie.
- Frontend wcześniej **20 passed**, build przeszedł. Logi `/tmp/formflow-refactor-frontend.log` i `/tmp/formflow-refactor-frontend-build.log`.
- Venv `/tmp/formflow-test-venv`, Black25.1.0. `PYTHONPATH=apps/api /tmp/formflow-test-venv/bin/python -m pytest -q apps/api/tests`.
- 32/32 lokalne ekstrakcje poprawnie zakończone, `/tmp/formflow-refactor-validation/extractions/{group}_{ext}.json`. ODS1 spadł z100000 do4774 znaków, bez obcięcia. To NIE dowodzi kompletności renderera.
- Pełna płatna macierz **32/32 HTTP200**, model **openai/gpt-4.1**, starszy LO7.4: `/tmp/formflow-refactor-validation/matrix-v2/summary.json`, odpowiedzi obok; log `matrix-v2.log`. **29 quality.ok=true,3 false, ALE są błędne pozytywne oceny. Nie nazywać tego 29/32 poprawnych.**
- Liczby wejść wg formatów:
  - Grupa1: wszystkie8 formatów po8 pól; przejrzano etykiety/typy, data przywrócona, kontakt bez EMAIL, klauzula readonly.
  - Grupa2: doc24, docx15, jpeg26, jpg26, ods24, pdf25, png24, xlsx24. DOCX ginie cała druga strona; JPEG/JPG tworzą dwa pola na jeden kod pocztowy (dla obu adresów). PDF25 wymaga sprawdzenia, czy to tylko rozdzielenie dwóch niezależnych załączników, czy błąd. Kwota jest konsekwentnie TEXT_FIELD zamiast NUMBER.
  - Grupa3: doc/jpeg/docx/jpg/pdf/png po8; ods9 i quality false; xlsx7 i quality false. XLSX renderuje2 strony, brak daty na początku, audyt mylnie żąda na stronie2 pól z pierwszej. Sprawdzić źródło XLSX i normalizację.
  - Grupa4: doc/docx/jpeg/pdf/png10, jpg9, ods/xlsx11. Często ginie wybór wynajem/użyczenie ze skreśleniem; PDF ma quality false. Właściwy wykaz semantyczny wygląda na11, ale sprawdzić źródła, nie poprawiać licznikiem.
- Oddzielne INFO schema rozwiązało generowanie tysięcy spacji do limitu6500 na klauzulach. Wcześniejsze response length były naprawdę niezamknięte, nie wolno ich akceptować/naprawiać. Probe v2 uzyskał poprawny pełny inwentarz8+klauzula. Tymczasowe `/tmp/formflow-probe.py` przechwytuje response body bez kluczy; nie wdrażać go do aplikacji.
- Wygenerowano **2** niezależne fikcyjne DOCX: service (oczekiwane9 pól), roles (6 pól,2 strony). Generator `apps/api/tests/fixtures/create_independent.py`; źródła i expected/manifest `/tmp/formflow-refactor-validation/independent`. Jeszcze NIE wykonano konwersji. Zapowiedziany trzeci test tabeli nie został dodany — dokończyć przed deklaracją testów niezależnych.


## Nierozwiązany renderer DOCX

DOCX2 zawiera130 textboxów i850 DrawingML anchors; druga strona po LO jest praktycznie pusta (OCR ©), choć `word/document.xml` zawiera pełną treść. LO25.2 na trixie **NIE naprawił** problemu: `/tmp/formflow-refactor-validation/2_docx-trixie.json` nadal2213 znaków, druga strona1 znak. To nie jest błąd modelu.

Dwie próby DIAGNOSTYCZNE poza repo też nie naprawiły: wybór wszystkich mc:Fallback (`compat-docx.docx`,845 branchy), nadanie unikalnych wp:docPr i v:shape ID (`unique-ids.docx`). Nie wprowadzono tych modyfikacji do kodu. docPr IDs już były unikalne;780 VML shape miałoid=shape_0. Nie rozwijać kaskady takich eksperymentów w produkcji.

Potrzebna jest wiarygodna weryfikacja utraty zawartości na granicy normalizacji (np. oryginalny tekst OOXML kontra wynik renderowania) i poprawne wsparcie złożonego DOCX albo jawne odrzucenie z informacją. Taki guard JESZCZE NIE został zaimplementowany. Sam audyt obrazu pustej strony nie wykryje, że renderer zgubił treść.

## Dane

- Oryginały: `/tmp/formflow-audit-20261121/inputs/{1,2,3,4}/` (32 źródła + materiały referencyjne, referencji nie traktować jakoformularzy).
- Bazowe wyniki przed refaktorem: `/tmp/formflow-audit-20261121/results/{group}_{ext}.json`.
- Nowy manifest32: `/tmp/formflow-refactor-validation/manifest.json`.
- Nie używać starego ad hoc run.py do nowych testów: brak circuit breakera. Używać skryptu w repo.
- Stare audytowe raporty w Library: FormFlow_audyt_i_plan_naprawy.md `libfile_88cf19c9c3808191b4955011ad113fa5`, porównanieHTML `libfile_e036d59b27b8819183ad0a464b4b12e7`, ZIPwyników `libfile_e345addd38148191a7407aec8b0bd624`.

## Dalsza praca

1. Przeczytać aktualne diff i powyższe wyniki. Nie uruchamiać od razu kolejnej pełnej płatnej macierzy.
2. Rozwiązać źródłową utratę DOCX/normalizacji i wykrywanie niekompletnego renderu. Bez pól z nazw wniosków, bez kopiowania z PDF innego wariantu!
3. Małe kontrolne próbki nowej konfiguracji gpt-5.2 (aktualnie kandydat). Zweryfikować opcje, zgrupowanie kodów, daty, kwoty, warunki, statyczne deklaracje. Nie wystarczyHTTP200/qualitytrue.
4. Niezależne formularze + kilka powtórzeń stabilności. Potem32 źródła; rzeczywiste porównanieinput/output.
5. Przepisać docs/REFACTOR_VALIDATION.md i README na uczciwy finalny stan; obecne402 jest historyczne.
6. Testy backend/frontend/build, git diff --check. Dopiero wtedy commit/push/PR i podmiana produkcji, zachowując prywatny dostęp i preexistingRAMzmiany. Nie wdrażać teraz kandydata jako „naprawionego”.
7. Import do docelowego systemu COI nadal niepotwierdzony.

Kandydat:
```bash
FORMFLOW_HOST_PORT=18172 docker compose -p formflow-review -f compose.yaml -f compose.dev.yaml -f compose.docling.yaml -f compose.pdf.yaml -f compose.review.yaml --profile docling --profile pdf up -d --build
```
Poczekać na health przed kolejką. Głównego portu18171 nie zmieniać do pozytywnej walidacji. W chwili przekazania brak aktywnych płatnych procesów testowych. Ostatni proces1473798 to lokalne extract-preview dwóch plików, bez wywołań AI.
