# FormFlow — zamrożony audyt end-to-end (22.11.2026)

## Cel i zakres

**Audyt bez zmian w kodzie aplikacji i bez nowych bibliotek.** Kandydat v1.4.0 na prywatnym `127.0.0.1:18172`, gałąź `refactor/source-page-pipeline`, model **`qwen/qwen3-vl-30b-a3b-instruct`**, temperatura `0`. Instancja produkcyjna v1.3.0 (18171) nie była zmieniana. Wszystkie osiem wyników pochodzi z jednego przebiegu na tych samych plikach, bez retry.

Trzy fikcyjne dokumenty mają niezależne oczekiwania z `apps/api/tests/fixtures/create_independent.py` i prywatnego `expected.json`. Pięć prawdziwych dokumentów zestawiono z **własnymi oryginałami**, ich widocznymi polami i treściami, nie z wersjami w innych formatach. Kontrola oryginałów obejmowała render wizualny PDF, PNG i odczyt arkusza XLSX. Stosowano ocenę poprawności semantycznej i kompletności, nie sam HTTP.

## Twarde wyniki

| Źródło | HTTP | Czas | Wejścia COI | Ocena względem źródła | Główny problem |
|---|---:|---:|---:|---|---|
| `service.docx` (niezależny) | 200 | 84,17 s | 0 / 9 | FAIL | 9 kontrolek zamieniono w bloki statyczne, brak wyborów, daty i warunku |
| `roles.docx` (niezależny) | 200 | 39,76 s | 1 / 6 | FAIL | Nazwiska obu ról, adres i data urodzenia jako bloki statyczne |
| `table.docx` (niezależny) | 502 | 47,17 s | — / 11 | FAIL | `MODEL_SCHEMA_INVALID`, brak wyniku COI |
| Zwrot opłaty skarbowej, **PDF** (2 strony) | 504 | 240,03 s | — | FAIL | `CONVERSION_TIMEOUT`; widoczne prostokątne pola PDF nie zostały przekształcone |
| Wydanie zaświadczenia, **XLSX** | 200 | 112,41 s | 2 / ok. 7 | FAIL | Dane wnioskodawcy jako tekst informacyjny, brak grupy wyboru i zależności `Inne` |
| Wydanie zaświadczenia, **ODS** | 200 | 61,77 s | 13 / ok. 8 | FAIL | Każda opcja wyboru jako osobne TEXT_FIELD, podpis edytowalny |
| Wynajęcie świetlicy, **PNG** | 200 | 99,09 s | 3 / ok. 11 | FAIL | Brak tożsamości, dat i terminów, brak `wynajem/użyczenie` |
| Numer porządkowy nieruchomości, **DOC** | 200 | 71,86 s | 7 / ok. 8 | FAIL | Powielone pole wnioskodawcy, zlane lokalizacja/ulica i działka/obręb; `quality.ok=true` |

**Podsumowanie:** 8/8 konwersji wywołanych; 6 HTTP200, 1 HTTP502, 1 HTTP504; **0/8 merytorycznie poprawnych** (w ramach zdefiniowanych kryteriów). Spośród sześciu HTTP200: pięć miało `quality.ok=false`, **jedna była fałszywie pozytywna**. Checker 3 niezależnych dokumentów: **0/3 PASS**.

## Weryfikacja, że to nie wyłącznie problem formatu Office

- Dwa niezależne DOCX z widocznymi miejscami na odpowiedzi zwróciły 0 i 1 pole; model błędnie używał `INFO_BLOCK`/`TEXT_BLOCK`.
- Prawdziwy PNG idzie bezpośrednio na analizę obrazu, bez LibreOffice i Docling, a mimo to pominięto większość odpowiedzi. OCR w tym skanie również pomijał niektóre etykiety, jednak model otrzymał obraz źródłowy.
- Dwustronicowy PDF jest oryginalny i nie przechodzi przez konwersję Office. Mimo wyraźnie widocznych kontrolek nie ukończył się w 240 s.
- XLSX i ODS przeszły wcześniej lokalny odczyt i test granic PDFium (1 widoczna strona, 0 wektorowych znaków poza stroną). Mimo tego COI ma błędne typy i braki.
- **Nie porównuj pól XLSX i ODS między sobą:** ODS zawiera datę, której w tej wersji XLSX nie ma.

