# FormFlow AI — stan wdrożenia (21.11.2026)

## Wdrożone na VPS

- [x] FastAPI 0.3.0 i Docker Compose z portem 127.0.0.1:18171
- [x] Prywatny Tailscale Serve: https://vibe.tail075c6f.ts.net:9466/
- [x] Przesyłanie dokumentów, weryfikacja formatu, rozmiaru i nazwy
- [x] Oddzielny dev-only adapter OpenRouter Qwen3-VL-8B-Instruct
- [x] Rzeczywisty test wywołania API, HTTP 200: 5 stron, 15 pól (łącznie z sekcjami), 0 błędów walidacji strukturalnej
- [x] Lekka ekstrakcja tekstu z PDF/DOCX/XLSX; vision dla JPG/PNG i skanowanych PDF (do 2 stron)
- [x] Mapowanie z prostego JSON semantycznego na format tabs/sections/flow COI
- [x] Wymagana jawna zgoda na wysyłkę dokumentu do OpenRouter

## Ograniczenia

- [ ] Docling nie jest jeszcze uruchomiony
- [ ] Stare DOC oraz ODS nie mają jeszcze ekstraktora (API zwraca 501)
- [ ] Walidacja pełnym oficjalnym JSON Schema COI **nie została wdrożona** — działa walidator strukturalny
- [ ] Wersja konkursowa musi działać bez zewnętrznego API; compose.yaml nie zawiera OpenRouter, compose.dev.yaml służy wyłącznie do rozwoju
- [ ] JSON Forms (renderer) nie jest jeszcze podłączony
- [ ] Nie zmierzono jeszcze jakości na prawdziwych formularzach konkursowych
- [ ] GitHub remote nie został jeszcze opublikowany (gh CLI niedostępne z zapisanym logowaniem)

## Komendy operacyjne

```bash
cd /home/tymot/projects/formflow-ai
# Development — używa lokalnego pliku .env, który nie trafia do Git.
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
# Konkurs / offline — bez OpenRouter
docker compose -f compose.yaml -f compose.dev.yaml down
docker compose -f compose.yaml up -d --build
```

## Następny krok

Przenieść pełny schemat COI z materiałów konkursowych, wdrożyć Docling/ODS/DOC,
zbudować renderer i przeprowadzić pomiary jakości JSON na rzeczywistych formularzach.
