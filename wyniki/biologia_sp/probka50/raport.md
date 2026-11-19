# Raport pilotażu JUTRO – biologia_sp (probka50)

Wygenerowano: 2026-11-19T18:30:33+01:00. Ziarno: `20261113`.

Wszystkie listy są listami kandydatów z procesu automatycznego. Żadna nie została sprawdzona przez specjalistów, a etykiety modeli nie zostały jeszcze porównane z oceną ludzi.

## 1. Dane

| miara | wartość |
|---|---|
| materiały docelowe (biologia) | 50 |
| materiały kontrastowe (inne przedmioty etapu) | 300 |
| słowa w korpusie docelowym | 81151 |
| słowa w korpusie kontrastowym | 405499 |
| hasła słowniczków ZPE w materiałach docelowych (różne) | 241 |

## 2. Lematyzacja i tagowanie (4.1)

| narzędzie | cała forma zgodna | składniki zgodne | zgodna z formą redakcji ZPE |
|---|---|---|---|
| `llm_sonnet_5_5` | 0.783 | 0.947 | 0.665 |
| `stanza_morfeusz` | 0.777 | 0.937 | 0.659 |
| `llm_haiku_5_5` | 0.773 | 0.937 | 0.67 |
| `spacy_morfeusz` | 0.767 | 0.933 | 0.648 |
| `morfeusz_pierwsza` | 0.65 | 0.93 | 0.527 |
| `stanza` | 0.473 | 0.893 | 0.385 |
| `spacy` | 0.457 | 0.863 | 0.39 |

Próba: 300 form. Arkusz sprawdzony przez człowieka: **nie**. Dopóki nie jest sprawdzony, odniesieniem jest forma podstawowa zapisana przez redakcję ZPE, a gdzie jej brak – tymczasowa odpowiedź modelu językowego; wyniki nie są więc pomiarem względem złotego standardu.

Tager używany dla całego korpusu: `spacy_morfeusz`.

## 3. Frekwencja ogólna (4.3)

| zasób | udział lematów biologii obecnych w zasobie |
|---|---|
| kwjp | 0.922 |
| nkjp1m | 0.698 |
| subtlex | 0.836 |
| wordfreq | 0.909 |

Zasób używany w publikowanych listach: KWJP100 lemma (CC BY 4.0); SUBTLEX tylko do porównań wewnętrznych. SUBTLEX-PL (CC BY-NC-SA 4.0) służy tylko do porównań.

## 4. Kandydaci na terminy (4.2)

| miara | wartość |
|---|---|
| kandydaci przedmiotowi po progach | 3844 |
| … jednowyrazowi | 2892 |
| … wielowyrazowi | 952 |
| … obecni tylko w jednym materiale (frekwencja ≥ próg) | 441 |
| kandydaci ogólni (do puli T1/T2) | 5327 |
| odrzuceni jako nazwy własne | 231 |
| słowa: korpus docelowy / kontrast / lista KWJP100 | 80831 / 397178 / 81664894 |
| terminy zwrócone przez TermoPL | 12706 |

Ile haseł ze słowniczków ZPE proces w ogóle znajduje (górna granica pełności):

| srebrny standard | hasła | wydobyte z korpusu | wśród kandydatów po progach | udział |
|---|---|---|---|---|
| slowniczek | 243 | 234 | 165 | 67.9% |
| pojecie_ref | 207 | 199 | 148 | 71.5% |

Precyzja i pełność rankingów względem haseł ZPE (oba srebrne standardy łącznie). Udział haseł wśród wszystkich kandydatów, czyli precyzja losowego rankingu: **0.042**.

| metoda | kandydatów w rankingu | P@100 | P@300 | R@300 | R@1000 |
|---|---|---|---|---|---|
| log-likelihood względem kontrastu | 3844 | 0.21 | 0.157 | 0.288 | 0.767 |
| log ratio względem kontrastu | 3844 | 0.26 | 0.217 | 0.399 | 0.73 |
| TF-IDF po przedmiotach | 3844 | 0.24 | 0.19 | 0.35 | 0.755 |
| Simple Maths względem KWJP100 | 2892 | 0.22 | 0.203 | 0.53 | 0.887 |
| log-likelihood względem KWJP100 | 2892 | 0.2 | 0.143 | 0.374 | 0.87 |
| PMI (frazy) | 952 | 0.08 | 0.083 | 0.521 | 1 |
| logDice (frazy) | 952 | 0.15 | 0.113 | 0.708 | 1 |
| C-value (TermoPL) | 2432 | 0.21 | 0.15 | 0.283 | 0.497 |
| łączenie rang (RRF) | 3844 | 0.26 | 0.183 | 0.337 | 0.761 |
| sama frekwencja w biologii | 3844 | 0.1 | 0.067 | 0.123 | 0.454 |

