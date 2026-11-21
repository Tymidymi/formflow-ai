# FormFlow AI v0.6.0 — PDF Layout + OCR (21.11.2026)

## Architektura uruchomiona na VPS

```
Tailscale HTTPS :9466
  → FastAPI v0.6.0 :18171 (loopback)
       → Docling Office :8001 (private network)   DOCX/XLSX/ODS
       → PDF Engine :8002 (private network)       PDF/PNG/JPG/JPEG
            → pypdf — ekstrakcja z zachowaniem wierszy
            → pypdfium2 — lokalne renderowanie PDF
            → Tesseract pol+eng — OCR stron bez warstwy tekstowej
       → OpenRouter Qwen3-VL-30B-A3B (WYŁĄCZNIE DEV)
       → Semantic normalization → COI JSON → official JSON Schema
```

PDF Engine nie ma wystawionych portów ani dostępu do Internetu. Limit 384 MiB RAM, użytkownik non-root, read-only filesystem, ograniczenia procesów. Dane wejściowe nie są zapisywane trwale.

## Funkcjonalność

- [x] PDF z tekstem: lokalna ekstrakcja układu wierszy przez `pypdf`, normalizacja znaczników wyboru.
- [x] PDF skanowany: render przez PDFium i OCR Tesseract po polsku/angielsku.
- [x] PNG/JPG/JPEG: lokalny OCR; obraz może też zostać przekazany do Qwen w trybie developerskim za świadomą zgodą.
- [x] Metadane: liczba stron, użycie OCR, źródło tekstu na poziomie strony, ograniczenie długości wejścia, liczba stron podglądu.
- [x] `POST /api/v1/forms/extract-preview`: lokalny podgląd tekstu i metadanych — bez OpenRouter.
- [x] `POST /api/v1/forms/convert`: JSON COI; raport diagnostyczny przez `?mode=diagnostic`.
- [x] Korekty semantyczne oparte wyłącznie na jawnych etykietach w dokumencie: data, PESEL, dane osobowe, wynajem/użyczenie, zakres dat, liczba uczestników; papierowy podpis jest pomijany jako pole tekstowe. Lista poprawek w `normalization`.

## Wyniki sprawdzone

| Test | Wynik |
|---|---|
| Izolowany PDF Engine: tekstowy PDF, OCR PNG, skan PDF, uszkodzony PDF i limit stron | **5/5** |
| FastAPI i integracje (mock, bez zewnętrznych API) | **40/40** |
| Syntetyczny skan PDF → lokalny OCR → Qwen → COI JSON | **HTTP 200, schema_valid=true, quality=true, 5 pól wejściowych** |
| Wcześniejsze modele semantyczne na źródłowym tekście COI #3 | 11 pól przed i po normalizacji; poprawnie odzyskana data, usunięty papierowy podpis |
| Wcześniejsze modele semantyczne na źródłowym tekście COI #4 | 17 → 18 pól; oddzielona data, wybór wynajem/użyczenie, pominięty papierowy podpis |
| Oryginalne binarne PDF-y COI #3/#4 na lokalnym stanowisku analitycznym | PDF #3: 1 strona, 2293 znaki tekstu z layoutem; PDF #4: 1 strona, 2739 znaków |
| Wersje PNG formularzy #3/#4 OCR Tesseract na lokalnym stanowisku | #3: 1234 znaki; #4: 1448 znaków; zachowane kluczowe etykiety (z błędami OCR) |

**Ważne:** Ostatnie dwa testy zostały wykonane lokalnie na oryginalnych binarnych materiałach COI, a nie na VPS. Benchmark end-to-end z oryginalnymi binarnymi PDF-ami (zamiast syntetycznych lub tekstu źródłowego) **pozostaje do wykonania**. Dane konkursowe nie są commitowane do GitHuba.

## Ograniczenia i zabezpieczenia

- Maksymalnie 25 stron PDF, 4 strony wymagające OCR, 15 MiB uploadu.
- Maksymalnie 18 tys. znaków na żądanie modelu; obcięcie jest raportowane i **blokuje surowy eksport** COI jako niekompletny.
- OCR może pomijać pola lub błędnie odczytywać symbole; `schema_valid=true` nie gwarantuje jakości merytorycznej.
- Podgląd stron przez Qwen (obrazy PDF) jest konfigurowalny `FORMFLOW_PDF_VISION=true`; domyślnie wyłączony, aby zachować oszczędność RAM/transferu.
- Nadal brak pełnego pakietu Docling PDF/layout z modelami AI. Używamy lekkiego pypdf + pypdfium2 + Tesseract, ponieważ VPS ma ograniczoną pamięć.
- Nadal brak starszego .doc, słowników/warunków, JSON Forms oraz **konkursowego lokalnego LLM** (OpenRouter tylko podczas developmentu).
- Tesseract: Apache-2.0; pypdfium2: Apache-2.0/BSD-3-Clause; pełny audyt pozostałych transytywnych licencji wciąż wymagany.

## Polecenia operacyjne

```bash
cd /home/tymot/projects/formflow-ai

# Development stack z PDF/OCR:
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build

# Kontrola stanu:
docker ps --filter name=formflow
curl -fsS http://127.0.0.1:18171/healthz
docker stats --no-stream formflow-ai-api-1 formflow-ai-docling-office-1 formflow-ai-pdf-engine-1

# Podgląd lokalnej ekstrakcji bez użycia AI:
curl -F file=@form.pdf http://127.0.0.1:18171/api/v1/forms/extract-preview

# Awaryjne wyłączenie workera:
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf stop pdf-engine
```

## Następne zadania

1. Sprawdzić rzeczywiste oryginalne pliki źródłowe w pełnym pipeline (PDF/JPG/PNG).
2. Ocenić kompletność pól i poprawność typów względem ręcznie zweryfikowanych wzorców, nie tylko schematu JSON.
3. Przetestować warunki oraz słowniki COI i dodać preview JSON Forms.
4. Wdrożyć offline Qwen na dedykowanej maszynie GPU — wymagane dla finalnej zgodności konkursowej.
