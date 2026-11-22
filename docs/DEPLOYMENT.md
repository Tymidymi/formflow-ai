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

## Dostęp dla jury i publikacja przez HTTPS

Dostęp kontroluje **Caddy 2.11.9 (oficjalny obraz Docker)** przez
`basic_auth` na wszystkich ścieżkach, przed `reverse_proxy api:8000`.
Bez nagłówka `Authorization` lub przy niepoprawnym haśle Caddy zwraca
`401 Unauthorized` i `WWW-Authenticate: Basic`. Przeglądarka wyświetla
natywne okno logowania. Nie ma sesji/cookie ani formularza logowania
po stronie FastAPI. Caddy **nie** przekazuje tego nagłówka do backendu.

### Przygotowanie hasła

```bash
cp .env.example .env  # tylko przy pierwszym uruchomieniu
python3 scripts/setup_gateway.py --username jury
# Skrypt prosi o hasło i jego potwierdzenie bez echo, wywołuje
# 'docker run caddy:2.11.9-alpine caddy hash-password', zapisuje
# 'jury <hash bcrypt>' do ignorowanego pliku z uprawnieniami 0600.
```

Możesz zmienić hasło przez `python3 scripts/setup_gateway.py --username jury
--rotate` i restart kontenera `gateway`. Nie umieszczaj hasła lub
hasha w repozytorium ani w `compose.yaml`. Caddyfile importuje
`/etc/caddy/jury-users.caddy` montowany tylko do odczytu.

### Uruchomienie (obowiązkowa bramka)

```bash
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  --profile docling --profile pdf up -d --build
```

FastAPI nie ma opublikowanego portu hosta. Jedyny bind to
`127.0.0.1:${FORMFLOW_HOST_PORT:-18171}` należący do Caddy.
OCR/Office/PDF są w wewnętrznej sieci Docker; nie publikuj 8000/8001/8002.
Tailscale Serve `9466` przekazuje HTTPS do localhost `18171`.
Nie włączaj Funnel ani publicznego reverse proxy bez decyzji użytkownika.

### Test przed publiczną publikacją

```bash
curl -si http://127.0.0.1:18171/ | head -n 12
# Oczekiwane 401 oraz nagłówek WWW-Authenticate.
curl --user jury http://127.0.0.1:18171/api/v1/demo/convert
# curl zapyta o hasło, nie wpisuj go bezpośrednio w terminalu.
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  config --format json
# Upewnij się, że TYLKO gateway ma opublikowany port.
```

Dla użytkowników zewnętrznych wymagany jest prawidłowy **HTTPS**;
HTTP Basic przesyła hasło w postaci odwracalnego Base64 w nagłówku.
Używaj długiego, losowego hasła. Wersja demonstracyjna nie ma natywnego
„wyloguj”, per-użytkownikowego audytu ani limitera prób logowania.
Do wdrożenia produkcyjnego rozważ centralne SSO / rate limiting.


## 2. Uruchomienie kompletnego stosu developerskiego

```bash
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  --profile docling --profile pdf up -d --build
```

- `compose.yaml`: API bez włączonego AI; podstawowe ograniczenia bezpieczeństwa.
- `compose.dev.yaml`: dostęp do OpenRouter + zwiększony limit RAM API; **nie używać jako konfiguracji offline**.
- `compose.docling.yaml`: renderer Office (wewnętrzny port 8001).
- `compose.pdf.yaml`: OCR PDF (wewnętrzny port 8002).
- `compose.auth.yaml`: **obowiązkowy** Caddy Basic Auth, jedyny opublikowany port hosta.
- `compose.ollama.yaml`: opcjonalny lokalny adapter/model; nie jest wymiennikiem gotowym bez pobrania wag i testów.
- Nie uruchamiaj samodzielnego `compose.yaml`, jeśli oczekujesz pełnej konwersji: `readyz` zgłosi brak AI.

Caddy ma bind wyłącznie na `127.0.0.1:${FORMFLOW_HOST_PORT:-18171}`. API jest dostępne tylko w sieci Docker. Workerów nie publikuj bezpośrednio do Internetu.

## 3. Smoke test

```bash
# Każda ścieżka, także /healthz, jest chroniona: oczekiwane HTTP 401.
curl -si http://127.0.0.1:18171/ | head -n 12
docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  --profile docling --profile pdf ps

# Po skonfigurowaniu HTTPS (hasło wpisuje się na wezwanie curl):
curl --user jury https://HOST/readyz
curl --user jury https://HOST/api/v1/capabilities
curl --user jury https://HOST/api/v1/demo/convert
```

Sprawdź pozycje `api` i `gateway`: oba kontenery muszą działać.
Dodatkowo przetestuj `extract-preview` na DOCX, konwersję PDF i
`convert?mode=diagnostic` na kontrolnym formularzu. Gdy worker Office zwraca
502 „Brak poprawnego PDF”, sprawdź, czy API i worker są z tej samej rewizji.

## 4. Dostęp HTTPS i bezpieczeństwo

Na serwerze demonstracyjnym port lokalny 18171 jest dostępny prywatnie przez **Tailscale Serve :9466**. Nie należy go mylić z Funnel: dostępna usługa jest przeznaczona dla sieci tailnet. Nie publikuj `.env`, źródłowych dokumentów ani portów 8001/8002.

Zewnętrzny Caddy stosuje HTTP Basic Auth do całej aplikacji; sam FastAPI nie zarządza użytkownikami, sesjami ani JWT/RBAC. Wysyłanie formularzy do OpenRouter nadal wymaga świadomej zgody w UI.

Przed publikacją sprawdź prywatność repozytorium, prawa do materiałów COI i zasady użycia modelu.

## 5. Aktualizacja

```bash
git pull --ff-only origin main
npm --prefix apps/frontend ci
npm --prefix apps/frontend run build

docker compose -f compose.yaml -f compose.dev.yaml \
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
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
  -f compose.docling.yaml -f compose.pdf.yaml -f compose.auth.yaml \
  --profile docling --profile pdf stop
```

Do usunięcia niepotrzebnego starego wpisu Tailscale Serve dla portu 9467 (wymaga uprawnień operatora/root): `sudo tailscale serve --https=9467 off`. **Nie używaj `tailscale serve reset`**, bo usunie również konfigurację innych usług VPS.
