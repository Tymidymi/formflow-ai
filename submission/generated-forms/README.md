# Przykładowe wyniki FormFlow AI — HackNation 2026 / COI

Pliki źródłowe JSON dla pojedynczych prób są **rzeczywistymi, nieedytowanymi wynikami** aplikacji FormFlow AI. Ewentualny plik scalony nr 9 został zestawiony automatycznie z tych wyników.
Uruchomiono endpoint `POST /api/v1/forms/convert?mode=diagnostic&vision=auto` na jednym dokumencie z każdego zestawu nr 1–9 (PDF oraz DOCX dla zestawów nr 1 i 5). 
Pozostałych wersji tego samego formularza w innych formatach nie przetwarzano w tym zestawieniu.

**Ważne:** walidacja składniowa COI nie oznacza pełnej zgodności z oryginałem. 
Wyniki oznaczone „Do kontroli” należy ręcznie porównać z każdą stroną źródła, zwłaszcza pod kątem brakujących pól, błędnych warunków i opcji.
Wersja demonstracyjna korzysta z modelu OpenRouter, więc nie należy jej przedstawiać jako zgodnej z wymaganiem lokalnego przetwarzania bez zewnętrznego API.

| Nr | Formularz | Źródło | Pola wejściowe | Status | JSON COI |
|---:|---|---|---:|---|---|
| 1 | Wniosek o ustalenie numeru porządkowego nieruchomości | DOCX | 10 | Do kontroli | [Zobacz / pobierz](./01-ustalenie-numeru-porzadkowego-nieruchomosci.json) |
| 2 | Wniosek o zwrot opłaty skarbowej | PDF | 11 | Do kontroli | [Zobacz / pobierz](./02-zwrot-oplaty-skarbowej.json) |
| 3 | Wniosek o wydanie zaświadczenia | PDF | 7 | Do kontroli | [Zobacz / pobierz](./03-wydanie-zaswiadczenia.json) |
| 4 | Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej | PDF | 10 | Do kontroli | [Zobacz / pobierz](./04-wynajecie-swietlicy.json) |
| 5 | Wniosek o stwierdzenie nadpłaty podatku | DOCX | 15 | Do kontroli | [Zobacz / pobierz](./05-nadplata-podatku.json) |
| 6 | Zezwolenie na zajęcie pasa drogowego | PDF | 26 | Do kontroli | [Zobacz / pobierz](./06-zajecie-pasa-drogowego.json) |
| 7 | Zezwolenie na utrzymywanie psów ras uznawanych za agresywne | PDF | 19 | Do kontroli | [Zobacz / pobierz](./07-psy-rasy-agresywne.json) |
| 8 | Deklaracja opłaty za odpady komunalne | PDF | 72 | Do kontroli | [Zobacz / pobierz](./08-odpady-komunalne.json) |
| 9 | Stypendium, nagroda lub wyróżnienie sportowe | PDF (podzielony na 4 części) | 140 | Do kontroli | [Zobacz / pobierz](./09-stypendium-sportowe-scalony.json) · [cz. 1](./09-stypendium-sportowe-czesc-1.json) / [cz. 2](./09-stypendium-sportowe-czesc-2.json) / [cz. 3](./09-stypendium-sportowe-czesc-3.json) / [cz. 4](./09-stypendium-sportowe-czesc-4.json) |

## Jak powstały wyniki

- Źródła to niewypełnione formularze konkursowe COI dostarczone przez uczestnika.
- Dla nr 1 dostępna była również referencyjna konfiguracja COI. Opublikowany wynik wygenerowano od nowa z dokumentu źródłowego przez FormFlow — **nie kopiowano** referencyjnego JSON.
- Zestaw nr 9 liczy 16 stron, ale silnik aplikacji ma ograniczenie 12 obrazów stron. Zamiast ukrywać błąd, podzielono **ten sam PDF** na cztery kolejne zakresy po 4 strony i każdy uruchomiono osobno przez API. Jeżeli dostępny jest wynik scalony, to połączono wyłącznie wygenerowane definicje stron, zmieniono identyfikatory i połączenia nawigacji oraz ponownie zwalidowano schemat; nie dopisywano żadnych pytań.
- Konwersja odbyła się przez faktyczne API aplikacji w trybie diagnostycznym — bez ręcznego dopisywania pól, bez hardkodowania poprawek dla konkretnych dokumentów.
- Publikowane są pliki JSON COI ze strukturalnie poprawnych odpowiedzi zawierających przynajmniej jedno pole wejściowe. Formularze bez pól lub z błędnym schematem nie są prezentowane jako sukcesy.
- Statusy i metadane znajdują się w [manifest.json](./manifest.json). Pełna poprawność merytoryczna **nie została potwierdzona**.

Projekt: [FormFlow AI](https://github.com/Tymidymi/formflow-ai) · [Demo dla jury](https://vibe.tail075c6f.ts.net:9466/projekt/) (prywatny adres Tailscale, wymaga logowania).
Alternatywnie: [tymczasowe demo przez Cloudflare Tunnel](https://subject-kids-bolt-citations.trycloudflare.com/projekt/) (wymaga logowania; adres tunelu może się zmienić).