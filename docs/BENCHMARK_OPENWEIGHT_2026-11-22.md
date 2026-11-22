# FormFlow — benchmark modeli open-weight przez OpenRouter (22.11.2026)

## Decyzja

**Nie zmieniać modelu produkcyjnego na podstawie tego benchmarku.** Żaden przetestowany kandydat nie przeszedł obu rzeczywistych formularzy bez istotnego defektu. **Qwen3-VL-235B** daje wyraźnie lepszy odczyt formularza świetlicy, ale w dwóch pozostałych testach błędnie buduje zależności warunkowe. Dotychczasowy **Qwen3-VL-30B** pozostaje jedynym z porównanych modeli z pełnym wynikiem PASS na niezależnym syntetycznym formularzu `service.docx`; jednak jego powtarzalność na prawdziwych dokumentach jest słaba.

To badanie dotyczy **wyłącznie eksperymentów deweloperskich** przez OpenRouter. Zewnętrzne API jest sprzeczne z wymogiem COI opisanym w `docs/DECISION_API_SUBMISSION.md` i nie można przedstawiać tej konfiguracji jako zgodnej z regulaminem konkursowym.

## Metoda

- Użyto kandydata v1.4 z gałęzi `refactor/source-page-pipeline` (commit bazowy `38ad223`), nie zmieniono produkcji v1.3.
- Trzy identyczne migawki wejściowe, przygotowane **raz** istniejącym ekstraktorem FormFlow: XLSX „Wniosek o wydanie zaświadczenia” (1 strona), PNG „Wniosek o wynajęcie świetlicy” (1 strona) i fikcyjny `service.docx` (1 strona).
- Ten sam OCR, ten sam obraz strony, ten sam prompt `page_inventory.PROMPT`, ten sam `INVENTORY_SCHEMA`, temperatura `0`, jedna analiza modelowa na stronę, te same deterministyczne normalizatory i builder COI.
- Odrębna kontrola treści źródłowych: **13** prostych punktów dla XLSX oraz **16** dla PNG (pola wnioskodawcy, wyborów, dat, oświadczeń, podpisów, warunków, regionów). Skala jest **pomocnicza**, nie zastępuje pełnego wizualnego audytu człowieka. Brak wyniku API oznacza niezaliczony test, a nie zero poprawnie odczytanych pól.
- Dla `service.docx` użyto istniejącego niezależnego `scripts/evaluate_independent.py` z 9 polami, typami, opcjami, warunkiem i dosłowną instrukcją.
- Wszystkie surowe odpowiedzi i obrazy przechowywane **tylko tymczasowo** wewnątrz review-containera `/tmp/formflow-openweight-benchmark/`, poza Git. Do repo trafiają wyłącznie wyniki zbiorcze.

## Wyniki

| Model (ID OpenRouter) | XLSX: liczba pól / punkty | PNG: liczba pól / punkty | `service.docx` | Uwagi |
|---|---|---|---|---|
| `qwen/qwen3-vl-30b-a3b-instruct` | 7 / **12 z 13** | 10 / **12 z 16** | **9/9 PASS** (52,59 s) | XLSX: nieodtworzony podpis; PNG: brak wyboru „wynajem/użyczenie”, brak daty zakończenia, fałszywy CHECKBOX dla podpisywanego oświadczenia |
| `qwen/qwen3-vl-235b-a22b-instruct` | 7 / **10 z 13** | 10 / **15 z 16** | **9/9 FAIL** (31,71 s) | XLSX: zdublowany identyfikator wyboru i błędny warunek; PNG: zachował 2 daty i statyczne oświadczenie, ale pominął wybór przez skreślenie; `service`: zepsuł warunek `SHOW` |
| `mistralai/mistral-small-3.2-24b-instruct` | 7 / **11 z 13** | 6 / **10 z 16** | Nie badano | XLSX: brak warunku „inne” i podpisu; PNG: pominięte dane wnioskodawcy i wybór |
| `nvidia/nemotron-3.5-super-vl` | 7 / **11 z 13** | **Błąd MODEL_RESPONSE_FORMAT** | Nie badano | XLSX: brak regionów odpowiedzi dla wszystkich 7 pól i warunek bez istniejącego wyboru; wynik semantycznie niepoprawny mimo JSON COI valid |
| `qwen/qwen3.5-122b-a10b` | **HTTP 400** | **HTTP 400** | Nie badano | Dostawcy OpenRouter (SiliconFlow/Alibaba) odrzucili złożony kontrakt `response_format.json_schema.schema` („None is not of type object, boolean”). Próba zamiany nullable `anyOf` na `type: [...,null]` nie pomogła. To **błąd kompatybilności schematu/dostawcy**, a nie pomiar jakości modelu |
| `qwen/qwen3.5-27b` | Brak odpowiedzi w ponad 2 min | Nie wykonano | Nie badano | Przerwano niekończące się oczekiwanie na pierwszy wynik |
| `google/gemma-3-27b-it` | Brak zakończonego wyniku w ponad 4 min | Nieukończony | Nie badano | Przerwano test z powodu czasu; nie wyciągać wniosków o semantycznej jakości modelu |

