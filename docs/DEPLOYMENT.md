# FormFlow — wdrożenie i utrzymanie

## Wymagania

Docker Engine + Compose v2, co najmniej kilka GB wolnego RAM na workery, możliwość pobrania obrazów i zależności. Komponenty obrazu: API Python 3.13, Office z LibreOffice i Docling Slim, PDF z Tesseract, pypdfium2 i pypdf. Model multimodalny wymaga odpowiedniego dostawcy lub dedykowanego hosta GPU.

Wszystkie polecenia wykonuj z katalogu głównego repozytorium. Plik `.env` nie jest wersjonowany.

## 1. Konfiguracja

```bash
cp .env.example .env
# W trybie developerskim ustaw OPENROUTER_API_KEY
# Opcjonalnie zmień OPENROUTER_MODEL i FORMFLOW_HOST_PORT
```

## 2. Uruchomienie kompletnego stosu developerskiego

```bash
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build
```

- `compose.yaml`: API bez włączonego AI; podstawowe ograniczenia bezpieczeństwa.
- `compose.dev.yaml`: dostęp do OpenRouter + zwiększony limit RAM API; **nie używać jako konfiguracji offline**.
- `compose.docling.yaml`: renderer Office (wewnętrzny port 8001).
- `compose.pdf.yaml`: OCR PDF (wewnętrzny port 8002).
- `compose.ollama.yaml`: opcjonalny lokalny adapter/model; nie jest wymiennikiem gotowym bez pobrania wag i testów.
- Nie uruchamiaj samodzielnego `compose.yaml`, jeśli oczekujesz pełnej konwersji: `readyz` zgłosi brak AI.

API ma bind wyłącznie na `127.0.0.1:${FORMFLOW_HOST_PORT:-18171}`. Workerów nie publikuj bezpośrednio do Internetu.

## 3. Smoke test

```bash
curl -fsS http://127.0.0.1:18171/healthz
curl -fsS http://127.0.0.1:18171/readyz
curl -fsS http://127.0.0.1:18171/api/v1/capabilities
curl -fsS http://127.0.0.1:18171/api/v1/demo/convert > /tmp/formflow-demo.json
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml ps
```

`/healthz` sprawdza żywotność, `/readyz` wykrywa skonfigurowanego providera, lecz **nie potwierdza kompletnego pipeline’u**. Dodatkowo przetestuj `extract-preview` na DOCX oraz `convert?mode=diagnostic` na kontrolnym formularzu. Gdy ekstraktor Office zwraca 502 „Brak poprawnego PDF”, sprawdź czy worker i API pochodzą z tej samej rewizji kodu/obrazu; samo `up -d api` nie aktualizuje workerów.

## 4. Dostęp HTTPS i bezpieczeństwo

Na serwerze demonstracyjnym port lokalny 18171 jest dostępny prywatnie przez **Tailscale Serve :9466**. Nie należy go mylić z Funnel: dostępna usługa jest przeznaczona dla sieci tailnet. Nie publikuj `.env`, źródłowych dokumentów ani portów 8001/8002.

Wersja aplikacyjna nie posiada własnego JWT/RBAC: kontrolę dostępu zapewnia Tailscale lub administrator bramy sieciowej. Wysyłanie formularzy do OpenRouter wymaga świadomej zgody w UI.

Przed publikacją sprawdź prywatność repozytorium, prawa do materiałów COI i zasady użycia modelu.

## 5. Aktualizacja

```bash
git pull --ff-only origin main
npm --prefix apps/frontend ci
npm --prefix apps/frontend run build

docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf up -d --build
```

Przy zmianie kontraktu API/ekstraktora **odbuduj również workery**. Wcześniej zachowaj kopię releasu i sprawdź niezależny wynik JSON. Nie nadpisuj produkcji wariantem nieprzetestowanym.

## 6. Diagnostyka

```bash
docker ps --filter name=formflow
docker logs --tail 60 formflow-ai-api-1
docker logs --tail 60 formflow-ai-docling-office-1
docker logs --tail 60 formflow-ai-pdf-engine-1
docker stats --no-stream formflow-ai-api-1 formflow-ai-docling-office-1 formflow-ai-pdf-engine-1
```

Logi mają metadane techniczne i identyfikator żądania, nie powinny przechowywać treści dokumentu. Rezultaty diagnostyczne mogą ujawniać fragmenty źródeł — traktuj je jako poufne.

**Wymóg utrzymaniowy:** użytkownik końcowy musi potwierdzić poprawność każdego wygenerowanego formularza. Sam status `schema_valid` nie jest wystarczającym testem odbiorowym.

## 7. Zatrzymanie bez usuwania danych

```bash
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml \
  --profile docling --profile pdf stop
```

Do usunięcia niepotrzebnego starego wpisu Tailscale Serve dla portu 9467 (wymaga uprawnień operatora/root): `sudo tailscale serve --https=9467 off`. **Nie używaj `tailscale serve reset`**, bo usunie również konfigurację innych usług VPS.
