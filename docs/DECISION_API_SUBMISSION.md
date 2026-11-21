# Decyzja projektowa — zgłoszenie hackathonowe z API (21.11.2026)

**Status:** decyzja użytkownika/zespołu obowiązująca dla pozostałych runów HackNation 2026.

## Wybór rozwiązania

- Na konkurs składamy **FormFlow AI używający API OpenRouter/Qwen3-VL-30B-A3B**. Model ma otwarte wagi, ale **inferencja w tej wersji jest wykonywana przez zewnętrzne API**.
- Ekstrakcja PDF/OCR, Docling, walidacja COI i aplikacja nadal działają na VPS.
- **Nie stawiamy lokalnego Ollama ani lokalnego LLM na hackathonie**, nie przygotowujemy GPU i nie mierzymy inferencji offline.
- Istniejący adapter Ollama jest zachowany jako **opcjonalny backlog po konkursie**. Nie jest warunkiem submission, demo ani MVP.
- Priorytety kolejnych runów: pełny benchmark oryginalnych formularzy, poprawne pola/JSON, interaktywny podgląd, testy, prezentacja i materiały zgłoszeniowe.

## Uczciwa ocena zgodności z regulaminem

COI zakazuje zależności od **zewnętrznych API, MCP i SaaS** oraz osobno użycia modeli dostępnych **wyłącznie przez API**. To odrębne ograniczenia obowiązujące łącznie.

**Wybór OpenRouter nie spełnia zakazu zależności od zewnętrznego API.**
Fakt, że Qwen można także uruchomić lokalnie, nie usuwa tego naruszenia.
Jest to **świadoma decyzja projektowa z ryzykiem niespełnienia wymogów / odrzucenia zgłoszenia**, a nie zaakceptowany wyjątek. **Nie twierdzimy, że wersja konkursowa spełnia regulamin**. Nie ukrywamy OpenRouter przed organizatorem.

Możemy spytać mentorów o **pisemną zgodę/interpretację**; dopóki jej nie ma, zakładamy, że zależność od OpenRouter jest niezgodna z wymogiem.

## Konfiguracja i bezpieczeństwo

- Obecny `compose.dev.yaml` zasila wersję z OpenRouter; nazwa `dev` pochodzi z historii projektu.
- Klucz API trzymamy wyłącznie w ignorowanym pliku `.env`, bez commita do repozytorium.
- Utrzymujemy zgodę użytkownika przed wysłaniem dokumentu do API; do demonstracji używamy danych syntetycznych lub zatwierdzonych.
- `readyz.competition_compliant=false` pozostaje prawidłowe.
- Lokalna inferencja / `compose.ollama.yaml` nie jest uruchamiana ani planowana na bieżący hackathon.

## Priorytet

Ten dokument **zastępuje wcześniejsze plany** offline Qwen w `docs/TASKLIST.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/LOCAL_QWEN.md` i poprzednich raportach.
