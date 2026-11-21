# FormFlow AI v1.1.0 — multimodal PDF + źródłowa weryfikacja pól

**Data:** 21 listopada 2026
**Stan:** rozwiązanie wdrożone na prywatnym VPS pod `https://vibe.tail075c6f.ts.net:9466/`.
**Model:** OpenRouter / `qwen/qwen3-vl-30b-a3b-instruct` (zewnętrzne API za świadomą zgodą).

## Co odkryliśmy

Przed wdrożeniem `FORMFLOW_PDF_VISION=false` w działającym kontenerze. PDF-y przetwarzane były głównie przez ekstrakcję layoutu pypdf lub Tesseract; Qwen nie otrzymywał obrazu stron. JPG/PNG już wcześniej przekazywały obraz. DOCX/XLSX/ODS nadal dostarczają tekst i strukturę tabel przez Docling Office, **bez obrazu strony**.

Sama wizja nie daje automatycznie wyższej jakości: może odczytać cztery oddzielne checkboxy, ale również błędnie utworzyć pola z informacji o opłacie lub połączyć kilka oświadczeń. Poprawność COI JSON Schema nie oznacza poprawności znaczeniowej.

## Co działa od v1.1.0

- **PDF Vision domyślnie ON:** renderowanie maksymalnie **trzech pierwszych stron** PDF do oddzielnych obrazów JPEG, z zachowaniem tekstu OCR/layout.
- **Jednoczesna analiza tekstu i obrazu** przez Qwen3-VL: prompt prosi o bezpośrednią analizę wyglądu dokumentu, tabel, checkboxów i drobnych podpisów.
- **Jawna kompletność:** `vision_page_numbers`, `model_images_sent`, `vision_incomplete`, `vision_rejected_pages`, `vision_requested` w diagnostyce. Dłuższy PDF oznaczamy jako wymagający dodatkowej kontroli; nie twierdzimy, że wszystkie strony były widziane.
- **Kontrolowany test A/B:** parametr `vision=off|on|auto` w `POST /api/v1/forms/convert?mode=diagnostic`. Domyślny `auto` korzysta z flagi Compose.
- **Evidence report:** plik `field_grounding.py` szuka dla pól potwierdzenia w liniach źródłowego OCR i numery stron. Brak dopasowania daje `requires_visual_review`, a nie automatyczne usunięcie.
- **Wsparcie urzędnika:** w kroku 2 można rozwinąć listę pytań, których OCR nie potwierdził jednoznacznie. Jeśli nie obejmujemy wszystkich stron PDF obrazowo, interfejs o tym ostrzega.
- **Odróżnienie treści niewypełnialnej:** końcowe `INFORMACJE:`, `POUCZENIE`, `OBJAŚNIENIA` identyfikujemy jako osobny informacyjny `TEXT_BLOCK`, nie pola `TEXTAREA`; zachowujemy tekst źródłowy do podglądu.
- **Dodatkowe korekty:** papierowe `/podpis/` nie jest edytowalnym inputem; po źródłowym `oświadczam, że:` numerowane oświadczenia można odzyskać jako osobne checkboxy, jeśli model połączy je w jedno.
- **Konserwatywne automatyczne naprawy:** nie ma automatycznego usuwania pola wyłącznie dlatego, że OCR go nie odczytał — obraz może zawierać prawdziwy podpis.

## Zasady bezpieczeństwa i limity

- Qwen otrzymuje najwyżej 3 obrazy i do 18 000 znaków tekstu; granice są raportowane, ale **wielostronicowa pełna analiza wszystkich obrazów** nie jest jeszcze wdrożona.
- OCR skanowanego PDF nadal ma osobny limit czterech stron wymagających OCR.
- Source grounding na razie wskazuje **najlepiej dopasowaną linię tekstu**, nie geometryczne bounding boxes. To priorytet do ręcznego sprawdzenia, nie niezależna wzrokowa weryfikacja.
- Tryb A/B wykorzystuje ten sam model, ale wynik jest probabilistyczny. Jeden lub dwa przebiegi nie dają statystycznej gwarancji poprawy.
- DOCX/ODS/XLSX nadal bez wizualnego renderu. Docling Office to ekstrakcja tekstu/struktur tabel; nie zastępuje prawdziwego wyglądu strony.
- Zewnętrzny OpenRouter pozostaje **niezgodny** z konkursowym zakazem zewnętrznych API. Decyzja zespołu: API w zgłoszeniu; bez lokalnego LLM.
- Binarne dokumenty i surowe wyniki benchmarku są w `data/private` i nie są dodawane do GitHuba.

## Benchmark A/B — COI #3 i #4

