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
            df[c] = df[c].round(3)
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
_MODELS = {"haiku_5_5": "Claude Haiku 5.5", "sonnet_5_5": "Claude Sonnet 5.5", "opus_5_5": "Claude Opus 5.5"}

COLUMNS: dict[str, str] = {
    # kandydaci / pule
    "forma_podstawowa": "Base (dictionary) form of the candidate. Where the LLM returned a different base form, "
                        "this is the LLM's form; compare with `forma_kandydata`.",
    "forma_kandydata": "The candidate exactly as extracted in step 4. All counts, scores and ranks in the row were "
                       "computed for this string.",
    "form_changed": "Derived for this page: `yes` if `forma_podstawowa` differs from `forma_kandydata`.",
    "dlugosc": "Number of words in `forma_kandydata`.",
    "cls": "Inflectional class of the lemma from Morfeusz2 (`subst` noun, `adj` adjective, `ger` gerund, "
           "`ppas`/`pact` participles, `fin`/`inf`/`praet` verb forms, `adv` adverb); `mwu` for multiword candidates.",
    "freq_cel": "Occurrences in the target corpus (biology).",
    "freq_kontrast": "Occurrences in the contrast corpus (other subjects of the same school stage).",
    "n_mat_cel": "Number of target materials containing the candidate.",
    "n_mat_kontrast": "Number of contrast materials containing the candidate.",
    "n_przedmiotow": "Number of contrast subjects in which the candidate occurs (dispersion).",
    "n_klas_cel": "Number of distinct estimated grades among target materials containing the candidate.",
    "freq_kwjp": "Lemma frequency in KWJP100 (general Polish, CC BY 4.0), summed over inflectional classes.",
    "zipf_wordfreq": "Zipf frequency from `wordfreq` (0 = not found; single words only).",
    "ll_vs_kontrast": "Log-likelihood keyness, target vs contrast corpus; negative when relatively rarer in biology.",
    "log_ratio_kontrast": "Log₂ ratio of relative frequencies, target vs contrast (smoothing 0.5).",
    "ll_vs_kwjp": "Log-likelihood keyness against KWJP100 (reference size is a convention; use for ranking only).",
    "log_ratio_kwjp": "Log₂ ratio of relative frequencies, target vs KWJP100.",
    "simple_maths_kwjp": "Kilgarriff's Simple Maths keyness against KWJP100 (per-million rates, N = 1).",
    "tfidf_biol": "Relative frequency in biology × log(1 + subjects / (1 + `n_przedmiotow`)).",
    "rozproszenie": "Same value as `n_przedmiotow` (higher = more cross-subject, i.e. more T2-like).",
    "pmi": "Pointwise mutual information of the first two lemmas of a multiword candidate (0 for single words).",
    "logdice": "logDice of the first two lemmas of a multiword candidate (0 for single words).",
    "cvalue": "TermoPL C-value on the target corpus (0 = not returned by TermoPL).",
    "termopl_ok": "Whether TermoPL ran successfully in this run.",
    "etykieta_regulowa": "Rule-based pre-label from frequency thresholds (`T3?`, `T2?`, `T1?`, `do_llm` = undecided).",
    "kategoria_final": "LLM label (empty if the candidate was not sent to the LLM).",
    "kategoria": "Label used for the pools: the LLM label where available, otherwise the rule-based pre-label.",
    "label_source": "Derived for this page: `LLM` if `kategoria` comes from the models, `rule` if only from the rule-based pre-label.",
    "forma_podstawowa_llm": "Base form returned by the LLM.",
    "pojecie": "Short concept label from the LLM, shared by variants and synonyms.",
    "obrazowalnosc": "LLM judgement whether the concept can be shown in a picture or diagram (`tak`, `czesciowo`, `nie`).",
    "do_przegladu": "True if the models disagreed or one had low confidence, so Opus adjudicated.",
    "forma_join": "Candidate form as sent to the LLM (join key).",
    "zipf_bin": "Zipf frequency bin (half-unit steps) used for matching.",
    "cls_bin": "Class bin used for matching (`mwu` for multiword).",
    "dopasowanie_ogolne": "General-pool item matched to this term on length and Zipf frequency.",
    "dopasowanie_przedmiotowe": "Subject-pool term this item was matched to.",
    # pojęcia
    "terminy": "Subject-pool terms grouped under the concept.",
    "n_terminow": "Number of terms in the group.",
    # pseudosłowa
    "szablon": "Real word (single-word general-pool item) used as the template.",
    "pseudoslowo": "Generated pseudoword.",
    "metoda": "Generator: `wuggy`, `unipseudo`, `imbir` (ready-made list, not template-based) or `llm`.",
    "dlugosc_szablon": "Template length in letters.",
    "syl_szablon": "Template syllable count.",
    "syl": "Syllable count.",
    "zbitka": "Length of the longest run of consonant letters.",
    "diakryty": "Number of Polish diacritic letters.",
    "para_blokada": "Template::pseudoword pair, to keep the two from appearing together in one test form.",
    "podobne_ua_ru": "Coarse flag: within edit distance 2 of a transliterated Ukrainian/Russian word from a short list.",
    "old20": "Approximate OLD20: mean edit distance to the 20 nearest of 2 000 forms sampled from the corpus lexicon.",
    "powod_odrzucenia": "Reason for rejection (`znane_morfeusz` = known to Morfeusz2, `literowka_edit1` = one edit from a "
                        "real word, `prefiks/sufiks_na_istniejacym` = productive affix on an existing stem).",
    # złoty zbiór
    "id": "Item identifier.",
    "metoda_top": "Extraction method that ranked the candidate highest.",
    "warstwa_freq": "Frequency quartile stratum (target corpus).",
    "warstwa_dl": "Length stratum (1, 2, 3–4 words).",
    "kategoria_oceniajacy_A": "To be filled in by annotator A.",
    "kategoria_oceniajacy_B": "To be filled in by annotator B.",
    "uwagi": "Annotator notes.",
    # ocena lematyzacji
    "warstwa": "Sample stratum: rare term, multiword expression, other.",
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
for _c in ["ll_vs_kontrast", "log_ratio_kontrast", "simple_maths_kwjp", "ll_vs_kwjp", "tfidf_biol", "pmi", "logdice", "cvalue"]:
    COLUMNS[f"rank_{_c}"] = f"Rank of the candidate by `{_c}` (1 = best)."
