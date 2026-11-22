# FormFlow — testowanie i znane ograniczenia

## Automatyczne testy kodu

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api python -m pytest -q -p no:cacheprovider apps/api/tests

npm --prefix apps/frontend ci
npm --prefix apps/frontend test
npm --prefix apps/frontend run build
```

Weryfikacja 22.11.2026 (kandydat v1.4, nowszy interfejs): **122 testy Python przeszły**, **20 testów JS przeszło**, **frontend zbudowany**. To weryfikuje kontrakty, przypadki brzegowe i zgodność kodu; nie jest dowodem dokładnego odwzorowania dowolnego dokumentu źródłowego.

## Test integracyjny

1. `GET /healthz`, `GET /readyz` i `GET /api/v1/capabilities`.
2. `GET /api/v1/demo/convert` — fikcyjny formularz, bez zewnętrznych wywołań.
3. `POST /api/v1/forms/extract-preview` — plik DOCX, kontrola liczby stron i tekstu PDF.
4. `POST /api/v1/forms/convert?mode=diagnostic` — ten sam plik, kontrola `form`, `validation`, `grounding`, `quality`.
5. Porównanie pól, typów, etykiet, opcji i warunków ze źródłem, a nie tylko liczby pól.
6. Edycja w UI, potwierdzenie weryfikacji, pobranie JSON, test `POST /api/v1/forms/validate-json`.
7. Test formatów PDF, skan JPG/PNG, DOC/DOCX oraz XLSX/ODS, w tym dokumentów wielostronicowych. Przetwarzanie nowych formularzy jest częścią demonstracji jury.

Niezależna kontrola `service.docx`: `scripts/evaluate_independent.py`. Powtarzalne serię diagnostyczne: `scripts/validate_forms.py`. Dane wejściowe konkursowe i wynikowe zawierające treść dokumentów **nie** powinny trafić do publicznego GitHub.

## Znane ograniczenia i problemy

- Multimodalne Qwen3-VL potrafi nie rozpoznać pola, zmienić je w blok statyczny albo błędnie zinterpretować wybór przez skreślenie. Przy temperaturze 0 wyniki mogą być różne.
- Drugi modelowy weryfikator został usunięty: w testach potrafił skasować prawidłowo rozpoznane pola. Aktualny pipeline opiera się na jednym przebiegu i kontrolach deterministycznych.
- Tabele, rysunki i układ dokumentów Office mogą nie przetrwać renderowania w 100%; materialna utrata tekstu powoduje błąd 422.
- Warunki `SHOW` wymagają istniejącego pola i opcji. Formalnie poprawny JSON COI nie gwarantuje poprawnej logiki formularza.
- `quality.ok` i `schema_valid` są heurystykami/strukturą. **Nie są** pomiarem accuracy względem ground truth.
- Wersja demonstracyjna nie została sprawdzona z rzeczywistym importerem COI. Dostępność importerów i rzeczywiste API pozostają poza zakresem.
- Port Tailscale jest prywatny; sama aplikacja nie ma wieloużytkownikowego uwierzytelnienia. Wymaga kontroli dostępu na poziomie infrastruktury.
- Lokalny model Ollama może działać na mocniejszym hoście, ale nie ma potwierdzonego wyniku e2e na obecnej maszynie.

## Kryteria gotowości do konkursu

- Kompletny plik README, instrukcja uruchomienia Docker, opis REST API i architektury.
- Działające `/healthz` oraz **faktyczna** analiza jednego kontrolnego dokumentu, nie tylko gotowość.
- Schemat COI przechodzi walidację; wynik jest weryfikowany z oryginałem.
- Frontend pokazuje źródło, podgląd eUsługi, edycję i eksport.
- Materiały konkursowe (PDF prezentacji do 10 slajdów, JSON wynikowe, film do 3 minut i kod) są osobnymi składnikami zgłoszenia; nie stanowią części danych testowych repozytorium.

## Ocena jakości modeli

Przeprowadzono mały benchmark kilku otwartych modeli VLM, także Qwen3-VL-30B/235B, Mistral Small i Nemotron. **Żaden nie wygrał bezbłędnie na wszystkich rzeczywistych formularzach**. Nie zmieniać produkcyjnego modelu bez nowej, niezależnie zweryfikowanej próby. Historyczne pliki przebiegów i dokumenty źródłowe pozostają poza repozytorium.

**Dalsza praca:** zwiększać reprezentatywny zestaw testowy z poprawnymi odpowiedziami (pola, opcje, warunki, strony), nie tworzyć wyjątku w kodzie dla konkretnego formularza.
