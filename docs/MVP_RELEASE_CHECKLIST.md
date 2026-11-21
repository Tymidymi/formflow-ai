# FormFlow AI — MVP / instrukcja demonstracji (22.11.2026)

**Status:** kandydat demonstracyjny v1.4.0, **nie gotowy do automatycznego bezobsługowego przetwarzania dowolnych formularzy**. Produkcja v1.3.0 pozostaje bez zmian.

## Co można pokazać

1. Trzy kroki aplikacji: **Dodaj dokument → Sprawdź i popraw → Pobierz formularz**.
2. Darmowy, syntetyczny przykład w UI (**Uruchom przykład**) bez zewnętrznego API.
3. Przejście od źródłowego dokumentu do COI JSON przez Qwen3-VL na OpenRouter, o ile świadomie wyrażono zgodę. AI może ominąć pola i musi być weryfikowane przez człowieka.
4. Podgląd oryginału, weryfikację i edytor definicji pól, zapis ręcznych poprawek do pliku oraz walidację strukturalną JSON COI.
5. Przy `needs_review` UI wymaga potwierdzenia, że użytkownik porównał każdą stronę z oryginałem. Nie jest to certyfikat wierności i nie zastępuje audytu.

## Środowiska

- **Dotychczasowe demo/produkcja:** `https://vibe.tail075c6f.ts.net:9466/` → `127.0.0.1:18171`, v1.3.0.
- **Kandydat v1.4:** `http://127.0.0.1:18172/` na VPS, stack `formflow-review`, osobno od produkcji. Adres bezpośredni dostępny z VPS; nowy port Tailscale wymaga uprawnień administratora.
- Repo: `Tymidymi/formflow-ai`, branch `refactor/source-page-pipeline`, draft PR #1. Nie łączyć automatycznie z `main`.

Kontrola bez płatnego wywołania:

```bash
curl -fsS http://127.0.0.1:18172/healthz
curl -fsS http://127.0.0.1:18172/api/v1/capabilities
curl -fsS http://127.0.0.1:18172/api/v1/demo/convert
```

Przykładowy test prawdziwego przepływu AI na fikcyjnym `service.docx`:

```bash
curl --max-time 250 -H 'X-External-AI-Consent: true' \
  -F 'file=@/tmp/formflow-refactor-validation/independent/service.docx' \
  'http://127.0.0.1:18172/api/v1/forms/convert?mode=diagnostic'
```

Oryginały i surowe wyniki nie trafiają do Git. Dane prywatne testować wyłącznie zgodnie z zasadami zgody i ochrony danych.

## Stan pomiarów — nie mylić z testami jednostkowymi

- Starszy audyt 8 plików dwustopniowego pipeline: **0/8 pełnych sukcesów semantycznych**; 6 odpowiedzi HTTP 200 nie oznacza sukcesu. `docs/AUDIT_END_TO_END_2026-11-22.md`.
- W najnowszym eksperymencie usunięto destrukcyjny drugi przebieg LLM. W trzech zwykłych wywołaniach API: **1/3 poprawnych** według niezależnych kryteriów (syntetyczny `service.docx`: 9/9, XLSX: 2/ok.7, PNG: 0/ok.11). `docs/SINGLE_PASS_EXPERIMENT_2026-11-22.md`.
- Lokalnie 22.11: **122/122 testów backendu** i **20/20 frontendu**, build UI przechodzi. To są testy kodu, nie dowód wierności źródłu.
- Dodatkowy test live po aktualizacji MVP: fikcyjny **service.docx** → Qwen, **HTTP 200, 9/9 pól, poprawny schemat, niezależny checker PASS**, czas **104,82 s**, 3851 tokenów. To pojedynczy pozytywny przebieg — brak gwarancji powtarzalności.
- Lockfile npm naprawiony i instalacja `npm ci` od zera przetestowana lokalnie; uruchomienie CI GitHub na nowym commicie wymaga osobnego potwierdzenia.

## Otwarte ryzyka przed oddaniem

- Niestabilność detekcji prawdziwych pól przez Qwen: `INFO_BLOCK` zamiast wejścia, zły wybór, podpisy i warunki.
- Złożony DOCX z tabelami/rysunkami bywa niekompletny po renderowaniu LibreOffice — wykrywana strata skutkuje błędem HTTP 422, a nie cichym sukcesem.
- Nadal brak pozytywnego testu importu JSON do systemu COI.
- **Regulamin COI zakazuje zależności od zewnętrznych API. Bieżący model jest wywoływany przez OpenRouter i nie jest zgodny z tym wymogiem.** Decyzja o ewentualnej akceptacji wymaga pisemnej interpretacji organizatora.

## Bramka wdrożenia

Nie podmieniać v1.3.0 na porcie 18171, dopóki nie przejdzie reprezentatywna niezależna macierz semantyczna i nie potwierdzono możliwości demo. Jeżeli czas na eksperymenty się skończył, demonstrować **uczciwie syntetyczny przykład + edycję i walidację COI**, jasno zaznaczając, że automatyczna konwersja wciąż wymaga ręcznej kontroli.

Nagranie demonstracyjne: pokaż trzy etapy aplikacji, oryginał obok formularza, poprawę jednego pola, walidację i pobranie JSON. Nie pokazuj nieudanej automatycznej konwersji jako zakończonej sukcesem.
