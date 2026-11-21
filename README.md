# FormFlow AI · HackNation 2026 · COI

Prywatny prototyp systemu cyfryzacji urzędowych formularzy. Projekt docelowo użyje **Docling → lokalny Ollama / Qwen2.5-VL → JSON COI** i **JSON Forms** do podglądu. **Etap 1** dostarcza działającą, zabezpieczoną warstwę uploadu i interfejs webowy – jeszcze **nie** generuje JSON COI.

## Uruchomienie

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:18171/healthz
```

Adres HTTP widoczny tylko na VPS: `http://127.0.0.1:18171`. Przykładowe prywatne udostępnienie przez **Tailscale Serve** (nie Funnel):

```bash
tailscale serve --bg --https=9466 http://127.0.0.1:18171
# W razie potrzeby wyłącz tylko ten nowy port:
tailscale serve --https=9466 off
```

## API

- `GET /healthz` – status API.
- `GET /readyz` – etap gotowości (konwersja nieaktywna).
- `GET /api/v1/capabilities` – lista formatów i aktualnych możliwości.
- `POST /api/v1/forms/inspect` – `multipart/form-data` (`file`) → JSON: rozmiar i MIME, bez trwałego zapisu.
- `POST /api/v1/forms/convert` – zarezerwowany endpoint. W etapie 1 zawsze zwraca `501`.
- `/api/docs` – dokumentacja OpenAPI.

## Testy

```bash
python -m pip install -r apps/api/requirements-test.txt
PYTHONPATH=apps/api pytest -q apps/api/tests
```

## Polityka przechowywania danych

Nie zapisujemy wgrywanych dokumentów na dysku aplikacyjnym ani do repozytorium. Framework może korzystać z tymczasowego dysku podczas odczytu multipart; kontener ma wydzielony tmpfs czyszczony wraz z kontenerem. W tym etapie żaden dokument nie jest wysyłany do zewnętrznych usług.

## Aktualny status wdrożenia

- [Raport statusowy](docs/STATUS.md)
- [Plan realizacji — aktualizowany](docs/IMPLEMENTATION_PLAN.md)
- [Raport z pierwszego etapu](docs/STAGE_1_REPORT.md)

## Status / dalszy plan

Zobacz [architekturę](docs/ARCHITECTURE.md). Materiały konkursowe z Discorda są konieczne przed implementacją adaptera eksportującego JSON COI.
