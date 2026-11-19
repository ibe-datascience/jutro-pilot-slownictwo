# JUTRO – pilotaż: słownictwo przedmiotowe i pseudosłowa (biologia, ZPE)

Pilotaż IBE PIB. Proces buduje **listy kandydatów** do testu JUTRO na materiałach Zintegrowanej Platformy Edukacyjnej
(biologia, szkoła podstawowa, kl. 5–8): pulę terminów przedmiotowych (T3), pulę słownictwa ogólnego/szkolnego (T1/T2),
grupy pojęć i pseudosłowa do testu typu LexTALE. Żadna lista nie jest zwalidowana ekspercko.

**Raport (EN):** https://ibe-datascience.github.io/jutro-pilot-slownictwo/
**Raport szczegółowy (PL):** [`wyniki/biologia_sp/probka50/raport.md`](wyniki/biologia_sp/probka50/raport.md)

## Uruchomienie

```bash
python -m jutro run --config config/biologia_sp.yaml --probka 50   # próbka 50 materiałów
python -m jutro run --config config/biologia_sp.yaml               # pełny korpus
```

Przedmiot i klasy są parametrami w `config/biologia_sp.yaml`. Kroki: korpus → tagowanie → frekwencje → kandydaci →
llm → pule → pseudoslowa → raport.

## Zawartość repozytorium

| Ścieżka | Opis |
|---|---|
| `jutro/` | kod procesu |
| `config/` | konfiguracja przebiegu |
| `wyniki/biologia_sp/probka50/` | wyniki próbki 50 materiałów (CSV/XLSX, metryki JSON, raport PL) |
| `site/` | źródło raportu Quarto; `docs/` – wyrenderowana strona (GitHub Pages) |
| `resources/*/README*.md`, `manifest.json` | dokumentacja zasobów: dostępność, licencje, sumy kontrolne |

Nie ma tu zrzutu ZPE (`data/`), środowiska ani zasobów zewnętrznych (modeli, słowników frekwencyjnych, list
pseudosłów) – opis pobrania i licencji jest w `resources/*/README*.md`. SUBTLEX-PL (CC BY-NC-SA 4.0) służy wyłącznie
do metryk porównawczych.
