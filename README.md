# JUTRO – pilotaż: słownictwo przedmiotowe i pseudosłowa (biologia, ZPE)

Pilotaż IBE PIB. Listy kandydatów do testu JUTRO zbudowane na materiałach Zintegrowanej Platformy Edukacyjnej
(biologia, szkoła podstawowa, kl. 5–8): pula terminów przedmiotowych, pula słownictwa ogólnego i szkolnego, grupy
pojęć oraz pseudosłowa do testu rozpoznawania słów. Żadna lista nie była jeszcze sprawdzana przez ludzi.

**Prezentacja wyników:** https://ibe-datascience.github.io/jutro-pilot-slownictwo/

## Zawartość

| Ścieżka | Opis |
|---|---|
| `docs/` | strona z metodą i wynikami (GitHub Pages) |
| `wyniki/biologia_sp/probka50/` | wyniki przebiegu na próbce 50 materiałów |
| `wyniki/biologia_sp/pelny/` | opis pełnego korpusu (tylko krok 1) |

Pliki w `wyniki/biologia_sp/probka50/`:

| Plik | Opis |
|---|---|
| `kandydaci.csv` | wszyscy kandydaci ze statystykami, wynikami metod i etykietami modeli |
| `pula_przedmiotowa.csv` | terminy biologiczne (T3) z dopasowanym słowem ogólnym |
| `pula_ogolna.csv` | słownictwo codzienne (T1) i szkolne (T2) |
| `pojecia.csv` | grupy terminów nazywających to samo pojęcie |
| `terminy_llm_spoza_kandydatow.csv` | terminy wypisane przez model wprost z materiałów, których nie ma wśród kandydatów |
| `pseudoslowa.csv` | pseudosłowa, które przeszły filtry; kolumna `wybrane` oznacza listę rekomendowaną |
| `pseudoslowa_odrzucone.csv` | odrzucone pseudosłowa z powodem |
| `pseudoslowa_szablony.csv`, `pseudoslowa_rozklady.csv` | słowa-wzorce i porównanie ich cech z pseudosłowami |
| `zloty_zbior_do_oznaczenia.xlsx` | arkusz do oznaczenia przez dwie osoby (bez etykiet modeli) |
| `ocena_lematyzacji_300.xlsx` | arkusz do sprawdzenia lematyzacji |
| `raport.md` | raport szczegółowy po polsku |
| `metryki/*.json`, `przebieg.json` | metryki każdego kroku, wersje bibliotek |

Repozytorium nie zawiera kodu procesu, materiałów ZPE ani zasobów zewnętrznych (modeli, list frekwencyjnych, list
pseudosłów). Metoda, narzędzia, modele i ustawienia przebiegu są opisane na stronie.
