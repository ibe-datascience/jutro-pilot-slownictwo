# Raport pilotażu JUTRO – biologia_sp (probka50)

Wygenerowano: 2026-11-13T17:22:06+01:00. Ziarno: `20261113`.

## 1. Dane

```json
{
  "zrodlo": "/Users/michalpalinski/Desktop/ibe/dashboards/podstawy_programowe/data/zpe",
  "pola_katalogu": [
    "source",
    "id",
    "title",
    "typ_materialu",
    "przedmiot",
    "etap",
    "etap_kod",
    "klasa",
    "url",
    "authors",
    "extra{subject_ids, stage_ids, student_content, teacher_content, cover, has_validable_exercises, searcher}"
  ],
  "materialy_lacznie": 350,
  "materialy_cel": 50,
  "materialy_cel_tylko_ten_przedmiot": 43,
  "materialy_kontrast": 300,
  "jednostki_html_cel": 63,
  "slowa_cel": 81151,
  "slowa_kontrast": 405499,
  "slowa_cel_wg_typu_segmentu": {
    "tresc": 51017,
    "definicja": 4501,
    "cwiczenie": 22330,
    "podpis": 3173,
    "alt": 32042,
    "tytul": 130
  },
  "slowa_wszystkie_wg_typu_segmentu": {
    "tresc": 306260,
    "definicja": 17700,
    "cwiczenie": 146748,
    "podpis": 15541,
    "alt": 234538,
    "tytul": 401
  },
  "segmenty_w_statystykach": [
    "cwiczenie",
    "definicja",
    "podpis",
    "tresc",
    "tytul"
  ],
  "materialy_wg_przedmiotu": {
    "Informatyka": 81,
    "Język polski": 57,
    "Biologia": 50,
    "Matematyka": 44,
    "Historia": 28,
    "Wiedza o społeczeństwie": 23,
    "Geografia": 18,
    "Przyroda": 14,
    "Fizyka": 13,
    "Plastyka": 13,
    "Muzyka": 8,
    "Chemia": 8,
    "Edukacja zdrowotna": 7,
    "Edukacja dla bezpieczeństwa": 4,
    "Wychowanie fizyczne": 2,
    "Technika": 1,
    "Wychowanie do życia w rodzinie": 1,
    "Etyka": 1
  },
  "slowa_wg_przedmiotu": {
    "Język polski": 87318,
    "Biologia": 81151,
    "Historia": 74583,
    "Informatyka": 44833,
    "Matematyka": 43597,
    "Geografia": 36522,
    "Wiedza o społeczeństwie": 35610,
    "Muzyka": 23121,
    "Plastyka": 21195,
    "Przyroda": 19313,
    "Fizyka": 18055,
    "Edukacja zdrowotna": 15762,
    "Chemia": 9604,
    "Edukacja dla bezpieczeństwa": 7064,
    "Technika": 1763,
    "Wychowanie fizyczne": 363,
    "Wychowanie do życia w rodzinie": 273,
    "Etyka": 44
  },
  "materialy_cel_wg_typu": {
    "edukacja dostępna": 39,
    "zasób dodatkowy (KZD)": 4,
    "e-materiał": 4,
    "edukacja włączająca": 3
  },
  "klasa_katalog_cel": {
    "4-8": 50
  },
  "klasa_szac_reguly_cel": {
    "None": 4,
    "5": 16,
    "6": 7,
    "8": 7,
    "7": 16
  },
  "klasa_szac_pewnosc_cel": {
    "wysoka": 36,
    "niska": 3,
    "brak": 4,
    "srednia": 7
  },
  "klasa_jawnie_w_tresci_cel": 0,
  "zrodlo_tresci": {
    "html": 344,
    "txt": 6
  },
  "pliki_pobrane_z_icloud": 220,
  "bledy_parsowania": [],
  "liczba_bledow": 0,
  "szablony": {
    "prog_materialow": 4,
    "rozne_zdania_usuniete": 1055,
    "usuniecia_lacznie": 18795,
    "slowa_usuniete": 35947,
    "wg_powodu": {
      "szablon powtarzalny": 266,
      "polecenie techniczne": 624,
      "metadane/licencja": 165
    }
  },
  "srebrny_standard": {
    "hasla_slowniczka_cel": 262,
    "rozne_hasla_cel": 241,
    "materialy_cel_ze_slowniczkiem": 36,
    "hasla_slowniczka_kontrast": 684,
    "pary_forma_lemat_cel": 223,
    "rozne_pary_forma_lemat_cel": 215
  },
  "czas_s": 117.8
}
```

## 2. Porównanie narzędzi