**Ważne:** wszystkie zakończone odpowiedzi realnych formularzy miały `quality.ok = false`, mimo że struktura wygenerowanego COI przechodziła walidację. Liczba pól ani poprawność JSON **nie są** miarą zgodności ze źródłem. Prawdziwa niezawodność wymaga większej próby i ręcznie zatwierdzonych referencji.

### Czasy dwóch realnych dokumentów (model inference, bez ponownej ekstrakcji)

- Qwen3-VL-30B: **23,56 s + 44,08 s**
- Qwen3-VL-235B: **16,27 s + 74,98 s**
- Mistral Small 3.2: **22,10 s + 76,33 s**
- Nemotron 3.5 Super VL: **11,75 s + 16,44 s** (drugie wywołanie zakończone błędem odpowiedzi)
- Qwen3.5-122B: ok. 1,3 s na odrzucenie żądania przez dostawcę

Czasy pojedynczych żądań zależą też od obciążenia OpenRouter i nie są gwarantowaną latencją modelu.

## Wnioski z porównania jakości

1. **Nie wybierać modelu po liczbie wygenerowanych pól.** Duży Qwen rozpoznał w PNG bardziej poprawną strukturę, ale zgubił kluczowy wybór; mały Qwen wykrył wiele pól, lecz zamienił oświadczenie prawne w fałszywą grupę opcjonalnych checkboxów.
2. **Problemy z warunkami są krytyczne dla COI.** Qwen235 i Nemotron potrafiły stworzyć poprawny składniowo JSON, w którym `show_when` odwołuje się do nieistniejącej opcji/identyfikatora.
3. **Stabilność jest osobnym problemem.** Ten sam Qwen30 przy temperaturze 0 dał wcześniej 2 i 0 pól na XLSX/PNG, a w tym teście odpowiednio 7 i 10. Powtarzalność bez pełnego gold-setu nie została zapewniona.
4. **Qwen3.5-122B nie dostał uczciwego testu jakości.** Problem z implementacją strict JSON Schema u obecnych dostawców wymagałby osobnego zadania integracyjnego. Nie mieszać takiej zmiany z wydaniem MVP.
5. **Nie zmieniać działającej aplikacji na podstawie jednego dobrego przypadku.** Zachować audyt, ręczną kontrolę każdego formularza, walidację JSON i edytor, uczciwie prezentować ograniczenia.

## Dalsza decyzja MVP

**Zamrozić model i pipeline.** Jeśli termin oddania jest blisko, nie powiększać liczby fallbacków ani nie wprowadzać ensemble. Na demo używać syntetycznego `service.docx`, który przeszedł niezależny test, a realne formularze oznaczać jako wymagające ręcznej korekty. Przed ewentualną zmianą modelu wymagać PASS dla reprezentatywnej, niezależnie ocenianej paczki rzeczywistych źródeł, w tym wyborów i tabel. Osobno uzyskać rozstrzygnięcie ograniczenia COI dotyczącego zewnętrznych API.

**Repo nie zawiera w tym raporcie obrazów źródeł, danych osobowych, surowych odpowiedzi modelu ani kluczy API.**
