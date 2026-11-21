# FormFlow AI — status wdrożenia (2026-11-21)

## Stan etapów

| Komponent | Status |
|---|---|
| Repozytorium lokalne | ✅ Gotowe: `/home/tymot/projects/formflow-ai`, branch `main`, commit `8f339f1` |
| Repozytorium GitHub | ⏳ Jeszcze nieopublikowane — wymagana finalizacja sesji gh |
| FastAPI | ✅ Uruchomione, `/healthz` = HTTP 200 |
| Docker Compose | ✅ `formflow-ai-api-1` healthy, `127.0.0.1:18171` |
| Tailscale Serve | ✅ `https://vibe.tail075c6f.ts.net:9466/` wyłącznie w Tailnet |
| Walidacja plików | ✅ Etap 1: nazwa, rozszerzenie, limit, podstawowa sygnatura/MIME |
| Frontend | 🟡 Prosty HTML/CSS/JS, bez React/JSON Forms |
| Testy | ✅ 11 testów etapu 1 + smoke testy 200/415/501 |
| Docling | ⬜ Nie zainstalowano |
| Ollama + Qwen2.5-VL | ⬜ Nie zainstalowano |
| JSON COI | ⬜ Nie generuje: `/api/v1/forms/convert` celowo zwraca HTTP 501 |
| JSON Forms | ⬜ Jeszcze niezaimplementowane |

## Weryfikacja

- [x] HTTPS przez prywatny Tailscale Serve, bez Funnel.
- [x] Kontener nie ma publicznie otwartego portu; `127.0.0.1:18171`.
- [x] `GET /healthz`: `{"status":"ok","service":"formflow-ai-api","version":"0.1.0"}`.
- [x] `GET /readyz`: `{"status":"foundation_ready","conversion_ready":false}`.
- [x] Odrzucenie nieprawidłowego PDF: HTTP 415.
- [x] Brak pozornej konwersji: HTTP 501.
- [ ] JSON w formacie konkursowym COI.

## GitHub — problem autoryzacji

Logowanie kodem urządzenia przeszło weryfikację, ale CLI nie zapisało tokenu: katalog `/home/tymot/.config` ma właściciela `root`, a użytkownik `tymot` nie może tam zapisać `gh/hosts.yml`. Do bezpiecznego rozwiązania przygotowano `/home/tymot/.local/share/gh-cli`. Po nowym zatwierdzeniu urządzenia używać `GH_CONFIG_DIR=/home/tymot/.local/share/gh-cli gh ...`; nie zmieniać uprawnień całego `~/.config`.

## Co następne

1. Dokończyć uwierzytelnienie i utworzyć prywatne `Tymidymi/formflow-ai`, następnie push.
2. Pobrać materiały COI: wzorcowe JSON-y, przykładowe dokumenty i specyfikację.
3. Dodać worker Docling i parser do `DocumentBlocks` z testami na PDF/DOCX/skanie.
4. Zbadać zasoby inferencji — VPS miał około 1,1 GiB dostępnego RAM, więc nie wdrażać pochopnie ciężkiego Qwen.
5. Dopiero potem stworzyć `CanonicalForm`, lokalny pipeline AI, adapter COI JSON i podgląd JSON Forms.

## Komendy kontrolne

```bash
cd /home/tymot/projects/formflow-ai
docker compose ps
curl -fsS http://127.0.0.1:18171/healthz
tailscale serve status
GH_CONFIG_DIR=/home/tymot/.local/share/gh-cli gh auth status
git status -sb
git remote -v
```
