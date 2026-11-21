# FormFlow AI v0.7.0 — Quality Engine (21.11.2026)

## Zakres

- Warunkowa widoczność pól `SHOW` w formacie JSONata zgodnym ze składnią referencji COI #1/#5.
- Deterministyczna reguła dla świetlicy #4, gdy osobą odpowiedzialną jest ktoś inny niż wnioskodawca: wybór roli, widoczne dane tej osoby i osobny załącznik jej oświadczenia.
- Słowniki: obsługa konfiguracji `dictionaryName` dla `SELECT` z `Kraje`; dodatkowe nazwy tylko z oficjalnej listy dopuszczonych identyfikatorów. Wciąż brak importu pełnych danych słownikowych/TERYT.
- Pokrycie pól: ręcznie przygotowana, jawna lista referencyjna do testów #3/#4, wynik zawiera kompletność etykiet i poprawność typu.
- Alternatywny adapter Qwen przez Ollama (bez klucza i z prywatną siecią Docker), **mock-only**, niewdrożony na VPS.

## Benchmark regresyjny — odtworzenie zapisanych wyników Qwen

| Przypadek | Oczekiwane pola | Znalezione etykiety przed | Po | Poprawny typ przed | Po | Stan SHOW |
|---|---:|---:|---:|---:|---:|---:|
| COI #3 – Zaświadczenie | 11 | 10 | **11** | 10 | **11** | 0 |
| COI #4 – Świetlica | 18 | 15 | **18** | 14 | **18** | 2 |

Oba wynikowe JSON-y: `schema_valid=true`, `valid=true`, normalizacja idempotentna. Porównania wykonano na **zapisanych polach wygenerowanych uprzednio przez model z wyodrębnionych tekstów** COI #3/#4. To **nie jest pełny test oryginalnych binarnych plików PDF** i nie stanowi gwarancji pełnej semantycznej poprawności. Manualna lista nie jest oficjalną listą COI.

Dokładna lista oczekiwanych etykiet i typów w `apps/api/app/benchmark_gold.py`. Wyniki per-field w ignorowanym `data/private/benchmark_v07.json`.

## Warunki dynamiczne

Referencyjny JSON COI używa zapytań w postaci:

```json
{"type":"SHOW","query":"(\"Inna osoba\" in tabs['Dane' in title].questions['sekcja_0_0' in field.techName].field.repeatingSectionGrid['kto_jest_osoba_odpowiedzialna' in field.techName].field.__userAnswer)"}
```

W repozytorium zapytanie generowane jest dla rzeczywistych identyfikatorów i tytułów sekcji, a wartości pochodzą tylko z jawnych opcji. To **test statycznej konstrukcji**; poprawność wykonywania JSONata w docelowym rendererze COI nie została potwierdzona.

## Testy

- **46/46** testów FastAPI, eksportu, inferencji warunków, słownika `Kraje`, błędów i adaptera offline (mock).
- Dodatkowe **5/5** testów izolowanego silnika PDF/OCR (z v0.6).
- Wersja produkcyjna konkursowa wciąż wymaga prawdziwego offline Qwen i testu importera.

## Ograniczenia i ryzyka

1. Oryginalne binarne PDF-y #3/#4 dostępne są w materiałach rozmowy, ale nie zostały jeszcze przeniesione na VPS; wykonano lokalne potwierdzenie warstwy tekstowej (jedna strona w każdym) i replay na źródłowej treści.
2. Nie ma jeszcze interaktywnego renderera COI/JSON Forms, więc nie przetestowano działania `states` dla kliknięć użytkownika.
3. Heurystyczny benchmark pokrycia nie mierzy wiarygodnie precyzji na nowych formularzach.
4. Pozostały słowniki TERYT, numerów kierunkowych, zależności zaawansowane, stary DOC oraz benchmark pozostałych formularzy.
5. VPS nie ma widocznego GPU, przy około 0,6 GB dostępnej pamięci RAM nie uruchamialiśmy lokalnego modelu. Sprzęt z GPU nie był dostępny zdalnie.

## Następny krok

Przenieść oryginalne binarne formularze na urządzenie z dostępem do modelu, uruchomić pełny benchmark, sprawdzić JSONata w rendererze oraz wykonać próbę Ollama całkowicie bez Internetu.
