# FormFlow AI – architektura (etap 1)

> **Nota aktualizacyjna:** diagram poniżej opisuje dawny etap 1 i nie odzwierciedla całej v0.7.0. **Wersja zgłoszeniowa korzysta z OpenRouter API, a nie lokalnego LLM**. Nie jest zgodna z zakazem zewnętrznych API COI. [Aktualna decyzja](DECISION_API_SUBMISSION.md), [tasklista](TASKLIST.md).


```text
Browser --Tailscale Serve HTTPS :9466--> 127.0.0.1:18171 --Docker--> FastAPI
                                                     |-- / (minimalny interfejs)
                                                     |-- /api/v1/forms/inspect (walidacja uploadu)
                                                     |-- /api/v1/forms/convert (501 do czasu podłączenia silnika)
                                                     |-- /api/docs (OpenAPI)
```

## Dlaczego Docker Compose?

- separacja zależności i powtarzalne wdrożenie;
- użytkownik procesu bez uprawnień root, tylko do odczytu, brak zbędnych capabilities;
- port opublikowany wyłącznie na loopback VPS;
- Tailscale Serve udostępnia aplikację wyłącznie w tailnecie (bez Funnel);
- brak stałych wolumenów z uploadami, chwilowe pliki frameworka mieszczą się w tmpfs.

## Zakres etapu 1

- upload jednego pliku, kontrola nazwy, rozmiaru, rozszerzenia oraz podstawowych sygnatur (w Office dodatkowo sprawdzana struktura ZIP);
- UI importu dokumentu i czytelny wynik kontroli;
- endpoint konwersji **intencjonalnie zwraca 501**, nie generuje pozornego wyniku;
- nie używa zewnętrznego API.

## Ograniczenia (jawne)

- Trwałe uruchamianie Qwen/Ollama na obecnym VPS odroczone z powodu małej ilości wolnego RAM.
- Brak Docling, OCR i COI schema: do implementacji w drugim etapie.
- Dla plików DOC sygnatura OLE2 stanowi kontrolę podstawową; pełną identyfikację zapewni parser w następnym etapie.
- Limit wysyłanych danych jest sprawdzany przez `Content-Length` oraz po odczycie pliku. Bardziej rygorystyczne ograniczanie strumienia HTTP należy dodać przed publicznym udostępnieniem.
- Wstępna autoryzacja opiera się na dostępie do prywatnego Tailscale; wymagania JWT trzeba dopracować przy integracji z systemem COI.

## Dalej

1. Materiały COI: wzorcowe JSON-y, pliki wejściowe i słowniki.
2. Lokalny Docling w osobnym workerze (nie obciążać API).
3. Lokalny Ollama z Qwen2.5-VL na sprzęcie z dostępną pamięcią lub GPU.
4. Adapter CanonicalForm → COI JSON według specyfikacji, niezależny od JSON Forms.
5. Interaktywny podgląd JSON Forms i testy na nieznanych dokumentach.
