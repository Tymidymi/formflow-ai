# FormFlow AI v1.3.0 — uniwersalne rozumienie dokumentów i tabele

**Wersja:** 1.3.0 · **Data:** 21.11.2026 · **Silnik:** OpenRouter Qwen3-VL (z zewnętrznym API za zgodą). Nie uruchamiamy lokalnego LLM.

## Cel i wykryta przyczyna regresji

Poprzedni pipeline wykonywał jeden prompt na cały dokument, po czym twarde reguły z `form_repair.py`, `semantic_quality.py`, `conditional_rules.py` dopisywały pola wzorowane na poprzednich przykładach. Wskutek tego obcy formularz drogowy otrzymał „Data rozpoczęcia wynajmu” i „Miejscowość budynku”. Stary quality gate sprawdzał ogólne słowa, nie kompletność. Prawidłowy COI JSON Schema nie oznacza wiernej konwersji.

**Od v1.3 produkcyjna ścieżka NIE importuje ani nie wywołuje przykład-specyficznych modułów.** Usunięto stare pliki i ich przykładowe testy. Syntetyczne demo nadal ma fikcyjnie zdefiniowane pola, ale nie jest używane do ekstrakcji plików użytkownika.

## Uniwersalny pipeline

1. **Lokalne OCR + render stron** — worker PDF rozpoznaje tekst i raster; obsługuje do 12 stron wymagających OCR i do 12 obrazów na dokument, zamiast dotychczas 4 i 3. Tekst do 100 000 znaków, z jawną flagą ucięcia.
2. **Podział na strony / fragmenty** — każda strona dostaje własny OCR i obraz. Dla plików Office bez informacji o stronach tekst dzielony jest na fragmenty bez obcinania całości. Nie jest to jeszcze wizualny render Office.
3. **Ogólne wykrywanie pól Qwen** — model rozpoznaje puste miejsca, wybory, rodzaje danych, nagłówki, etykiety i oryginalne cytaty. Nie może dopisywać cech obcych dokumentów.
4. **Wielokolumnowe wiersze w OCR** — parser identyfikuje powtarzające się *struktury* kolumn z kropkowanymi liniami i deterministycznie tworzy oddzielne kontrolki każdego wiersza. Bez znanych nazw pól/urzędów/typów wniosków.
5. **Niezależny model geometrii tabeli** — dla każdej strony z obrazem Qwen dostaje osobne zadanie: tylko określić liczbę wierszy, nazwy kolumn i grupy. Utracone przez OCR puste linie można odzyskać na podstawie widocznego układu; skrypt rozszerza je do fizycznych komórek. Algorytm weryfikuje liczbę powtarzających się wierszy w OCR i zachowuje identyfikowalne pochodzenie.
6. **Scalanie z deduplikacją** — miejsca już wyodrębnione z obrazu/OCR nie są ponownie dodawane z ogólnej odpowiedzi Qwen; porównujemy oryginalne cytaty i nazwy kolumn.
7. **Niezależna reanaliza** — gdy wykrytych pól jest znacząco mniej niż pustych miejsc (lub mało jest potwierdzeń źródłowych), druga analiza strony poprawia propozycję. Nie przywraca pól z żadnych szablonów.
8. **RODO i informacje** — klauzule prawne są czytelne, ale nieedytowalne. Wyraźne oświadczenia/zgody są odrębnie rozpoznawane z oryginału, a potencjalne duplikaty usuwane na podstawie tekstu.
9. **Mapowanie do COI** — ogólny eksporter zapisuje wiersze i kolumny siatki (x/y/cols); nie ucina automatycznie przy 80 polach. Przy bardzo dużych danych zwraca błąd zamiast niepostrzeżenie obciąć stronę/sekcję/pola.
10. **Quality gate i dowody** — raportuje liczbę pustych miejsc OCR, liczbę wejść, strony obejrzane i źródłowe fragmenty dla każdego pola. Duże braki blokują „OK”, mniejsze wątpliwości są prezentowane urzędnikowi. JSON Schema COI jest weryfikowany osobno.

## Gdzie w kodzie

- `apps/api/app/structured_extraction.py`: stronicowanie, niezależne modelowanie i kontrola.
- `apps/api/app/layout_slots.py`: wielokolumnowe puste miejsca i grupowanie wierszy.
- `apps/api/app/visual_tables.py`: obrazowa geometria tabeli i detekcja kolumn.
- `apps/api/app/legal_actions.py`: odróżnienie wymaganej odpowiedzi od statycznej klauzuli.
- `apps/api/app/document_zones.py`: uniwersalne oddzielanie tekstu informacyjnego.
- `apps/api/app/quality_gate.py`: kontrola kompletności.
- `apps/api/app/coi_builder.py`: siatka COI i jawne limity.
- `apps/frontend/preview.jsx`: dowody źródłowe i ostrzeżenia przy przeglądzie.

## Ocena jakości i ograniczenia

- Test regresyjny: zniekształcony OCR czterech grup × dwa wiersze × trzy kolumny — **24 źródłowe komórki bez zakodowanych nazw grup**.
- Druga niezależna próbka: rejestracja urządzenia z tabelą parametrów pomiarowych, niepowiązana semantycznie z wnioskiem drogowym.
- **Testy są potrzebne na oryginalnych binariach PDF/DOCX/XLSX/ODS**, z ręcznym ground truth: precyzja/recall, poprawne typy, kompletność, duplikaty. Dwie syntetyczne próbki nie wystarczą do zagwarantowania poprawności każdego dokumentu.
- Źródłowe cytaty są tekstowe; dokładne bounding boxes i podświetlenie pola na skanie pozostają do dalszej pracy.
- Ograniczenia skanów PDF: maks. 12 stron OCR/raster na konwersję (cały PDF może zawierać do 25 stron tekstowych); dłuższy skan może zostać odrzucony. Office: Docling tekst/tabele, bez pełnego renderu stron.
- Architektura wymaga kilku wywołań modelu na dokument, więc jest potencjalnie wolniejsza i droższa niż jednoprzebiegowy Qwen. Nie obiecujemy braku błędów modelu, ale **nie uzupełniamy braków przez ręcznie zakodowane formularze**.
- OpenRouter API jest wykorzystywane świadomie pomimo konkursowego zakazu zależności od zewnętrznych API — ryzyko bez zmian.

## Dodatkowe prace

- Pełny test benchmarkowy na oryginalnych plikach organizatorów i przypadkowych formularzach innych urzędów.
- Pełna analiza obrazowa Office, lepszy OCR w rozproszonych tabelach i rozpoznawanie położenia bounding boxes.
- Ścieżka zatwierdzania zmian oraz trwałego zapisu wersji zaakceptowanej przez urzędnika.
