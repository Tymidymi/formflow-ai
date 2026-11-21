# FormFlow AI — zależności i licencje (inwentaryzacja)

**Stan: 21.11.2026.** To jest inwentaryzacja bezpośrednich komponentów
na podstawie zainstalowanych pakietów, a **nie zakończony audyt prawny**.
Przed dystrybucją obrazu Docker trzeba zweryfikować wszystkie zależności
przechodnie oraz dołączyć wymagane teksty licencji i informacje o źródłach.

| Komponent | Wersja | Licencja / informacja | Gdzie używany |
|---|---|---|---|
| Python | 3.13.9 | PSF | API i workery |
| FastAPI | 0.115.12 | sprawdzić metadane dystrybucji | API i workery |
| Uvicorn | 0.34.3 | BSD-3-Clause | API i workery |
| Pydantic | 2.11.7 | MIT | CanonicalForm |
| jsonschema | 4.25.1 | MIT | COI JSON |
| httpx | 0.28.1 | BSD-3-Clause | adapter usług |
| pypdf | 6.1.3 | BSD-3-Clause | PDF |
| pypdfium2 | 5.2.0 | BSD-3-Clause/Apache-2.0 + zależności | PDF |
| Pillow | 12.0.0 | MIT-CMU | obrazy |
| python-docx | 1.2.0 | MIT | DOCX fallback |
| openpyxl | 3.1.5 | MIT | XLSX fallback |
| Docling Slim | 2.151.1 | MIT | Office source structure |
| Docling Core | 2.108.0 | MIT (weryfikacja licencji zależności przechodnich wymagana) | struktura dokumentów |
| Tesseract OCR | Debian Bookworm | Apache-2.0 (sprawdzić wersję i paczki językowe) | PDF/OCR |
| React, React DOM | 18.3.1 | MIT | frontend |
| JSON Forms (core/react/vanilla) | 3.8.0 | MIT | frontend |
| esbuild | 0.25.12 | MIT | build frontendu |

## Normalizacja Office

Worker uruchamia pakiety LibreOffice Writer i Calc z Debian Trixie oraz fonts-dejavu-core. Dokładne informacje licencyjne instalowanych pakietów znajdują się w obrazie w `/usr/share/doc/libreoffice-common/copyright` i `/usr/share/doc/fonts-dejavu-core/copyright`. Docling Slim 2.151.1 jest instalowany z extras format-office i format-opendocument; bez modeli PyTorch i nowego OCR. Antiword nie jest używany.

## Ryzyko regulaminowe niezależne od licencji

Obecna wersja przesyła dokumenty do zewnętrznego API OpenRouter po zgodzie.
Wymóg COI zabrania zewnętrznego API. Użyty model Qwen jest dostępny
również lokalnie, ale to **nie** usuwa niezgodności uruchomionej wersji.
Zob. docs/DECISION_API_SUBMISSION.md.

## Otwarte kontrole

- [ ] Licencje wszystkich zależności pośrednich Python/Node/Debian i obrazu PDFium.
- [ ] Pełna lista źródeł, przypiętych wersji, kopie wymaganych not prawnych.
- [ ] Wyjaśnienie, czy wywołanie Antiword jako procesu i dołączenie binarnego
      programu do obrazu spełniają kryteria COI.
- [ ] Licencja wag Qwen oraz warunki usługi OpenRouter używanej na konkursie.
- [ ] Potwierdzenie prawa do rozpowszechniania przykładowych dokumentów.
