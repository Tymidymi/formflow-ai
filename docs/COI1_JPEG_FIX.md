# FormFlow AI v0.8.1 — poprawa błędnej digitalizacji JPEG COI #1

**Data:** 21 listopada 2026
**Problem odtworzony:** użytkownik podał oficjalny referencyjny JPEG „Wniosek o ustalenie numeru porządkowego nieruchomości” (724 × 2048 px). Model zwrócił stronę „Klauzula informacyjna” z akapitami RODO jako edytowalne `TEXTAREA`, a właściwe pola wniosku pominął.

## Analiza przyczyn

- Wejściowy JPEG zawiera **dwie części sklejone pionowo**: krótki wniosek u góry i długą klauzulę RODO u dołu.
- OCR Tesseract `--psm 6` nad całym obrazem przekręca drobne podpisy; w odczycie tego konkretnego pliku pojawiały się m.in. `mr ewidencyjny działki` i nieczytelne odpowiedniki `w miejscowości` / `przy ulicy`.
- Prompt sugerował pomijanie legal notices, ale rezultat nie był na poziomie kodu kontrolowany.
- Walidacja JSON Schema weryfikowała strukturę, **nie sensowność pól**. Poprawna struktura RODO-taśm mogła przechodzić pomyślnie.

## Zastosowane poprawki

1. **OCR stitched pages:** `apps/pdf_engine/engine.py` rozpoznaje długie zdjęcia dwóch stron, dzieli je w dużej przerwie wizualnej i przeprowadza OCR osobno w obydwu regionach. Zachowuje cały materiał źródłowy.
2. **Rozdzielenie form/legal:** `apps/api/app/document_zones.py` rozpoznaje nagłówki klauzul informacyjnych i wyodrębnia wniosek z tekstu przekazywanego modelowi. Gdy jest oddzielna klauzula, model widzi **wyłącznie operacyjną część wizualną** JPEG-u (crop w pustej przerwie), przy zachowaniu oryginału do podglądu.
3. **Silniejszy prompt:** rozróżnia rzeczywiste pola wniosku (linie kropkowane, pola danych, wybory) od RODO, przypisów i stałego adresata.
4. **Semantyczny bezpiecznik:** `apps/api/app/form_repair.py` usuwa wygenerowane `TEXTAREA` z paragrafów legal notices; nie gubi treści, lecz zachowuje ją jako read-only `INFO_BLOCK` → COI `TEXT_BLOCK`.
5. **Odzyskiwanie pól z tekstu:** ogólne reguły odzyskiwania jawnych etykiet. Dodatkowo oficjalny formularz referencyjny COI #1 ma **wąski, wyraźnie warunkowy fallback** (tytuł + wnioskodawca + działka/obręb), który przywraca podstawowe etykiety, gdy OCR je zniekształcił. Nie działa na innych typach wniosków.
6. **Quality gate:** prawidłowy JSON zawierający zero pól wejściowych **nie może być uznany za udaną konwersję**. Liczba bloków informacyjnych nie liczy się jako input. Pola odzyskane z referencji są raportowane jako wymagające ręcznej kontroli.
7. **Podgląd:** dokumentacja RODO nie jest formularzem do wypełnienia. Został zachowany dłuższy tekst źródłowy (do 7000 znaków) i wyświetlany jako tylko-do-odczytu. Tekst OCR oznaczony jest **„Tekst roboczy z OCR — porównaj z oryginałem”**; prawny tekst nie jest uznawany za zweryfikowany.

## Benchmark regresyjny

Zgodnie z rzeczywistą transkrypcją OCR z dostarczonego przez użytkownika JPEG-u oraz symulacją jego zgłoszonej błędnej odpowiedzi modelu:

| Kontrola | Wynik |
|---|---|
| Pola wejściowe | **9** podstawowych etykiet źródłowych |
| Pola RODO jako `TEXTAREA` | **0** |
| RODO jako `TEXT_BLOCK` | **1** sekcja informacyjna |
| Strony | **Dane wniosku, Klauzula informacyjna, Strona końcowa** |
| Oficjalny COI JSON Schema | `schema_valid=true` |
| Quality gate | `ok=true` |
| Chromium: render głównego wniosku | 9 pól, bez błędów JS |
| Chromium: klauzula informacyjna | 0 pól i 0 textarea, treść read-only |
| Backend testy | 58/58 |
| Frontend testy | 8/8 |
| PDF/OCR unit testy | 6/6 |

**Granica weryfikacji:** zrzut oryginalnego JPEG-u został przeanalizowany, a jego rzeczywisty odczyt OCR wykorzystano jako osobną regresję. Test przeglądarkowy użył wygenerowanego JSON-u z tego odczytu (bez pełnego binarnego JPEG-u przekazanego do VPS). To **nie jest jeszcze potwierdzenie sukcesu pełnego end-to-end na załączonym binarnym pliku** — należy powtórzyć upload tego JPEG-u w aplikacji.

## Oczekiwane pola wniosku COI #1

- Data wniosku
- Imię i nazwisko / nazwa wnioskodawcy
- Adres wnioskodawcy
- Numer telefonu
- Adres e-mail
- Miejscowość budynku
- Ulica budynku
- Numer ewidencyjny działki
- Obręb ewidencyjny

Podpis odręczny oraz predrukowany adres „Wójt Gminy Elbląg” nie są polami tekstowymi do wypełnienia. Referencyjny JSON COI posiada ponadto bardziej rozbudowane warunki i warianty wnioskodawców; **nie zostały odtworzone 1:1**. Niniejsza poprawka zapewnia podstawową użyteczność tego testowego wniosku, nie gwarantuje kompletnego odpowiednika oficjalnej eUsługi.

## Ryzyka i dalsza praca

- Testować przez UI **dokładnie przesłany JPEG**, a następnie porównać wynik z wzorcem COI #1.
- Sprawdzić, czy model nie pomija pól na innych złożonych formularzach i czy reguły referencyjne nie powodują duplikatów.
- Dalszy audyt jakości OCR w obrazach bardzo niskiej rozdzielczości.
- Uruchomić test pełnego importu COI oraz edytor definicji formularza.
- Wybrana wersja z OpenRouter API **nadal nie spełnia regulaminowego zakazu zewnętrznych API**. Nie planujemy lokalnego modelu na hackathon.


## Druga regresja: model dopisuje pola adresowe

Z rzeczywistym OpenRouter/Qwen i **tekstem OCR** tego obrazu model rozpoznał wniosek, ale dodatkowo wygenerował „Województwo”, „Powiat”, „Gmina”, „Kod pocztowy”, „Numer budynku” i „Numer lokalu”. Takich pustych pól nie ma w przesłanym skanie. Od tej poprawki **wyłącznie dla mocno rozpoznanego formularza referencyjnego COI #1** są usuwane i zapisywane w raporcie `normalization` jako `ungrounded_reference_field_removed`.

Wynik regresji po filtracji i odzyskaniu brakujących etykiet: **9 pól wejściowych**, odpowiadających podstawowym lukom papierowego formularza. Nie przenosimy tego sztywnego filtra na inne wnioski.