Jako dane porównawcze wykorzystano **PDF-y obrazowe odtworzone z prawdziwego tekstu OCR dostarczonych formularzy konkursowych**, a nie ich oryginalne pliki binarne. Pliki `coi_3_ab_scan.pdf` i `coi_4_ab_scan.pdf` wygenerowano dla testu, by wymusić OCR i dać Qwen taki sam układ tekstowy w obu trybach.

| Przypadek | OCR-only | OCR + Vision |
|---|---:|---:|
| COI #3: automatyczne dopasowanie etykiet z referencji | 7/11 | 6/11 |
| COI #3: koszt OpenRouter na przebieg | $0.00057345 | $0.00085485 |
| COI #4: automatyczne dopasowanie etykiet z referencji | 12/18 | 13/18 |
| COI #4: koszt OpenRouter na przebieg | $0.00048255 | $0.0010684 |

**Uwaga metodologiczna:** dopasowanie etykiet jest automatyczną, niedoskonałą heurystyką z uwzględnieniem opcji checkboxów. To **nie jest ręcznie zatwierdzony precision/recall**. COI #3 z Vision poprawnie oddzielił cztery wybory, lecz wprowadził pola z tekstu o opłacie. COI #4 z Vision zauważył zakres dat, ale błędnie połączył cztery odrębne oświadczenia. Wynik Vision jest mieszany, więc poza obrazami potrzebne są dodatkowe zabezpieczenia semantyczne.

## Benchmark po dodaniu reguł semantycznych

Po włączeniu separacji końcowych informacji i korekty podpisów przeprowadzono kolejne zapytania OpenRouter na tych samych odtworzonych skanach:

- **COI #3:** model generował 7 kontrolek wejściowych (jedną listę z pięcioma opcjami oraz sześć innych pól). Sekcja o opłacie została zachowana jako osobny, **nieedytowalny blok informacyjny**, a podpis odręczny usunięty z pytań. Schemat COI przechodzi walidację. Automatyczne dopasowanie referencji: **6/11**; porównanie nie rozstrzyga, czy jedna lista jest semantycznie równoważna osobnym checkboxom.
- **COI #4:** po rozszerzeniu parsera o wielowierszowe numerowane oświadczenia Qwen + postprocesor przywrócił **cztery oddzielne potwierdzenia**, podczas gdy wcześniejszy przebieg z Vision używał jednego zbiorczego checkboxa. Oficjalny JSON Schema i reguły COI: **valid=true**. Automatyczne dopasowanie referencji: **13/18**, przed dodatkową korektą przykładu w nawiasie.
- Dodatkowa regresja usuwa wtórne pole „(rodzaj uroczystości, np. wesele…)” tylko wtedy, gdy istnieje już osobne pytanie o cel wynajęcia. Nie przeprowadzono osobnego płatnego testu Qwen po tej pojedynczej korekcie, lecz objęto ją testem automatycznym.

Wniosek: udało się usunąć **konkretne znane klasy błędów**, ale pełnego wzrostu precision/recall na oryginalnych dokumentach **nie potwierdzono**. Nie traktować testu syntetycznie odtworzonego PDF jako wyniku końcowego benchmarku konkursowego.

## Testy automatyczne

- Backend FastAPI: **70/70** testów (`pytest`), w tym testy przełączania Vision, podziału treści informacyjnych, obowiązkowych zgód i odzyskiwania oświadczeń.
- PDF/OCR worker: **7/7** testów, w tym maksymalnie 3 obrazy stron oraz jawne oznaczanie nieobjętej strony 4.
- Frontend React: **16/16** testów, pakowanie do lokalnych JS/CSS.
- Testy jakości modelu w prywatnym katalogu `data/private/benchmark_v11_*`; benchmark może zostać odtworzony skryptem `scripts/benchmark_multimodal.py`.

## Następny etap jakościowy

1. Pełny benchmark na **oryginalnych binarnych** plikach COI #2–#9 (nie na rekonstrukcjach), z ręcznym wykazem expected fields, precision, recall, typów i obowiązkowości.
2. Dostarczenie wizualnej analizy **wszystkich** stron przez chunking modeli i deduplikację wyników, zamiast jedynie trzech obrazów; ograniczenie kosztu, czasu i halucynacji.
3. Office-to-image dla DOCX/XLSX/ODS z zachowaniem układu stron; do oceny biblioteki i wpływ na zasoby VPS.
4. Niezależna weryfikacja obrazowa, geolokalizacja pól (bounding boxes) i wizualne podświetlenie odpowiednika pola w oryginale; obecny OCR evidence report jest tylko pierwszym krokiem.

**Nie dodawaliśmy lokalnego modelu LLM.**
