# Lokalny Qwen — przygotowanie konkurencyjnego trybu offline

## Stan

- Działa **mockowany** adapter `FORMFLOW_AI_PROVIDER=ollama`, model `qwen3-vl:8b-instruct` przez natywne `http://ollama:11434/api/chat`.
- Nie potrzeba klucza OpenRouter, obrazy do modelu są przesyłane bezpośrednio wewnątrz lokalnej sieci Docker.
- Szablon w `compose.ollama.yaml`; usługa Ollama ma wyłącznie prywatną sieć `extractor_private` i brak publicznego portu.
- **NIE przeprowadzono jeszcze realnej inferencji offline.** Samo istnienie adaptera nie oznacza zgodności z zadaniem konkursowym.

## Dlaczego nie na VPS?

Podczas pracy VPS miał ~11 GiB RAM, z czego około 0,6 GiB dostępne; brak urządzenia GPU. Qwen3-VL 8B w wariancie kwantyzowanym pobiera około 6 GB modelu, plus pamięć robocza. Uruchomienie modelu na obecnym VPS groziłoby destabilizacją pozostałych usług.

Komputer z RTX 3070 może być punktem startowym, ale najpierw trzeba potwierdzić dostępność urządzenia i VRAM. Jeśli Qwen3-VL-8B nie mieści się w pamięci, należy porównać wariant Qwen3-VL-4B z jakością 8B i 30B.

## Procedura (na osobnym, autoryzowanym hostcie)

1. Zainstalować Ollama na hostcie z GPU i uruchomić `ollama pull qwen3-vl:8b-instruct` **przed wyłączeniem Internetu**.
2. Przetestować `ollama run qwen3-vl:8b-instruct` lokalnie z rzeczywistym dokumentem.
3. Podłączyć adapter do prywatnego adresu kontenera `http://ollama:11434`, bez dostępu publicznego.
4. Zatrzymać OpenRouter i usunąć klucz z konfiguracji konkursowej.
5. Wykonać pełny benchmark i test w odciętej sieci. Nie uznawać wyniku za gotowy przed tym krokiem.
6. Przeprowadzić audyt licencji wersji modeli, Ollama i całego drzewa zależności (bez licencji copyleft wymagających ujawnienia kodu).

Dostawca Ollama publikuje Qwen3-VL 8B w bibliotece modeli oraz podaje licencję Apache 2.0; zgodność wszystkich transytywnych komponentów wymaga dalszego audytu.

## Ważna różnica

`compose.dev.yaml` = OpenRouter, tylko programowanie i testy. `compose.ollama.yaml` = przygotowanie do trybu offline, lecz **nie uruchamiamy go na aktualnym VPS**.
