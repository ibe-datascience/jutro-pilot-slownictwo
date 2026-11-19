"""Krok 3. Frekwencje w korpusie ZPE i w zasobach polszczyzny ogólnej (sekcja 4.3).

Wyjście (data/...):
  frekwencje_lemat.parquet   – lemat × (cel/kontrast) + frekwencje ogólne
  frekwencje_forma.parquet   – forma ortograficzna (dla zasobów opartych o formy)
  frekwencje.done
Metryki: frekwencje_43.json (pokrycie, korelacje rang, wpływ na top-300).
"""
from __future__ import annotations

import gzip
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import morf
from .common import Ctx, ROOT, Timer, log, read_jsonl

FREQ_DIR = ROOT / "resources" / "freq"


def _load_kwjp_lemma() -> tuple[dict[str, float], dict[tuple[str, str], float], float]:
    """KWJP100 (CC BY 4.0): lemat → suma freq po klasach; (lemat, klasa) → freq; suma całej listy.

    KWJP zapisuje odsłowniki i imiesłowy pod lematem czasownika („poruszać,ger”), a nasz lemat
    terminologiczny to „poruszanie”. Słownik (lemat, klasa) pozwala policzyć frekwencję takiego lematu
    (patrz `kwjp_freq`). Suma listy (ok. 81,7 mln) jest mianownikiem miar kluczowości względem KWJP.
    """
    path = FREQ_DIR / "kwjp100-slowa-lemma-all.csv.gz"
    out: dict[str, float] = defaultdict(float)
    by_cls: dict[tuple[str, str], float] = defaultdict(float)
    total = 0.0
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        next(fh)  # header
        for line in fh:
            parts = line.rstrip("\n").split(",")
            if len(parts) < 3:
                continue
            lemma, cls, freq = parts[0], parts[1], parts[2]
            try:
                f = float(freq)
            except ValueError:
                continue
            out[lemma.lower()] += f
            by_cls[(lemma.lower(), cls)] += f
            total += f
    return dict(out), dict(by_cls), total


DEVERBAL = ("ger", "pact", "ppas")


def kwjp_freq(lemma_lc: str, kwjp_l: dict[str, float], kwjp_cls: dict[tuple[str, str], float]) -> float:
    """Frekwencja lematu w KWJP z uwzględnieniem odsłowników i imiesłowów zapisanych pod czasownikiem."""
    f = kwjp_l.get(lemma_lc, 0.0)
    seen: set[tuple[str, str]] = set()
    for i in morf.analyse(lemma_lc):
        if i.cls in DEVERBAL:
            key = (i.lemma.lower(), i.cls)
            if key[0] != lemma_lc and key not in seen:
                seen.add(key)
                f += kwjp_cls.get(key, 0.0)
    return f


def zipf_from_freq(freq: float, total: float) -> float:
    """Skala Zipfa (log10 frekwencji na miliard słów) z wygładzeniem +1; 0 wystąpień w 81,7 mln ≈ 1,09."""
    return math.log10((freq + 1.0) / (total + 1.0) * 1e9)


def _load_kwjp_orth_lc() -> dict[str, float]:
    path = FREQ_DIR / "kwjp100-slowa-orth_lc-all.csv.gz"
    out: dict[str, float] = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            parts = line.rstrip("\n").split(",")
            if len(parts) < 2:
                continue
            form, freq = parts[0], parts[1]
            try:
                out[form.lower()] = float(freq)
            except ValueError:
                continue
    return out


def _load_nkjp_forms() -> dict[str, int]:
    """Formy z nkjp_1grams.gz (po usunięciu skrajnej interpunkcji, zsumowane warianty)."""
    import re

    path = FREQ_DIR / "nkjp_1grams.gz"
    raw: dict[str, int] = defaultdict(int)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            # "   12345 word" (uniq -c)
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            try:
                n = int(parts[0])
            except ValueError:
                continue
            form = re.sub(r"^[^\w]+|[^\w]+$", "", parts[1], flags=re.UNICODE).lower()
            if form:
                raw[form] += n
    return dict(raw)


def _load_nkjp1m_lemma() -> dict[str, int]:
    path = FREQ_DIR / "nkjp1m-1.2_lemma_freq.tsv"
    out: dict[str, int] = {}
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            lemma, freq = line.rstrip("\n").split("\t")
            out[lemma.lower()] = int(freq)
    return out


def _load_subtlex_lemma() -> dict[str, float]:
    """SUBTLEX-PL lematy – tylko do metryk porównawczych (CC BY-NC-SA 4.0); nie trafia do CSV produkcyjnych."""
    path = FREQ_DIR / "subtlex-pl-lemmas-master.csv"
    out: dict[str, float] = defaultdict(float)
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        i_lem = header.index("lemma")
        i_freq = header.index("freq")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max(i_lem, i_freq):
                continue
            try:
                out[parts[i_lem].lower()] += float(parts[i_freq])
            except ValueError:
                continue
    return dict(out)