Słowniczki zawierają tylko to, co redakcja ZPE zdecydowała się objaśnić, więc niska precyzja nie oznacza, że czołówka rankingu jest błędna. Miara służy wyłącznie do porównania metod między sobą.

Te same rankingi względem etykiety końcowej T3 z kroku 5 (udział T3 wśród kandydatów przedmiotowych: **0.205**). Etykiety pochodzą od modeli, nie od ludzi.

| metoda | P@100 | P@300 | P@1000 | P@300 słowa | P@300 frazy |
|---|---|---|---|---|---|
| log-likelihood względem kontrastu | 0.47 | 0.49 | 0.448 | 0.447 | 0.52 |
| log ratio względem kontrastu | 0.73 | 0.673 | 0.498 | 0.647 | 0.523 |
| TF-IDF po przedmiotach | 0.56 | 0.543 | 0.416 | 0.477 | 0.537 |
| Simple Maths względem KWJP100 | 0.74 | 0.68 | 0.417 | 0.68 | – |
| log-likelihood względem KWJP100 | 0.47 | 0.44 | 0.358 | 0.44 | – |
| PMI (frazy) | 0.38 | 0.46 | 0.325 | – | 0.46 |
| logDice (frazy) | 0.53 | 0.517 | 0.325 | – | 0.517 |
| C-value (TermoPL) | 0.53 | 0.493 | 0.375 | 0.27 | 0.56 |
| łączenie rang (RRF) | 0.6 | 0.597 | 0.471 | 0.513 | 0.57 |
| sama frekwencja w biologii | 0.16 | 0.18 | 0.227 | 0.17 | 0.507 |

## 5. Klasyfikacja modelami językowymi

Modele klasyfikujące niezależnie: `claude-sonnet-5-5`, `claude-opus-5-5`; rozbieżności i przypadki o niskiej pewności rozstrzyga `claude-fable-5-2`. Wersja promptu: `v2`. Model nie widzi etykiet regułowych ani wyników innych modeli.

| miara | wartość |
|---|---|
| sklasyfikowani kandydaci | 5344 |
| … przedmiotowi | 3844 |
| … tylko ogólni | 1500 |
| zgodność prosta (sonnet_5_5 vs opus_5_5) | 0.809 |
| kappa Cohena | 0.748 |
| rozstrzygane przez trzeci model | 1544 |
| pozostawione do przeglądu (brak większości lub niska pewność sędziego) | 335 |
| formy podstawowe poprawione przez model | 82 |

| grupa kandydatów | n | zgodność prosta | kappa |
|---|---|---|---|
| wszystkie | 5344 | 0.809 | 0.748 |
| przedmiotowe | 3844 | 0.815 | 0.755 |
| tylko_ogolne | 1500 | 0.795 | 0.715 |
| jednowyrazowe | 4004 | 0.788 | 0.691 |
| wielowyrazowe | 1340 | 0.874 | 0.752 |

| etykieta końcowa | wszyscy | kandydaci przedmiotowi | kandydaci tylko ogólni |
|---|---|---|---|
| T3 | 797 | 788 | 9 |
| T3_INNY | 219 | 69 | 150 |
| T2 | 1729 | 1098 | 631 |
| T1 | 1495 | 1101 | 394 |
| SZUM | 1104 | 788 | 316 |

Rodzaje szumu: luzne_polaczenie – 690, fragment_terminu – 238, interfejs – 103, nazwa_wlasna – 58, blad_ekstrakcji – 11, inne – 4.

Rozstrzygnięcia (1544): z powodu różnych etykiet 1019, z powodu niskiej pewności przy zgodnych etykietach 525. Sędzia zgodził się z: sonnet_5_5 – 926, opus_5_5 – 913; wybrał etykietę inną niż oba modele 159 razy.

Etykieta regułowa z kroku 4 (progi rozproszenia i frekwencji) rozstrzygała 3010 z 3844 kandydatów przedmiotowych i zgadzała się z etykietą końcową w 50.9% przypadków (precyzja T3: 44.2%, pełność T3: 75.6%). Etykiety regułowe nie są używane do budowy pul.

Metoda porównawcza: `claude-opus-5-5` wypisał terminy wprost z 30 materiałów (1230 różnych terminów biologicznych, w tym 598 wielowyrazowych). Wśród kandydatów z kroku 4 jest 51.0% z nich (jednowyrazowe 62.3%, wielowyrazowe 39.0%); pozostałe są w pliku `terminy_llm_spoza_kandydatow.csv`.

Grupowanie w pojęcia (`claude-fable-5-2`, jedno żądanie na całą listę): 790 terminów, 122 grup wieloterminowych obejmujących 275 terminów.