### 4.1 Lematyzacja / tagowanie (dokładność lematu na n=300)
| narzędzie | exact | składniki | exact|ZPE |
|---|---|---|---|
| llm_haiku_5_5 | 0.7733 | 0.9367 | 0.6703 |
| llm_sonnet_5_5 | 0.7833 | 0.9467 | 0.6648 |
| spacy | 0.4567 | 0.8633 | 0.3901 |
| spacy_morfeusz | 0.7667 | 0.9333 | 0.6484 |
| stanza | 0.4733 | 0.8933 | 0.3846 |
| stanza_morfeusz | 0.7767 | 0.9367 | 0.6593 |
| morfeusz_pierwsza | 0.65 | 0.93 | 0.5275 |

Referencja ludzka z arkusza: **False**. Do czasu ręcznego sprawdzenia `ocena_lematyzacji_300.xlsx` exact względem ZPE/Opus nie jest złotym standardem badania.

**Rekomendacja (ocena agenta):** tager produkcyjny `spacy_morfeusz` (ustawiony w konfiguracji: `spacy_morfeusz`) – najlepszy kompromis dokładności frazy i czasu; LLM nieznacznie wyżej na exact, ale kosztowny jako tager korpusu.

### 4.2 Ekstrakcja (precyzja@K względem srebrnego standardu ZPE)
| metoda | P@100 | P@300 | P@1000 |
|---|---|---|---|
| ll_kontrast | 0.12 | 0.1033 | 0.073 |
| log_ratio_kontrast | 0.17 | 0.1333 | 0.062 |
| simple_maths_kwjp | 0.12 | 0.0833 | 0.042 |
| tfidf_biol | 0.12 | 0.1033 | 0.074 |
| pmi_mwu | 0.07 | 0.0467 | 0.028 |
| logdice_mwu | 0.07 | 0.0467 | 0.028 |
| cvalue_termopl | 0.15 | 0.1067 | 0.069 |

Kandydatów po filtrach: **3513** (MWU: 817). TermoPL: True.

### 4.3 Frekwencja ogólna
| zasób | pokrycie lematów biol. |
|---|---|
| kwjp | 0.8113 |
| nkjp1m | 0.698 |
| subtlex | 0.8355 |
| wordfreq | 0.9091 |

KWJP100 lemma (CC BY 4.0); SUBTLEX tylko do porównań wewnętrznych

**Uwaga licencyjna:** SUBTLEX-PL = CC BY-NC-SA 4.0 – używany tylko w metrykach, nie w CSV produkcyjnych.

### 5. LLM (zgodność ≠ trafność)
- sklasyfikowano: 925
- rozstrzygnięcia Opus: 246
- zgodność haiku↔sonnet: {'prosta': 0.7762, 'kappa': {'haiku_5_5_vs_sonnet_5_5': 0.6562}}
- rozkład finalny: {'T3': 415, 'T2': 248, 'T1': 169, 'SZUM': 93}
- koszt API (cała konfiguracja): **$2.4354**
- Zgodność między modelami NIE jest miarą trafności – brak etykiet ludzkich ze złotego zbioru.

### 4.4 / B Pseudosłowa
- szablony: 80, zaakceptowane: 1093, odrzucone: 183
- powody odrzuceń: `{'znane_morfeusz': 155, 'sufiks_na_istniejacym': 11, 'literowka_edit1': 10, 'prefiks_na_istniejacym': 7}`

## 3. Wyniki plików
- `wyniki/biologia_sp/probka50/kandydaci.csv`: OK
- `wyniki/biologia_sp/probka50/pula_przedmiotowa.csv`: OK
- `wyniki/biologia_sp/probka50/pula_ogolna.csv`: OK
- `wyniki/biologia_sp/probka50/pojecia.csv`: OK
- `wyniki/biologia_sp/probka50/pseudoslowa.csv`: OK
- `wyniki/biologia_sp/probka50/pseudoslowa_odrzucone.csv`: OK
- `wyniki/biologia_sp/probka50/zloty_zbior_do_oznaczenia.xlsx`: OK
- `wyniki/biologia_sp/probka50/ocena_lematyzacji_300.xlsx`: OK

## 4. Wersje

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

## 5. Ograniczenia
- Klasa materiału jest szacowana regułami z działu tematycznego (katalog ZPE ma tylko etap 4–8).
- Concraft-pl jest dostępny w `resources/tools/concraft`, ale produkcyjny przebieg używa spaCy+Morfeusz.
- Złoty zbiór czeka na etykiety ludzkie – nie raportujemy P/R/F1 modeli względem ludzi.
- Pseudosłowa: UniPseudo/Wuggy zależą od lokalnych zasobów; Imbir to lista gotowa, nie generator.

Czas generowania raportu: 0.0s.