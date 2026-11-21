# Integracja z oficjalnym formatem COI — v0.4.0

## Materiały źródłowe

Użyto oryginalnego pliku `importowanyPlikJsonSchemat (1).json` z archiwum **Materiały do zadania dla Uczestników.zip**, przekazanego przez organizatora.

Zapisano **bez zmiany bajtów** w:
`apps/api/app/contracts/coi_form_schema.json`

SHA256: `6486974a7e6debb67675e879e5ae240b4903993015ed83c2a93dc9fd5785c7d2`

**Ważne:** prawa redystrybucji materiału COI poza repozytorium prywatnym nie są potwierdzone. Przed upublicznieniem repozytorium przejrzeć ten kontrakt i materiały konkursowe.

## Dwa poziomy walidacji

1. `schema_valid`: oryginalny schemat Draft 2020-12, bez zmian i własnych zaostrzeń.
2. `valid`: oryginalny schemat **oraz** reguły wyczytane z dokumentów COI:
   - tytuł, minimum dwie strony, MAIN + FINISH
   - pola w sekcjach, zakaz sekcji wewnątrz sekcji
   - identyfikatory pól i stron UUID, poprawne połączenia
   - połączenie pierwszej strony z FINISH, brak pól wejściowych w FINISH
   - typy komponentów i walidacji, rozmiary współrzędnych
   - ostrzeżenia o niejednoznacznościach wzorców

**Uwaga:** oficjalny schemat jest bardzo permissive: brak pól `required` nawet dla `title`, `tabs` czy `flow`. Sam wynik `schema_valid=true` nie oznacza poprawności biznesowej ani importowalności.

## Rozbieżności oficjalnych materiałów

| Obszar | Schemat / reguły | Przykłady COI | Podejście |
|---|---|---|---|
| Siatka sekcji | `repetingSectionGrid` (literówka w JSON Schema) | `repeatingSectionGrid` | Eksport używa pisowni z referencji, walidator rozpoznaje obie |
| FINISH | Reguły mówią o `INFO_SECTION` | FINISH zawiera `SECTION` z `TEXT_BLOCK` | Eksport naśladuje przykłady i zgłasza ostrzeżenie |
| ID przejść | Dokumentacja opisuje UUID | Referencja #5 ma krótkie identyfikatory, np. `a16ec` | Nie blokować importu; ostrzeżenie `LINK_ID_NON_UUID` |

## REST API

```http
POST /api/v1/forms/validate-json
Content-Type: application/json

{ "title": "...", "tabs": [...], "flow": { "links": [...] } }
```

Odpowiedź zawiera `schema_valid`, `valid`, tablice `errors` i `warnings` oraz metryki `summary`.

```http
POST /api/v1/forms/convert
Content-Type: multipart/form-data
X-External-AI-Consent: true

file=@wniosek.docx
```

**W trybie developerskim** odpowiedź HTTP 200 to bezpośrednio konfiguracja JSON COI. Po dodaniu `?mode=diagnostic` odpowiedź to obiekt `status, form, validation, model, usage` do prezentacji w UI.

Tryb OpenRouter to narzędzie developerskie, **nie spełnia wymagania konkursowego zakazującego zależności od zewnętrznych API**.

## Dodatkowe usprawnienia

- Stabilne UUID5 dla tego samego modelu semantycznego.
- Inferencja walidatorów PESEL, NIP, REGON, ZIP_CODE, EMAIL po precyzyjnym rozpoznaniu etykiety; wartości z zerami na początku pozostają tekstowe.
- Lokalna lekka ekstrakcja ODS (oparta na ZIP i XML; zabezpieczenie przed rozpakowaniem nadmiernych danych / `DOCTYPE` / `ENTITY`).
- Brak trwałego przechowywania wgranych dokumentów; publiczny podgląd wyłączony.

## Niewykonane

- Pełny parser Docling / konwersja starego DOC / pełny lokalny OCR.
- Lokalna inferencja z Open Weight model bez żadnego API.
- Test importu w prawdziwej aplikacji COI (nie otrzymaliśmy działającego importera).
- Kompleksowe porównanie jakości na referencjach #1 i #5 oraz oryginalnych formularzach #2–9.
- Słowniki, reguły warunkowe, JSON Forms i prezentacja konkursowa.

## Test jakości modelu na treści COI #3 (bez oryginalnego układu dokumentu)

- Qwen3-VL-8B: tylko jedno pole (podpis) — znaczna utrata danych mimo poprawnego schematu.
- Qwen3-VL-30B-A3B: 9 pól, PESEL, telefon, adres, cel i warianty zaświadczenia; schema_valid=true i valid=true.
- Model developerski w lokalnym pliku .env: qwen/qwen3-vl-30b-a3b-instruct.
- Quality gate ostrzega o brakujących polach i blokuje raw JSON dla bardzo ubogich wyników. Jest to heurystyka, nie pomiar trafności względem oryginalnego pliku.