def _wordfreq_zipf(lemma: str) -> float:
    import wordfreq

    try:
        return float(wordfreq.zipf_frequency(lemma, "pl"))
    except Exception:
        return 0.0


def _corpus_stats(ctx: Ctx) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Agregacja z tagi.parquet + metadane materiałów (przedmiot, klasa)."""
    tags = pq.read_table(ctx.data / "tagi.parquet").to_pandas()
    meta = {r["id"]: r for r in read_jsonl(ctx.data / "korpus.jsonl")}
    # tylko tokeny alfabetyczne treściowe
    tags = tags[tags["form"].str.replace("-", "", regex=False).str.isalpha()].copy()
    tags["lemma_lc"] = tags["lemma"].str.lower()
    tags["form_lc"] = tags["form"].str.lower()
    def _przedmiot(m: str) -> str:
        row = meta.get(m, {})
        ps = row.get("przedmioty") or []
        return ps[0] if isinstance(ps, list) and ps else str(row.get("przedmiot") or "")

    def _klasa(m: str) -> str:
        row = meta.get(m, {})
        return str(row.get("klasa_szac_reguly") or row.get("klasa_szacowana") or row.get("klasa") or "")

    tags["przedmiot"] = tags["mat"].map(_przedmiot)
    tags["klasa"] = tags["mat"].map(_klasa)

    def agg(df: pd.DataFrame, key: str) -> pd.DataFrame:
        g = df.groupby(key, sort=False)
        cel = df[df["cel"]].groupby(key)
        kon = df[~df["cel"]].groupby(key)
        out = pd.DataFrame({
            key: g.size().index,
            "freq_all": g.size().values,
            "freq_cel": cel.size().reindex(g.size().index, fill_value=0).astype(int).values,
            "freq_kontrast": kon.size().reindex(g.size().index, fill_value=0).astype(int).values,
            "n_mat_cel": cel["mat"].nunique().reindex(g.size().index, fill_value=0).astype(int).values,
            "n_mat_kontrast": kon["mat"].nunique().reindex(g.size().index, fill_value=0).astype(int).values,
            "n_przedmiotow": kon["przedmiot"].nunique().reindex(g.size().index, fill_value=0).astype(int).values,
            "n_klas_cel": cel["klasa"].nunique().reindex(g.size().index, fill_value=0).astype(int).values,
        })
        return out

    lemmas = agg(tags, "lemma_lc")
    forms = agg(tags, "form_lc")
    info = {
        "n_tokenow_alpha": int(len(tags)),
        "n_tokenow_cel": int(tags["cel"].sum()),
        "n_tokenow_kontrast": int((~tags["cel"]).sum()),
        "n_lematow": int(len(lemmas)),
        "n_form": int(len(forms)),
        "n_materialow_cel": int(tags.loc[tags["cel"], "mat"].nunique()),
        "n_materialow_kontrast": int(tags.loc[~tags["cel"], "mat"].nunique()),
    }
    return lemmas, forms, info


def _spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    from scipy.stats import spearmanr

    r, _ = spearmanr(a, b)
    return None if (r != r) else float(r)


def run(ctx: Ctx) -> None:
    t = Timer()
    log("s03: agregacja frekwencji korpusu…")
    lemmas, forms, info = _corpus_stats(ctx)

    log("s03: wczytywanie zasobów ogólnych (KWJP, NKJP, wordfreq; SUBTLEX tylko do metryk)…")
    kwjp_l, kwjp_cls, kwjp_total = _load_kwjp_lemma()
    kwjp_f = _load_kwjp_orth_lc()
    nkjp_f = _load_nkjp_forms()
    nkjp1m = _load_nkjp1m_lemma()
    subtlex = _load_subtlex_lemma()

    lemmas["freq_kwjp"] = lemmas["lemma_lc"].map(lambda w: kwjp_freq(w, kwjp_l, kwjp_cls))
    lemmas["zipf_kwjp"] = lemmas["freq_kwjp"].map(lambda f: round(zipf_from_freq(f, kwjp_total), 3))
    lemmas["freq_nkjp1m"] = lemmas["lemma_lc"].map(lambda w: float(nkjp1m.get(w, 0)))
    lemmas["freq_subtlex_lemma"] = lemmas["lemma_lc"].map(lambda w: subtlex.get(w, 0.0))
    lemmas["zipf_wordfreq"] = lemmas["lemma_lc"].map(_wordfreq_zipf)
    lemmas["w_kwjp"] = lemmas["freq_kwjp"] > 0
    lemmas["w_nkjp1m"] = lemmas["freq_nkjp1m"] > 0
    lemmas["w_subtlex"] = lemmas["freq_subtlex_lemma"] > 0
    lemmas["w_wordfreq"] = lemmas["zipf_wordfreq"] > 0

    forms["freq_kwjp_orth"] = forms["form_lc"].map(lambda w: kwjp_f.get(w, 0.0))
    forms["freq_nkjp"] = forms["form_lc"].map(lambda w: float(nkjp_f.get(w, 0)))
    forms["w_kwjp_orth"] = forms["freq_kwjp_orth"] > 0
    forms["w_nkjp"] = forms["freq_nkjp"] > 0

    # produkcyjny zasób ogólny: KWJP (CC BY 4.0); SUBTLEX nie wchodzi do kolumn „produkcyjnych” poza metrykami
    lemmas["freq_ogolna"] = lemmas["freq_kwjp"]
    lemmas["zrodlo_ogolne"] = "kwjp100-lemma"

    pq.write_table(pa.Table.from_pandas(lemmas, preserve_index=False), ctx.data / "frekwencje_lemat.parquet",
                   compression="zstd")
    pq.write_table(pa.Table.from_pandas(forms, preserve_index=False), ctx.data / "frekwencje_forma.parquet",
                   compression="zstd")

    # --- metryki 4.3
    cel = lemmas[lemmas["freq_cel"] > 0]
    top = cel.nlargest(300, "freq_cel")
    # wpływ wyboru zasobu na skład top-300: ranking po 1/(1+freq_ogolna) * freq_cel
    def top_set(col: str) -> set[str]:
        s = cel.copy()
        s["_score"] = s["freq_cel"] / (1.0 + s[col].astype(float))
        return set(s.nlargest(300, "_score")["lemma_lc"])

    sets = {
        "kwjp": top_set("freq_kwjp"),
        "nkjp1m": top_set("freq_nkjp1m"),
        "wordfreq_inv": set(
            cel.assign(_s=cel["freq_cel"] / (1.0 + 10 ** (cel["zipf_wordfreq"] - 3).clip(lower=0)))
            .nlargest(300, "_s")["lemma_lc"]
        ),
        "subtlex": top_set("freq_subtlex_lemma"),
    }
    overlap = {f"{a}_vs_{b}": round(len(sets[a] & sets[b]) / 300, 4)
               for a in sets for b in sets if a < b}

    # korelacje rang na lematach obecnych w ≥2 zasobach i w biologii
    sample = cel[cel["freq_cel"] >= 3].copy()
    pairs = [
        ("freq_kwjp", "freq_nkjp1m"),
        ("freq_kwjp", "freq_subtlex_lemma"),
        ("freq_kwjp", "zipf_wordfreq"),
        ("freq_nkjp1m", "freq_subtlex_lemma"),
    ]
    corrs = {}
    for x, y in pairs:
        mask = (sample[x] > 0) & (sample[y] > 0)
        corrs[f"spearman_{x}_vs_{y}"] = _spearman(
            sample.loc[mask, x].astype(float).tolist(),
            sample.loc[mask, y].astype(float).tolist(),
        )
        corrs[f"n_{x}_vs_{y}"] = int(mask.sum())

    info["kwjp_suma_listy"] = kwjp_total
    metrics = {
        "korpus": info,
        "jednostki": {
            "kwjp": "lemma × class (sumowane do lematu; odsłowniki i imiesłowy doliczane spod lematu czasownika); "
                    "plik kwjp100-slowa-lemma-all.csv.gz; zipf_kwjp = log10((freq+1)/(suma listy+1)*1e9)",
            "nkjp_1grams": "forma ortograficzna (po strip interpunkcji)",
            "nkjp1m": "lemat ręczny z podkorpusu 1M",
            "subtlex": "lemat (subtlex-pl-lemmas-master.csv); CC BY-NC-SA 4.0 – tylko metryki",
            "wordfreq": "forma case-folded → zipf; dane CC BY-SA 4.0",
        },
        "pokrycie_lematow_cel": {
            "n": int(len(cel)),
            "kwjp": round(float(cel["w_kwjp"].mean()), 4),
            "nkjp1m": round(float(cel["w_nkjp1m"].mean()), 4),
            "subtlex": round(float(cel["w_subtlex"].mean()), 4),
            "wordfreq": round(float(cel["w_wordfreq"].mean()), 4),
        },
        "pokrycie_form_cel": {
            "n": int((forms["freq_cel"] > 0).sum()),
            "kwjp_orth": round(float(forms.loc[forms["freq_cel"] > 0, "w_kwjp_orth"].mean()), 4),
            "nkjp": round(float(forms.loc[forms["freq_cel"] > 0, "w_nkjp"].mean()), 4),
        },
        "korelacje_rang_lematy_biol_freq_cel_ge_3": corrs,
        "wplyw_zasobu_na_top300_score_freq_cel_nad_1_plus_ogolna": overlap,
        "rekomendacja_produkcyjna": "KWJP100 lemma (CC BY 4.0); SUBTLEX tylko do porównań wewnętrznych",
        "czas_s": round(t.s, 1),
    }
    ctx.save_metrics("frekwencje_43", metrics)
    (ctx.data / "frekwencje.done").write_text("ok\n", encoding="utf-8")
    log(f"s03: gotowe w {t.s:.1f}s; lematów={info['n_lematow']}, pokrycie KWJP={metrics['pokrycie_lematow_cel']['kwjp']}")