Koszt API wszystkich kroków (także oceny lematyzacji i pseudosłów), razem z zadaniami wcześniejszych wersji promptów:

| zadanie / model | koszt USD |
|---|---|
| ekstrakcja_terminow / claude-sonnet-5-5 | 0.17 |
| ekstrakcja_terminow_v2 / claude-opus-5-5 | 1.19 |
| klasyfikacja / claude-haiku-5-5 | 0.05 |
| klasyfikacja / claude-sonnet-5-5 | 1 |
| klasyfikacja_rozstrzygniecie / claude-opus-5-5 | 0.63 |
| klasyfikacja_v2 / claude-opus-5-5 | 12.63 |
| klasyfikacja_v2 / claude-sonnet-5-5 | 6.49 |
| klasyfikacja_v2_rozstrzygniecie / claude-fable-5-2 | 6.75 |
| lematyzacja_proba / claude-haiku-5-5 | 0.01 |
| lematyzacja_proba / claude-sonnet-5-5 | 0.13 |
| lematyzacja_referencja / claude-opus-5-5 | 0.43 |
| pojecia_v2 / claude-fable-5-2 | 0.13 |
| pseudoslowa / claude-haiku-5-5 | 0 |
| pseudoslowa_ocena_v2 / claude-fable-5-2 | 2.3 |
| pseudoslowa_v2 / claude-opus-5-5 | 2.39 |
| test_smoke / claude-haiku-5-5 | 0 |
| test_smoke2 / claude-haiku-5-5 | 0 |
| test_smoke2 / claude-opus-5-5 | 0.01 |
| test_smoke2 / claude-sonnet-5-5 | 0 |
| test_v2 / claude-fable-5-2 | 0.84 |
| test_v2 / claude-opus-5-5 | 0.43 |
| test_v2 / claude-sonnet-5-5 | 0.21 |

Koszt API tej konfiguracji łącznie: **35.79 USD**.

Zgodność między modelami nie jest miarą trafności. Precyzję, pełność i F1 względem ludzi można podać dopiero po wypełnieniu arkusza `zloty_zbior_do_oznaczenia.xlsx` (zapisanego jako `zloty_zbior_oznaczony.xlsx`).

## 6. Pule

| miara | wartość |
|---|---|
| pula przedmiotowa (T3) | 789 |
| … terminy wielowyrazowe | 306 |
| pula ogólna | 3188 |
| … T1 / T2 | 1480 / 1708 |
| pojęcia (grupy terminów) | 636 |
| … obejmujące więcej niż jeden termin | 122 |
| pozycje w pulach oznaczone do przeglądu | 249 |
| wiersze złotego zbioru do oznaczenia | 400 |

Dopasowanie: każdemu terminowi przypisano najwyżej jedną pozycję puli ogólnej o tej samej części mowy i liczbie wyrazów (przypisanie optymalne, bez powtórzeń; dopuszczalna różnica: 1 na skali Zipfa i 3 litery). Dopasowano 514 z 789 terminów (65.1%).

| cecha | różnica standaryzowana przed | po dopasowaniu |
|---|---|---|
| frekwencja (Zipf) | -1.158 | -0.334 |
| długość w literach | 0.818 | 0.003 |

| warstwa | terminy | pozycje puli ogólnej | dopasowane | udział |
|---|---|---|---|---|
| czasownik | 12 | 518 | 12 | 100.0% |
| fraza 2 | 288 | 90 | 90 | 31.2% |
| fraza 3 | 18 | 0 | 0 | 0.0% |
| przymiotnik | 96 | 916 | 76 | 79.2% |
| przysłówek | 2 | 179 | 1 | 50.0% |
| rzeczownik | 373 | 1485 | 335 | 89.8% |

## 7. Pseudosłowa (4.4)

| miara | wartość |
|---|---|
| szablony (prawdziwe rzeczowniki i czasowniki) | 240 |
| kandydaci wygenerowani | 11603 |
| odrzuceni przez filtry | 8685 |
| po filtrach (różne ciągi) | 2911 |
| ocenieni przez model | 1232 |
| … ocenieni pozytywnie | 550 |
| lista rekomendowana (`wybrane`) | 370 |
| szablony z co najmniej jednym rekomendowanym pseudosłowem | 206 |

