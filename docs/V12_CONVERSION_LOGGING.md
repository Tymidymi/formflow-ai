# FormFlow AI v1.2.0 — logi diagnostyczne konwersji

**Data:** 21.11.2026. **Status:** trwałe logowanie techniczne na prywatnym VPS, bez zapisu dokumentów.

## Co było nie tak?

W wersji v1.1.0 Docker zapisywał tylko komunikaty uruchamiania. Uvicorn działał z `--no-access-log`, a adapter Qwen nie zapisywał przyczyny niepoprawnego JSON-a. Historycznego błędu użytkownika z 21 listopada nie da się teraz odtworzyć. Wiadomo jedynie, że parser JSON odrzucił odpowiedź modelu.

## Co logujemy od v1.2.0?

Każda konwersja dostaje losowy 32-znakowy `request_id`, zwracany w nagłówku `X-Request-ID` i przy błędach w interfejsie.

Zdarzenia:
- `conversion_start`: rozszerzenie i rozmiar pliku, tryb Vision.
- `document_extracted`: liczba stron i obrazów.
- `model_request`: nazwa modelu, limit odpowiedzi i liczba obrazów.
- `model_response`: długość odpowiedzi, `finish_reason`, liczniki tokenów, czas, identyfikator zapytania OpenRouter.
- `model_invalid_json`: typ błędu i numer **wiersza/kolumny**, nigdy treść odpowiedzi.
- `model_http_failure`, `model_network_failure`, `conversion_failed`: typ awarii i kody HTTP.
- `conversion_processed`: czy JSON przeszedł walidację, wyniki jakości.
- `conversion_http`: końcowy status HTTP i czas operacji.

**Nie logujemy:** nazw plików, plików, tekstu OCR, promptów, etykiet, modelowego JSON-a, danych osobowych, nagłówków autoryzacji, sekretów, surowych odpowiedzi serwera. Działa twarda lista dozwolonych pól i walidacja ich typów oraz tekstów.

## Bezpieczeństwo i retencja

- Trwały plik wewnątrz kontenera: `/var/log/formflow/conversions.jsonl`.
- Trwały bind mount na VPS: `/home/tymot/projects/formflow-ai/data/private/logs`.
- Katalog: UID/GID `10001:10001`, prawa `0700`; pliki i rotowane pliki tworzone z `umask 0077` (0600).
- Rotacja: 3 MiB + 3 kopie, razem maksymalnie ok. 12 MiB. Bez gwarantowanej retencji czasowej.
- Docker logi: maks. 5 MiB × 3 pliki, ale **nie przeżywają odtwarzania kontenera**. Bind mount przeżywa.
- Plik ignorowany przez GitHub. Brak publicznego endpointu podglądu logów. Czyta go administrator VPS przez Docker.

Na VPS ostatnie wpisy:

`docker exec formflow-ai-api-1 sh -c 'tail -n 60 /var/log/formflow/conversions.jsonl'`

Wyszukiwanie po identyfikatorze użytkownika:

`docker exec formflow-ai-api-1 sh -c 'grep -F "TU_WKLEJ_32_ZNAKOWY_KOD" /var/log/formflow/conversions.jsonl*'`

## Interpretacja błędów

- `MODEL_OUTPUT_TRUNCATED` oraz `finish_reason=length`: model osiągnął limit długości.
- `MODEL_INVALID_JSON` oraz `finish_reason=stop`: model ukończył odpowiedź, ale jej składnia JSON była błędna. Zapisujemy pozycję błędu, nie surowy tekst.
- `MODEL_RESPONSE_FORMAT`: niezgodny format koperty API.
- `MODEL_TIMEOUT` i `MODEL_NETWORK_ERROR`: problem transportowy.
- `PROVIDER_HTTP_ERROR`: kod OpenRouter inny niż 200.

Limit wyjściowy Qwen podniesiony z **4000 do 6500 tokenów**. To zwiększa szansę, że długi formularz się zmieści, ale może wydłużyć pracę i zwiększyć koszt. **Nie wykonujemy automatycznie drugiego płatnego żądania.**

- `DOCUMENT_REJECTED`: plik uszkodzony lub nieobsługiwany; to błąd wejścia, a nie JSON/Qwen.

## Testy i ograniczenia

Testujemy błędny JSON, ucięty JSON, poprawny JSON, prywatność logów, spójność identyfikatora API i frontend oraz trwały zapis po ponownym uruchomieniu kontenera. Wszystko na danych syntetycznych bez wysyłania danych do OpenRouter.

Nie można odtworzyć wcześniejszej nieudanej odpowiedzi dla „Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.pdf”, ponieważ przed tą wersją nie zapisano jej metadanych. Logi zadziałają dopiero dla nowych prób.
