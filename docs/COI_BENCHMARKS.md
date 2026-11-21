# Benchmark FormFlow AI — COI #3 i #4

**Data:** 21.11.2026
**Tryb:** Qwen3-VL-30B-A3B przez OpenRouter (wyłącznie development; nie jest wariantem konkursowym).
**Źródło danych:** tekst wydobyty bezpośrednio z oryginalnych formularzy PDF dostarczonych przez COI. *Nie* zastępuje to end-to-end na oryginalnych plikach, nie uwzględnia rozkładu pól na stronie ani OCR.

## Wyniki początkowe (przed poprawkami promptu)

| Materiał | Pola rozpoznane przez AI | Strony COI JSON (MAIN + FINISH) | Oficjalny schemat | Reguły biznesowe | Koszt OpenRouter |
|---|---:|---|---|---|---:|
| #3 – Wniosek o wydanie zaświadczenia | 11 | prawidłowe | OK | OK | $0.0005058 |
| #4 – Wniosek o wynajęcie/użyczenie świetlicy wiejskiej | 17 | prawidłowe | OK | OK | $0.0005031 |

### Problemy jakościowe odkryte podczas benchmarku

**COI #3**:
- Model wykrył imię/nazwisko, adres, PESEL, telefon, cztery niezależne checkboxy, „inne”, cel, podpis.
- **Brak** pola daty („Młynary, dnia…”).
- Rodzaj zaświadczenia może wymagać pojedynczego RADIO zamiast wielu checkboxów; wymaga weryfikacji wymagań.
- Podpis na formularzu papierowym nie powinien być automatycznie zamieniany na zwykłe pole tekstowe w eUsłudze.

**COI #4**:
- Model rozpoznał okres od–do, uczestników, osobę odpowiedzialną i oświadczenia.
- **Nie rozdzielił wyboru „wynajem/użyczenie”** na osobne pole wyboru.
- Błędnie sklasyfikował podpis jako pole tekstowe.
- Pola dla innej osoby odpowiedzialnej powinny mieć warunkową widoczność, której obecny generator nie tworzy.

### Co zmieniliśmy

- Eksperymentalny długi prompt z dodatkowymi regułami pogorszył kompletność i został wycofany. Obecny runtime korzysta z krótszego promptu, który uzyskał lepszy wynik pierwszego pomiaru.
- Quality gate rozszerzono o kontrolę dodatkowych sygnałów (termin, uczestnicy, odpowiedzialny, cel, oświadczenia).
- Nie publikujemy źródłowych formularzy w repozytorium bez potwierdzenia warunków udostępniania; teksty robocze są w ignorowanym katalogu `data/private/`.

### Następne pomiary

- [ ] Powtórzyć benchmark na aktualnym prompcie.
- [ ] Pełny benchmark na **oryginalnych binarnych plikach** PDF/DOCX/XLSX/ODS/JPG/PNG.
- [ ] Ręcznie ocenić kompletność i poprawność typów oraz walidacji.
- [ ] Porównać jakościowo wyniki z referencyjnymi JSON-ami #1 i #5.
- [ ] Zmierzyć medianę i p95 czasu przetwarzania, liczbę odrzuceń przez quality gate.

**Nie należy utożsamiać** `schema_valid=true` z kompletną cyfryzacją formularza.


## Eksperyment z promptem rozszerzonym — nieprzyjęty

| Źródło | Krótki prompt (przed) | Długi prompt (po) | Decyzja |
|---|---:|---:|---|
| COI #3 | 11 pól | 5 pól, brak PESEL/danych osobowych | Wycofanie długiego promptu |
| COI #4 | 17 pól | 12 pól, nadal brak wyboru wynajem/użyczenie | Wycofanie długiego promptu |

W obu przypadkach schema_valid=true, co podkreśla potrzebę niezależnej oceny kompletności. Przy rozbudowanym prompcie quality gate oznaczył COI #3 jako niekompletny. Wzbogacona heurystyka quality gate zostaje, ale długi prompt **nie** trafił do finalnego kodu.

Model jest niedeterministyczny; zestawienie dotyczy pojedynczych uruchomień, a nie statystycznego benchmarku.