| generator | wygenerowane | przeszło filtry | ocenione | ocena pozytywna | wymawialność (1–5) | podobieństwo do słowa (0–3) | na liście rekomendowanej |
|---|---|---|---|---|---|---|---|
| `wuggy_koncowka` | 1856 | 36.0% | 298 | 39.3% | 3.49 | 0.899 | 74 |
| `wuggy` | 2268 | 14.0% | 126 | 25.4% | 3.246 | 0.937 | 20 |
| `unipseudo` | 2880 | 10.7% | 161 | 36.0% | 3.882 | 1.329 | 30 |
| `llm` | 2870 | 53.3% | 603 | 54.6% | 4 | 1.015 | 239 |
| `imbir` | 1729 | 5.4% | 44 | 31.8% | 3.5 | 1.068 | 7 |

| powód odrzucenia | kandydaci |
|---|---|
| długość, liczba sylab lub zakończenie inne niż we wzorcu | 4526 |
| nietypowy układ liter | 2388 |
| istniejące słowo | 766 |
| jedna litera od częstego słowa | 752 |
| istniejący rdzeń z przedrostkiem lub przyrostkiem, zrost | 188 |
| różni się od wzorca jedną literą | 52 |
| skojarzenie wulgarne | 9 |
| brzmi jak istniejące słowo | 2 |
| znaki spoza alfabetu | 1 |
| słowo ukraińskie lub rosyjskie | 1 |

Lista rekomendowana względem szablonów (różnica standaryzowana średnich; wartości bliskie 0 oznaczają, że pseudosłów nie da się odróżnić od słów po samej cesze):

| cecha | średnia | odch. std. | różnica względem szablonów |
|---|---|---|---|
| dlugosc | 7.668 | 1.695 | 0.145 |
| syl | 2.773 | 0.815 | 0.153 |
| zbitka | 2.062 | 0.674 | 0.011 |
| diakryty | 0.516 | 0.651 | -0.166 |
| old20 | 2.913 | 0.62 | 0.501 |
| bigram_lp | -2.444 | 0.183 | 0.042 |

Ocena „wymawialności” i skojarzeń pochodzi od modelu `claude-fable-5-2` i zastępuje ocenę sędziów tylko na etapie selekcji; lista wymaga oceny przez osoby dwujęzyczne i pilotażu z uczniami.

## 8. Pliki wynikowe

- `wyniki/biologia_sp/probka50/kandydaci.csv`: jest
- `wyniki/biologia_sp/probka50/pula_przedmiotowa.csv`: jest
- `wyniki/biologia_sp/probka50/pula_ogolna.csv`: jest
- `wyniki/biologia_sp/probka50/pojecia.csv`: jest
- `wyniki/biologia_sp/probka50/terminy_llm_spoza_kandydatow.csv`: jest
- `wyniki/biologia_sp/probka50/pseudoslowa.csv`: jest
- `wyniki/biologia_sp/probka50/pseudoslowa_odrzucone.csv`: jest
- `wyniki/biologia_sp/probka50/pseudoslowa_szablony.csv`: jest
- `wyniki/biologia_sp/probka50/pseudoslowa_rozklady.csv`: jest
- `wyniki/biologia_sp/probka50/zloty_zbior_do_oznaczenia.xlsx`: jest
- `wyniki/biologia_sp/probka50/ocena_lematyzacji_300.xlsx`: jest

## 9. Wersje

```json
{
  "python": "3.12.2",
  "platforma": "macOS-26.5.2-arm64-arm-64bit",
  "morfeusz2": "1.99.15",
  "spacy": "3.8.18",
  "pl_core_news_lg": "3.8.0",
  "stanza": "1.15.0",
  "torch": "2.15.0",
  "wordfreq": "3.1.1",
  "Wuggy": "1.1.2",
  "anthropic": "2.8.0",
  "pandas": "3.1.1",
  "numpy": "2.5.4",
  "scipy": "1.18.1",
  "scikit-learn": "1.9.1",
  "rapidfuzz": "3.14.6",
  "lxml": "6.1.3",
  "openpyxl": "3.1.5",
  "PyYAML": "6.0.3"
}
```

## 10. Ograniczenia

- Przebieg na próbce: liczebności i rankingi zmienią się na pełnym korpusie.
- Klasa materiału jest szacowana regułami z działu tematycznego (katalog ZPE zna tylko etap 4–8).
- Etykiety T1/T2/T3 pochodzą od modeli językowych; złoty zbiór czeka na etykiety ludzi.
- Frekwencja ogólna fraz nie jest dostępna w KWJP100, więc frazy dopasowuje się po frekwencji w korpusie ZPE.
- Kandydat wielowyrazowy musi pasować do wzorca składniowego (przymiotnik + rzeczownik, rzeczownik + dopełniacz); terminy o innej budowie są widoczne tylko w ekstrakcji modelem.
- Filtr słów ukraińskich i rosyjskich opiera się na transliteracji najczęstszych słów z list wordfreq i nie zastąpi oceny przez osoby znające te języki.

Czas generowania raportu: 0.0 s.