## Ważne ustalenia o modelu i weryfikatorze

1. **Niestabilna wierność między przebiegami/wersjami:** dokładnie ten sam SHA-256 `service.docx` w dwóch wcześniejszych próbach Qwena z temperaturą 0 dawał po 9 wejść, a obecny audyt — zero. Ponieważ w międzyczasie zmieniał się pipeline, wynik **nie dowodzi samodzielnie losowości modelu**; konieczne porównanie tej samej wersji, promptu i obrazów.
2. **Deklaracje audytu AI są niewiarygodne:** w XLSX `audit.changes` twierdzi, że pola wnioskodawcy przerobiono na TEXT_FIELD i utworzono grupę wyboru, podczas gdy wygenerowany COI nadal zawiera te pozycje jako TEXT_BLOCK. Tekst modelowego audytu ≠ faktyczna modyfikacja danych.
3. **Kontrakt nie zawsze jest spełniony:** niezależny dokument tabelaryczny zakończył się `MODEL_SCHEMA_INVALID` (HTTP502).
4. **Wydajność modelu:** model pracuje nad dwoma wezwaniami na stronę (draft i verifier), co przy złożonych plikach prowadzi do 240-sekundowego limitu. Nie ma dowodu, że drugi modelowy przebieg poprawia jakość.
5. **Quality gate nie wystarcza:** w pięciu przypadkach HTTP200 wykrył problem, ale przypadek DOC z `quality.ok=true` nadal miał istotne pominięcia i duplikat. Weryfikacja musi porównywać wynik z fizycznym źródłem.

## Ranking przyczyn i decyzje

**P1 — Semantyka pól i weryfikacja LLM (dominująca).** Nieodróżnianie tekstu statycznego od wejścia, brak grup wyboru, źle interpretowany podpis. Występuje w DOCX, XLSX, ODS i PNG. Najpierw rozdzielić ocenę **draft** i **verified**, zamiast rozbudowywać OCR.

**P2 — Strukturalne błędy modelu.** `MODEL_SCHEMA_INVALID` dla tabeli. Potrzebna izolacja: czy zawodzi draft, czy verified, a nie zmiana wszystkich komponentów naraz.

**P3 — Czas.** Realny PDF przekracza 240 s przy podwójnej analizie. Ustal, czy druga analiza wnosi korzyść większą niż koszt i opóźnienie.

**P4 — Renderowanie Office.** Znany trudny DOCX grupy 2 nadal ma 422 i jest osobnym problemem; **nie** był przedmiotem ośmiu testów end-to-end. To aktualnie nie jest argument za kolejną biblioteką do renderowania.

### Jeden ograniczony eksperyment następny

Na **dwóch jednostronicowych przykładach (`service.docx`, XLSX z grupy 3)** oraz **PNG** porównać na *identycznej wersji modelu i tych samych danych* wynik po pierwszym przebiegu (draft) z finalnym wynikiem verified. Traktować oryginał jako arbitra, a `audit.changes` tylko jako twierdzenie do sprawdzenia. Maksymalnie **2 warianty** i zero nowych zależności.

- Jeśli draft jest lepszy od verified, uprościć do **jednego** przebiegu Qwena plus deterministyczna walidacja źródłowa.
- Jeśli oba przebiegi błędnie klasyfikują odpowiedzi, testować **jedną** zmianę w reprezentacji inputów/prompcie/schemacie, nie dokładać kolejnych warstw ratunkowych.
- Po eksperymencie ponowić te same 3 przypadki; wymagane mierzalne odtworzenie pól, typów, wyborów i warunków. Gdy brak poprawy po 2 wariantach — zawęzić zakres produktu, nie rozwijać Frankensteina.

Nie uznawać pełnego 32/32 ani produkcyjnej gotowości na podstawie 122 zielonych testów jednostkowych. **Nie wdrażać na `main` / produkcję** bez audytu końcowego COI.

## Powtarzalność i dane

Logika testowa: `scripts/validate_forms.py`, `scripts/evaluate_independent.py`. Wyniki i pliki prywatne pozostają na VPS w `/tmp/formflow-eight-audit-20261122/{manifest.json,source_checklist.json,results/summary.json,results/*.json}`. Te dokumenty oraz pełne odpowiedzi nie są commitowane do Git. Brak zmian w kodzie w ramach tego audytu. Repo zawiera tylko ten raport.
