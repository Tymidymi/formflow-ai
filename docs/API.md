# FormFlow — REST API

**Baza lokalna:** `http://127.0.0.1:18171`. Szczegółowe modele odpowiedzi: `/api/openapi.json`; dokumentacja HTML: `/api/docs`.

## Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `GET /` | Interfejs użytkownika |
| `GET /healthz` | Liveness |
| `GET /readyz` | Gotowość silnika do konwersji |
| `GET /api/v1/capabilities` | Dostępne formaty, limit uploadu, wariant modelu |
| `POST /api/v1/forms/inspect` | Kontrola MIME, nazwy, rozmiaru |
| `POST /api/v1/forms/extract-preview` | Lokalny OCR i podgląd tekstu, **bez modelu** |
| `POST /api/v1/forms/convert` | Projekt JSON COI |
| `POST /api/v1/forms/validate-json` | Strukturalna kontrola COI |
| `GET /api/v1/demo/convert` | Syntetyczny przykład bez AI |

## Upload

`multipart/form-data`, pole `file`, pojedynczy plik `PDF/DOC/DOCX/ODS/XLSX/JPG/JPEG/PNG`. Nazwa maks. **250 znaków**, zakazane `; : > < / \\ | ' * % $`. Zawartość pliku musi odpowiadać rozszerzeniu (MIME/magic bytes). Rozmiar: `MAX_UPLOAD_MB` (domyślnie 15 MB).

### Zwykły eksport (tylko po przejściu kontroli)

```bash
curl -sS -H 'X-External-AI-Consent: true' \
  -F 'file=@wniosek.pdf' \
  'http://127.0.0.1:18171/api/v1/forms/convert'
```

HTTP 200: bezpośrednio konfiguracja COI JSON z kluczami `title`, `tabs`, `flow`. HTTP 422 `COI_REVIEW_REQUIRED`: automatyczna kontrola wykryła problem; nie oznacza to braku możliwości ręcznego przygotowania formularza.

### Tryb diagnostyczny dla UI

```bash
curl -sS -H 'X-External-AI-Consent: true' \
  -F 'file=@wniosek.pdf' \
  'http://127.0.0.1:18171/api/v1/forms/convert?mode=diagnostic&vision=auto'
```

HTTP 200: obiekt zawiera `status` (`generated` lub `needs_review`), `form`, `validation`, `quality`, `grounding`, `inventory`, `document`, `usage`, `model`. Status `generated` nie zastępuje ręcznej kontroli.

### Lokalne OCR bez modelu

```bash
curl -sS -F 'file=@wniosek.pdf' \
  'http://127.0.0.1:18171/api/v1/forms/extract-preview'
```

Zwraca tekst podglądu, metadane stron i liczbę obrazów. Nie wykonuje żądania do OpenRouter.

### Walidacja wynikowego COI

```bash
curl -sS -H 'Content-Type: application/json' \
  --data-binary @formularz.json \
  'http://127.0.0.1:18171/api/v1/forms/validate-json'
```

Odpowiedź zawiera co najmniej `schema_valid`, `valid`, `errors` i `warnings`. Walidacja COI jest strukturalna — importer docelowy nie został przetestowany.

## Kody błędów (przykłady)

| HTTP | Kod / sytuacja |
|---|---|
| 400 | Niepoprawny JSON wejściowy |
| 403 | `EXTERNAL_API_CONSENT_REQUIRED` |
| 413 | Przekroczony limit danych |
| 415 | Nieobsługiwany lub fałszywie oznaczony format |
| 422 | `DOCUMENT_REJECTED`, `INVALID_SEMANTIC_FORM`, `COI_REVIEW_REQUIRED` |
| 502 | Niedostępna lub błędna odpowiedź ekstraktora/modelu |
| 503 | Brak skonfigurowanego modelu lub workera |

W odpowiedziach błędów może wystąpić `request_id` do korelacji z logiem technicznym. Konwersja ma limit 240 sekund, a dwie równoległe konwersje to maksymalna współbieżność.

**Dokumentacja architektury:** [TECHNICAL.md](TECHNICAL.md).
