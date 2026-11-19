"""Wspólne funkcje stron Quarto: wybór przebiegu, wczytanie metryk i wyników, tabele.

Strony nie zawierają liczb wpisanych ręcznie – wszystko jest czytane przy renderowaniu z
`wyniki/<nazwa>/<przebieg>/`. Który przebieg jest pokazywany, mówi `site/_przebieg.json`
(zapisywany przez `python -m jutro site` i przez krok `raport`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from IPython.display import Markdown, display

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
RUN = json.loads((SITE / "_przebieg.json").read_text(encoding="utf-8"))
NAME, RUN_NAME = RUN["nazwa"], RUN["przebieg"]
OUT = ROOT / "wyniki" / NAME / RUN_NAME
REPO = "https://github.com/ibe-datascience/jutro-pilot-slownictwo"
RAW = "https://raw.githubusercontent.com/ibe-datascience/jutro-pilot-slownictwo/main"


# ----------------------------------------------------------------------------- wczytywanie
def metrics(name: str) -> dict[str, Any]:
    """Zawartość `metryki/<name>.json` (pole `dane`) albo pusty słownik."""
    p = OUT / "metryki" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))["dane"] if p.exists() else {}


def run_meta() -> dict[str, Any]:
    p = OUT / "przebieg.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name)


def xlsx(name: str) -> pd.DataFrame:
    return pd.read_excel(OUT / name)


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


# ----------------------------------------------------------------------------- wyświetlanie
def md(text: str) -> None:
    display(Markdown(text))


def fmt(v: Any) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ") if abs(v) >= 10_000 else str(v)
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}".replace(",", " ")
    return str(v).replace("|", "\\|").replace("\n", " ")


def table_md(rows: Iterable[Iterable[Any]], headers: list[str], align: str | None = None) -> str:
    """Mała statyczna tabela jako tekst Markdown. `align`: po jednym znaku l/r/c na kolumnę."""
    align = align or "l" + "r" * (len(headers) - 1)
    sep = {"l": ":---", "r": "---:", "c": ":---:"}
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(sep[a] for a in align) + "|"]
    lines += ["| " + " | ".join(fmt(x) for x in r) + " |" for r in rows]
    return "\n".join(lines)


def table(rows: Iterable[Iterable[Any]], headers: list[str], align: str | None = None) -> None:
    md(table_md(rows, headers, align))


def df_table(df: pd.DataFrame, align: str | None = None) -> None:
    table(df.itertuples(index=False, name=None), [str(c) for c in df.columns], align)


def dt(df: pd.DataFrame, page: int = 25, order: list | None = None, wrap: list[str] | None = None,
       hide: list[str] | None = None) -> None:
    """Pełna tabela interaktywna: szukanie, sortowanie, filtr w każdej kolumnie, eksport CSV/Excel.

    Wszystkie wiersze są osadzone w stronie (bez próbkowania). `hide` – kolumny domyślnie ukryte
    (do włączenia przyciskiem „Columns”); `wrap` – kolumny z długim tekstem, które mają się zawijać.
    """
    import itables

    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            s = df[c].round(3)
            whole = bool(s.notna().any() and (s.dropna() % 1 == 0).all())  # liczby całkowite wczytane jako 4.0
            if s.isna().any():
                # brak wartości ma być pustą komórką, nie „NaN”; liczby zapisane jako tekst DataTables nadal sortuje liczbowo
                df[c] = [("" if v != v else str(int(v)) if whole else f"{v:.3f}".rstrip("0").rstrip(".")) for v in s]
            else:
                df[c] = s.astype("int64") if whole else s
        elif df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].astype(object).where(df[c].notna(), "")
    cols = list(df.columns)
    defs = []
    if hide:
        defs.append({"targets": [cols.index(c) for c in hide if c in cols], "visible": False})
    if wrap:
        defs.append({"targets": [cols.index(c) for c in wrap if c in cols], "className": "dt-wrap"})
    itables.show(
        df,
        maxBytes=0,
        showIndex=False,
        pageLength=page,
        lengthMenu=[10, 25, 50, 100, 500],
        column_filters="footer",
        # itables 2.9.1: przy włączonym zaznaczaniu tekstu nagłówka sortowanie jest podpinane po numerze kolumny
        # widocznej, więc przy ukrytych kolumnach kliknięcie sortuje sąsiednią kolumnę; bez tej opcji sortuje DataTables
        text_in_header_can_be_selected=False,
        scrollX=True,
        order=order or [],
        columnDefs=defs,
        buttons=[
            {"extend": "colvis", "text": "Columns"},
            {"extend": "csvHtml5", "text": "CSV (filtered rows)"},
            {"extend": "excelHtml5", "text": "Excel (filtered rows)"},
        ],
        layout={"topStart": "pageLength", "topEnd": "search", "top2Start": "buttons",
                "bottomStart": "info", "bottomEnd": "paging"},
        classes="display compact nowrap",
        style="table-layout:auto;width:100%;caption-side:bottom",
    )


def source(*files: str) -> None:
    """Linki do plików źródłowych tabeli w repozytorium (podgląd i pobranie)."""
    parts = []
    for f in files:
        path = f"wyniki/{NAME}/{RUN_NAME}/{f}"
        parts.append(f"`{f}` ([view]({REPO}/blob/main/{path}) · [download]({RAW}/{path}))")
    md("Source file: " + "; ".join(parts) + ".")


def glossary(columns: Iterable[str]) -> None:
    """Objaśnienia kolumn (nazwy w plikach są polskie)."""
    rows = [(f"`{c}`", COLUMNS.get(c, "")) for c in columns]
    lines = ["| Column | Meaning |", "|:---|:---|"] + [f"| {c} | {d} |" for c, d in rows]
    md("::: {.callout-note collapse=\"true\" title=\"Column glossary\"}\n" + "\n".join(lines) + "\n:::")


def include_markdown(path: Path | str, drop_title: bool = True, shift: int = 0) -> None:
    """Wstawia plik Markdown z repozytorium do strony (bez pierwszego nagłówka H1).

    `shift` obniża poziom nagłówków o podaną liczbę (poza blokami kodu), żeby wstawiony plik
    mieścił się pod nagłówkiem strony.
    """
    text = Path(path).read_text(encoding="utf-8")
    if drop_title:
        text = re.sub(r"\A\s*# [^\n]*\n", "", text, count=1)
    if shift:
        out, fence = [], None
        for line in text.split("\n"):
            m = re.match(r"^\s*(`{3,}|~{3,})", line)
            if m and fence is None:
                fence = m.group(1)[0] * len(m.group(1))
            elif m and fence and line.strip().startswith(fence) and line.strip().strip(fence[0]) == "":
                fence = None
            elif fence is None and re.match(r"^#{1,5} ", line):
                line = "#" * shift + line
            out.append(line)
        text = "\n".join(out)
    md(text)


def code_file(path: Path | str, lang: str = "") -> None:
    md(f"````{lang}\n{Path(path).read_text(encoding='utf-8').rstrip()}\n````")


# ----------------------------------------------------------------------------- słownik kolumn
_MODELS = {"haiku_5_5": "Claude Haiku 5.5", "sonnet_5_5": "Claude Sonnet 5.5", "opus_5_5": "Claude Opus 5.5",
           "fable_5_2": "Claude Fable 5.2", "sedzia": "the adjudicating model"}

COLUMNS: dict[str, str] = {
    # kandydaci / pule
    "forma_podstawowa": "Base (dictionary) form of the item. Equal to `forma_kandydata` unless the models corrected a "
                        "wrong base form (same number of words only).",
    "forma_kandydata": "The candidate exactly as extracted in step 4. All counts, scores and ranks in the row were "
                       "computed for this string.",
    "lematy": "Lemmas of the candidate's words, in order (the key used to count occurrences).",
    "kategoria": "Final label from step 5: `T3` biology term, `T3_INNY` term of another school subject, `T2` school / "
                 "academic vocabulary, `T1` everyday vocabulary, `SZUM` not usable as a test item; `nieklasyfikowany` = "
                 "not sent to the models (in neither pool).",
    "kategoria_final": "Same as `kategoria`, empty when the candidate was not sent to the models.",
    "typ_szumu": "For `SZUM`: `fragment_terminu` part of a longer term, `luzne_polaczenie` free word combination, "
                 "`nazwa_wlasna` proper name, `blad_ekstrakcji` extraction error, `interfejs` platform interface or "
                 "instruction text, `inne` other; `brak` for all other labels.",
    "pelny_termin": "For fragments of a term: the full term the fragment belongs to, as given by the model.",
    "pojecie": "Concept the term belongs to. Terms that are variants, synonyms or derivatives of one concept share "
               "the label; a term without a group is its own concept.",
    "obrazowalnosc": "Model judgement whether the concept can be shown in a picture or diagram (`tak`, `czesciowo`, `nie`).",
    "do_przegladu": "True if no label had a majority among the models, or the adjudicator itself reported low confidence.",
    "zgodnosc_glosow": "How many of the votes carry the final label (for example `2 z 2`, `2 z 3`).",
    "model_sedzia": "Adjudicating model, where the case was adjudicated.",
    "duplikat_formy": "Filled when another row has the same `forma_podstawowa` after correction and is the main row "
                      "for it (this row is then left out of the pools).",
    "warianty": "All candidate strings that name this item after correction (for example `odwłok; odwłoka`, one lemma "
                "split by a tagging error).",
    "freq_cel_laczna": "Occurrences in the target corpus summed over all `warianty`.",
    "freq_kontrast_laczna": "Occurrences in the contrast corpus summed over all `warianty`.",
    "kand_przedmiotowy": "Candidate from the target corpus (passed the subject thresholds).",
    "kand_ogolny": "Candidate from the whole stage corpus, spread over several contrast subjects (source of T1/T2 items).",
    "dlugosc": "Number of words.",
    "pos": "Part of speech used for matching: `rzeczownik` noun, `przymiotnik` adjective, `czasownik` verb, "
           "`przysłówek` adverb, `fraza` multiword, `inne` other.",
    "cls": "Inflectional class of the lemma from Morfeusz2 (`subst` noun, `adj` adjective, `ger` gerund, "
           "`ppas`/`pact` participles, `fin`/`inf`/`praet` verb forms, `adv` adverb); `mwu` for multiword candidates.",
    "freq_cel": "Occurrences in the target corpus (biology).",
    "freq_kontrast": "Occurrences in the contrast corpus (other subjects of the same school stage).",
    "n_mat_cel": "Number of target materials containing the candidate.",
    "n_mat_kontrast": "Number of contrast materials containing the candidate.",
    "n_przedmiotow": "Number of contrast subjects in which the candidate occurs (dispersion).",
    "n_klas_cel": "Number of distinct estimated grades among target materials containing the candidate.",
    "udzial_nazw_wlasnych": "Share of occurrences tagged as a proper name.",
    "freq_kwjp": "Lemma frequency in KWJP100 (general Polish, CC BY 4.0), summed over inflectional classes; gerunds and "
                 "participles are counted from the verb's entry. Empty for multiword candidates.",
    "zipf_kwjp": "Zipf frequency in KWJP100: log₁₀ of occurrences per billion words (single words only).",
    "zipf_wordfreq": "Zipf frequency from `wordfreq` (0 = not found; single words only).",
    "zipf_zpe": "Zipf frequency in the whole stage corpus of ZPE (target + contrast); available for multiword candidates too.",
    "ll_vs_kontrast": "Log-likelihood keyness, target vs contrast corpus; negative when relatively rarer in biology.",
    "log_ratio_kontrast": "Log₂ ratio of relative frequencies, target vs contrast (smoothing 0.5).",
    "ll_vs_kwjp": "Log-likelihood keyness against KWJP100 (single words).",
    "log_ratio_kwjp": "Log₂ ratio of relative frequencies, target vs KWJP100 (single words).",
    "simple_maths_kwjp": "Kilgarriff's Simple Maths keyness against KWJP100 (per-million rates, N = 1; single words).",
    "tfidf_biol": "Relative frequency in biology × log(1 + subjects / (1 + `n_przedmiotow`)).",
    "rozproszenie": "Same value as `n_przedmiotow` (higher = more cross-subject).",
    "pmi": "Multiword candidates: lowest pointwise mutual information among adjacent word pairs of the phrase.",
    "logdice": "Multiword candidates: lowest logDice among adjacent word pairs of the phrase.",
    "cvalue": "TermoPL C-value on the target corpus (empty = not returned by TermoPL).",
    "termopl_ok": "Whether TermoPL ran successfully in this run.",
    "rrf": "Reciprocal-rank fusion of the method rankings (higher = ranked high by several methods).",
    "etykieta_regulowa": "Rule-based pre-label from dispersion and frequency thresholds (`T3?`, `T2?`, `T1?`, "
                         "`nierozstrzygniete`). Kept for comparison only; not shown to the models and not used for the pools.",
    "srebrny_slowniczek": "True if the candidate is an entry of a ZPE glossary in the target materials.",
    "srebrny_pojecie_ref": "True if the candidate is a base form written by ZPE editors for a linked term.",
    "n_liter": "Letters in `forma_podstawowa`, spaces not counted.",
    "zipf_dopasowania": "Frequency used for matching: `zipf_kwjp` for single words, `zipf_zpe` for phrases.",
    "warstwa": "Matching stratum: part of speech for single words, `fraza 2` / `fraza 3` for multiword items.",
    "dopasowanie_ogolne": "General-pool item matched to this term (same stratum, closest frequency and length); "
                          "empty if no item lies within the calipers.",
    "dopasowanie_przedmiotowe": "Subject term this general-pool item is matched to.",
    "dopasowanie_delta_zipf": "Zipf frequency of the term minus that of its match.",
    "dopasowanie_delta_liter": "Letters of the term minus letters of its match.",
    # pojęcia
    "terminy": "Subject-pool terms grouped under the concept, most frequent first.",
    "n_terminow": "Number of terms in the group.",
    "freq_cel_suma": "Occurrences of all terms of the concept in the target corpus.",
    "n_mat_cel_max": "Largest number of target materials among the terms of the concept.",
    # terminy spoza kandydatów
    "termin": "Term listed by the model directly from a material.",
    "kategoria_ekstrakcji": "Category the extracting model gave the term (`T3` biology term, `T2` school vocabulary).",
    "n_materialow": "Number of sampled materials from which the model listed the term.",
    # pseudosłowa
    "szablon": "Real word (noun or verb in base form, from the pools) the pseudoword is paired with.",
    "pseudoslowo": "Pseudoword.",
    "metoda": "Generator: `wuggy_koncowka` Wuggy keeping the template's ending, `wuggy` Wuggy with a free ending, "
              "`unipseudo` UniPseudo letter-trigram chain, `llm` language model, `imbir` ready-made list (Imbir et al. 2015).",
    "metody_wszystkie": "All generators that produced this string.",
    "relacja": "`pochodne` the pseudoword was derived from the template; `dopasowane` it was generated independently "
               "and paired with a template of the same length and part of speech.",
    "wybrane": "True for the recommended list: best-ranked pseudowords of each template that passed the model rating.",
    "pula_szablonu": "Pool the template comes from (`ogolna` general, `przedmiotowa` subject).",
    "ranga_w_szablonie": "Rank among the template's pseudowords by `odstep_od_szablonu` (1 = closest).",
    "odstep_od_szablonu": "Distance from the template in OLD20 and bigram probability (in standard deviations), plus "
                          "0.5 for having an orthographic neighbour and 0.5 for resembling a Ukrainian/Russian word.",
    "oceniane": "True if the pseudoword was sent to the rating model.",
    "ocena_pozytywna": "True if rated: pronounceable enough, not strongly reminiscent of a word, not existing, not "
                       "foreign, not inappropriate (thresholds in the configuration).",
    "ocena_wymawialnosc": "Model rating 1–5: 5 sounds like a natural Polish word, 1 non-Polish letter pattern.",
    "ocena_skojarzenie": "Real Polish word the pseudoword most strongly brings to mind, according to the model.",
    "ocena_podobienstwo": "Model rating 0–3 of the strength of that association: 0 none, 3 practically an existing word.",
    "ocena_istniejace": "Model: the string is an existing Polish word.",
    "ocena_slowo_obce": "Model: existing Ukrainian, Russian, English or German word the string is or sounds like.",
    "ocena_niestosowne": "Model: vulgar, offensive or ridiculing association.",
    "dlugosc_szablon": "Template length in letters.",
    "syl_szablon": "Template syllable count.",
    "syl": "Syllable count.",
    "odleglosc_od_szablonu": "Levenshtein distance between pseudoword and template.",
    "koncowka_zachowana": "True if the pseudoword ends with the template's final rime.",
    "zbitka": "Length of the longest run of consonant letters.",
    "diakryty": "Number of Polish diacritic letters.",
    "old20": "OLD20: mean Levenshtein distance to the 20 nearest lemmas of the reference lexicon (all KWJP100 lemmas "
             "known to Morfeusz2). Lower = denser orthographic neighbourhood.",
    "old20_szablon": "OLD20 of the template.",
    "bigram_lp": "Mean log₁₀ probability of the letter bigrams, word boundaries included (type counts over lemmas).",
    "bigram_lp_szablon": "The same for the template.",
    "min_trigram_typow": "Number of lemmas containing the pseudoword's rarest letter trigram.",
    "n_sasiadow_1": "Number of lemmas at Levenshtein distance 1.",
    "sasiedzi_1": "Up to five of those neighbours.",
    "najblizsze_czeste_slowo": "Frequent word form within Damerau–Levenshtein distance 2, if any.",
    "podobne_ua_ru": "Ukrainian or Russian word (from the 30 000 most frequent of each language, transliterated to "
                     "Polish spelling) that sounds the same up to one letter.",
    "para_blokada": "Template::pseudoword pair, to keep the two from appearing together in one test form.",
    "wuggy_pasmo": "Wuggy search band in which the string was found (lower = transition frequencies closer to the template).",
    "unipseudo_algorytm": "UniPseudo chain type (bigram up to 5 letters, trigram beyond).",
    "unipseudo_modeli": "Number of real words of that length and part of speech the chain was built from.",
    "imbir_n_sedziow": "Imbir et al.: number of the five judges who accepted the string as a good pseudoword.",
    "powod_odrzucenia": "Reason for rejection: `istniejace_slowo` existing word, `ksztalt_niezgodny_ze_wzorcem` length, "
                        "syllables or ending differ from the template, `za_blisko_wzorca` one letter from the template, "
                        "`ortotaktyka` untypical letter pattern, `literowka_czestego_slowa` one edit from a frequent word, "
                        "`homofon` sounds like a real word, `przejrzysta_budowa` existing stem with an affix or a compound, "
                        "`skojarzenie_wulgarne` vulgar association, `slowo_ukrainskie_lub_rosyjskie` Ukrainian or Russian word.",
    "szczegol": "Detail of the rejection (the word, cluster or trigram that triggered it).",
    # złoty zbiór
    "id": "Item identifier.",
    "kandydat": "Candidate to be labelled.",
    "liczba_wyrazow": "Number of words.",
    "wystapienia_biologia": "Occurrences in the biology sample.",
    "wystapienia_inne_przedmioty": "Occurrences in the other subjects of the sample.",
    "liczba_innych_przedmiotow": "Number of other subjects in which the candidate occurs.",
    "zdanie_1": "Sentence from the corpus containing the candidate.",
    "zdanie_2": "Second sentence, from a different material where possible.",
    "zdanie_3": "Third sentence.",
    "kategoria_oceniajacy_A": "To be filled in by annotator A.",
    "kategoria_oceniajacy_B": "To be filled in by annotator B.",
    "forma_poprawna_jesli_inna": "To be filled in only if the base form of the candidate is wrong.",
    "uwagi": "Annotator notes.",
    # ocena lematyzacji
    "zrodlo_referencji": "Where the reference lemma comes from: ZPE editors (`redakcja ZPE`) or provisional (Opus).",
    "forma": "Inflected form as found in the text.",
    "kontekst": "Sentence from the ZPE material containing the form.",
    "lemat_ref": "Reference base form used for scoring.",
    "lemat_ref_tymczasowy_opus": "Provisional reference proposed by Claude Opus 5.5 (to be checked by a human).",
    "pos_ref_tymczasowy_opus": "Provisional part of speech proposed by Claude Opus 5.5.",
    "lemat_poprawny_czlowiek": "To be filled in by the human checker.",
    "pos_poprawny_czlowiek": "To be filled in by the human checker.",
    "material_id": "ZPE material identifier.",
}
for _tool, _label in [("spacy", "spaCy alone"), ("spacy_morfeusz", "spaCy + Morfeusz2 (production)"),
                      ("stanza", "Stanza alone"), ("stanza_morfeusz", "Stanza + Morfeusz2"),
                      ("morfeusz_pierwsza", "Morfeusz2, first reading"),
                      ("llm_haiku_5_5", "Claude Haiku 5.5"), ("llm_sonnet_5_5", "Claude Sonnet 5.5")]:
    COLUMNS[f"{_tool}_lemat"] = f"Base form from {_label}."
    COLUMNS[f"{_tool}_pos"] = f"Part of speech from {_label}."
    COLUMNS[f"{_tool}_ok"] = f"1 if the base form from {_label} equals the reference."
for _m, _label in _MODELS.items():
    COLUMNS[f"{_m}_kategoria"] = f"Label from {_label}."
    COLUMNS[f"{_m}_pewnosc"] = f"Self-reported confidence of {_label} (`wysoka`, `srednia`, `niska`)."
    COLUMNS[f"{_m}_uzasadnienie"] = f"One-sentence reason given by {_label} (in Polish)."
for _c in ["ll_vs_kontrast", "log_ratio_kontrast", "simple_maths_kwjp", "ll_vs_kwjp", "tfidf_biol", "pmi", "logdice", "cvalue", "rrf"]:
    COLUMNS[f"rank_{_c}"] = f"Rank of the candidate by `{_c}` (1 = best)."
