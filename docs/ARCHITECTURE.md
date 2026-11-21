# Architektura konwersji 1.4

## Granice odpowiedzialności

| Moduł | Odpowiedzialność |
|---|---|
| `uploads.py` | Granice rozmiaru, formatów i MIME |
| `extraction_router.py` | Jeden przepływ stron PDF, struktura Docling i niezależny test widoczności |
| `apps/extractor/app.py` | Office → PDF, izolacja i bounded subprocess Docling Slim |
| `apps/extractor/xlsx_print.py`, `ods_print.py` | Bezstratna zmiana tylko ustawień wydruku XML w kopiach XLSX/ODS |
| `apps/extractor/office_structure.py` | Niezależny parser Docling Slim; źródłowe komórki bez duplikacji z Markdown |
| `render_fidelity.py` | PDFium: kontrola wektorowego tekstu poza widocznym obszarem strony |
| `apps/pdf_engine` | Tekst, OCR i obrazy fizycznych stron |
| `source_pages.py` | Zgodne identyfikatory stron i przypisanie tekstu do obrazu |
| `page_inventory.py` | Wspólny kontrakt, pojedyncza inwentaryzacja Qwena, regiony i deterministyczna kontrola |
| `ai_provider.py`, `ollama_provider.py` | Transport do modelu i jawny schemat odpowiedzi |
| `canonical_form.py` | Typowany model semantyczny, bez tworzenia nowych pytań |
| `coi_builder.py`, `coi_conditions.py` | Deterministyczny eksport i zależności odpowiedzi |
| `coi_validation.py` | Schemat COI i reguły strukturalne |
| `main.py` | HTTP, zgoda na model, limit całego zadania i anulowanie |
| `apps/frontend/adapter.mjs` | Interpretacja eksportu w podglądzie JSON Forms |

## Stałe zasady

1. Tekst i obraz opisują tę samą stronę. Nie dzielimy tekstu na części z powtórzonym obrazem całej strony.
2. **Jedno** wywołanie Qwena na stronę. Nie ma drugiego modelowego weryfikatora, kaskady odzyskiwania ani nieograniczonego retry.
3. Ilość pól nie zastępuje ich wierności źródłu. Zmiana usuwa destrukcyjny weryfikator, ale nie gwarantuje kompletności.
4. Wspólne schematy JSON określają pola, opcje, warunki, informacje i regiony. Transport nie odgaduje schematu z luźnej odpowiedzi.
5. Każdy edytowalny obszar ma stronę i identyfikator regionu. Współrzędne modelu muszą być skończone i znormalizowane. Mocno pokrywające się regiony trafiają do oceny.
6. Stałe teksty i podpisy pozostają informacjami. Zwykłe pole tekstowe nie realizuje podpisania dokumentu.
7. Deterministyczne korekty oraz testy spójności z tekstem źródłowym zapisują zmiany i nierozwiązane rozbieżności. Brak wizualnej weryfikacji, ucięcie, brak strony i wykryte problemy blokują pozytywną ocenę. Ocena automatyczna może nadal przeoczyć błędy semantyczne.
8. Całe zadanie ma 240 s, także podczas oczekiwania na wolne miejsce. Rozłączenie klienta propaguje anulowanie; Office ma dodatkowy limit procesu 75 s.
9. API nie zapisuje prywatnej treści do logów. Wynik diagnostyczny zwraca użytkownikowi regiony, deterministyczne zmiany, problemy i zużycie tokenów.

## Office

DOC/DOCX/XLSX/ODS mają wspólny renderer LibreOffice i oddzielny parser Docling Slim (bez modeli OCR). XLSX oraz ODS mają ujednoliconą szerokość wydruku poprzez zmianę samych metadanych strony wewnątrz kopii ZIP OOXML/ODF. Pozostawiamy niezmienione wartości, formuły, rysunki i pozostałe elementy archiwum. Scalone komórki są odczytywane z unikatowych obiektów źródłowych Docling, a nie powielanych slotów Markdown. LibreOffice działa bez interfejsu, w prywatnej sieci bez wyjścia do Internetu, z osobnym profilem i wyłączonym wykonywaniem makr. Po timeout proces jest kończony wraz z grupą procesów.

Renderowanie Office może różnić się od Microsoft Office, szczególnie dla rysunków i pól tekstowych. Niezależny test PDFium wykrywa znaki poza fizyczną stroną (nie są widoczne na obrazie, chociaż pypdf je odczytuje) i blokuje materialne obcięcie. Dla DOCX porównujemy także zawartość OOXML ze źródłowym tekstem PDF. To nadal nie gwarantuje pełnej zgodności wizualnej ani poprawności semantycznej COI.

## Usunięte mechanizmy

Usunięto moduły kaskady odzyskiwania: `structured_extraction`, `page_recovery`, `source_slot_audit`, `visual_tables`, `visual_choices`, `layout_slots`, `source_region_reconcile`, `document_zones`, `quality_gate`, `legal_actions`. Usunięto też osobne adaptery Office `legacy_doc` i `xlsx_sparse`.

Testy samych usuniętych algorytmów zostały wycofane. Pozostają testy kontraktów API, eksportu, typów, warunków, transportu, granic procesu i nowego przepływu. Rzeczywistą regresję jakości mierzy się ponownymi konwersjami źródeł z audytu, a nie liczbą starych testów.
