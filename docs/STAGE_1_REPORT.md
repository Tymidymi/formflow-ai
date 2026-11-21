# Etap 1 — wdrożenie na VPS (2026-11-21)

## Zrobione

- [x] Repozytorium robocze `/home/tymot/projects/formflow-ai` (lokalny Git; GitHub czeka na utworzenie z powodu braku uprawnień create repository w integracji i braku logowania gh na VPS).
- [x] FastAPI 0.115.12 + statyczny interfejs importu.
- [x] Walidacja rozszerzenia, nazwy, sygnatury MIME, ZIP Office i limitu pliku.
- [x] Endpointy: `/healthz`, `/readyz`, `/api/v1/capabilities`, `/api/v1/forms/inspect`, `/api/v1/forms/convert` (celowo HTTP 501).
- [x] Docker Compose (bez uprawnień root, read-only, tmpfs, limit pamięci, port tylko na `127.0.0.1:18171`).
- [x] Testy jednostkowe (11/11) w środowisku programistycznym.

## Blokery infrastruktury

**Tailscale Serve:** obecny użytkownik `tymot` nie ma roli operatora Tailscale; `tailscale serve` zwraca `Access denied`, a `sudo -n` wymaga hasła. Jednorazowa komenda na VPS (wpisywana przez właściciela):

```sh
sudo tailscale serve --bg --https=9466 http://127.0.0.1:18171
```

Wówczas prywatny URL: `https://vibe.tail075c6f.ts.net:9466/` (bez Funnel).

**GitHub:** na VPS nie ma sesji `gh auth`, a połączona integracja GitHub nie udostępnia tworzenia nowych repozytoriów. Można utworzyć puste prywatne `Tymidymi/formflow-ai` na GitHubie, następnie wypchnąć lokalny commit.

**AI:** ciężkich modeli nie uruchamiamy na VPS z ~1.1 GiB dostępnej pamięci; projektujemy osobny worker na host z GPU / RAM. Formaty i struktury COI wymagają materiałów z Discorda.

## Kolejny etap

Materiał COI -> test schematu -> Docling worker -> lokalny Qwen -> adapter CanonicalForm/COI -> JSON Forms. Nie tworzyć pozornego wyjścia konkursowego.
