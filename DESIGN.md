# FormFlow — zasady interfejsu

FormFlow jest narzędziem urzędnika, a nie stroną marketingową. Wizualnie nawiązuje do języka projektowego instytucji publicznych (granat, jasne przestrzenie robocze, niebieskie CTA i oszczędny akcent różowy), ale **nie jest oficjalną aplikacją COI**.

## Podstawowa ścieżka

**Dodaj dokument → Sprawdź i popraw → Pobierz formularz.**

Interfejs ma trzy jednoznaczne etapy. W szczególności:
- Automatyczny wynik jest wersją roboczą i **nie zwalnia z porównania z oryginałem**.
- Urzędnik widzi wynik i ma możliwość poprawienia pytania przed eksportem.
- Edytowalne kontrolki są czytelnie odróżnione od instrukcji i informacji prawnych.
- Opisy błędów nie powinny sugerować udanej konwersji, gdy brak pól lub trwa analiza.

## Design tokens

Źródło prawdy: `apps/api/app/static/style.css` (`:root`).

| Rola | Token | Kolor |
|---|---|---|
| Tło nawigacji | `--navy-deep` | `#06112a` |
| Nagłówki | `--navy` | `#091735` |
| Tekst | `--ink` | `#13264d` |
| Tekst pomocniczy | `--muted` | `#52617c` |
| Główna akcja | `--blue` | `#3157e9` |
| Hover | `--blue-hover` | `#2444c6` |
| Akcent | `--pink` | `#d84b9e` |
| Tło robocze | `--canvas` | `#f5f7fc` |
| Karty | `--surface` | `#ffffff` |
| Obramowanie | `--border` | `#dde4f0` |

Ważne zasady: kontrast i semantyka statusów, focus dla klawiatury, wsparcie `prefers-reduced-motion`, poprawna obsługa mobile, brak zależności od zewnętrznych fontów.

## Implementacja

- `apps/api/app/static/index.html` — struktura aplikacji i treść interfejsu.
- `apps/api/app/static/style.css` — layout, responsywność, tokeny.
- `apps/api/app/static/app.js` — sterowanie wizardem.
- `apps/frontend/preview.jsx` i `EditorPanel.jsx` — podgląd oraz edytor.
- `apps/frontend/preview.css` — style budowane do `apps/api/app/static/preview.bundle.css`.

Po zmianie kodu JS/CSS frontend uruchom `npm --prefix apps/frontend test` i `npm --prefix apps/frontend run build`. Nie zmieniaj wyglądu w sposób, który psuje kontrolę nad oryginałem i walidacją.
