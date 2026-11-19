"""Krok 4. Ekstrakcja kandydatów na terminy (sekcja 4.2) + wstępny podział regułowy.

Metody (wszystkie na tych samych danych; żadna nie zastępuje innej po cichu):
  * kluczowość względem polszczyzny ogólnej (KWJP): log-likelihood + log ratio + simple maths
  * kontrast między przedmiotami ZPE: TF-IDF + rozproszenie (n_przedmiotów)
  * TermoPL (C-value) na korpusie docelowym
  * wzorce składniowe NP + PMI / logDice dla MWU
  * (ekstrakcja LLM – w s05)

Wyjście:
  kandydaci_stat.parquet – jeden wiersz na kandydata (forma podstawowa) ze statystykami i rangami metod
  kandydaci_stat.parquet.done
Metryki: ekstrakcja_42.json (precyzja@K względem srebrnego standardu ZPE).
"""
from __future__ import annotations

import csv
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import morf
from .common import Ctx, ROOT, Timer, log, read_jsonl
from .frazy import iter_phrases
from .morf import Tok

CONTENT_CLS = {"subst", "ger", "depr", "adj", "pact", "ppas", "adv", "fin", "inf", "praet"}


def _ll_score(a: float, b: float, A: float, B: float) -> float:
    """Dwustronny log-likelihood (Rayson & Garside / Dunning) dla frekwencji a w korpusie A vs b w B."""
    if a <= 0 and b <= 0:
        return 0.0
    N = A + B
    if N <= 0:
        return 0.0
    e1 = A * (a + b) / N
    e2 = B * (a + b) / N
    s = 0.0
    if a > 0 and e1 > 0:
        s += a * math.log(a / e1)
    if b > 0 and e2 > 0:
        s += b * math.log(b / e2)
    return 2.0 * s


def _log_ratio(a: float, b: float, A: float, B: float, smooth: float = 0.5) -> float:
    return math.log2(((a + smooth) / (A + smooth)) / ((b + smooth) / (B + smooth)))


def _simple_maths(a: float, b: float, A: float, B: float, N: float = 1.0) -> float:
    """Simple Maths (Kilgarriff): (r_focus + N) / (r_ref + N) with relative frequencies per million-ish."""
    rf = (a / A * 1e6) if A else 0.0
    rr = (b / B * 1e6) if B else 0.0
    return (rf + N) / (rr + N)


def _pmi(xy: float, x: float, y: float, n: float) -> float:
    if xy <= 0 or x <= 0 or y <= 0 or n <= 0:
        return 0.0
    return math.log2((xy * n) / (x * y))


def _logdice(xy: float, x: float, y: float) -> float:
    if xy <= 0 or x <= 0 or y <= 0:
        return -math.inf
    return 14.0 + math.log2(2.0 * xy / (x + y))


def _collect_candidates(ctx: Ctx) -> tuple[pd.DataFrame, dict[str, Any]]:
    tags = pq.read_table(ctx.data / "tagi.parquet").to_pandas()
    tags = tags[tags["form"].str.replace("-", "", regex=False).str.isalpha()].copy()
    freq = pq.read_table(ctx.data / "frekwencje_lemat.parquet").to_pandas().set_index("lemma_lc")
    max_len = int(ctx.cfg["kandydaci"]["max_dlugosc"])
    min_f = int(ctx.cfg["kandydaci"]["min_frekw_cel"])
    min_m = int(ctx.cfg["kandydaci"]["min_materialow"])

    # --- jednowyrazowe
    singles: dict[str, dict[str, Any]] = {}
    for (mat, cel), g in tags.groupby(["mat", "cel"], sort=False):
        for form, lemma, cls, known in zip(g["form"], g["lemma"], g["cls"], g["known"]):
            if cls not in CONTENT_CLS or not known:
                continue
            if len(lemma) < 3 or not lemma.replace("-", "").isalpha():
                continue
            key = lemma.lower()
            rec = singles.setdefault(key, {
                "forma_podstawowa": key, "dlugosc": 1, "cls": cls,
                "freq_cel": 0, "freq_kontrast": 0, "mats_cel": set(), "mats_kontrast": set(),
                "przedmioty": set(), "klasy": set(),
            })
            if cel:
                rec["freq_cel"] += 1
                rec["mats_cel"].add(mat)
            else:
                rec["freq_kontrast"] += 1
                rec["mats_kontrast"].add(mat)

    meta = {r["id"]: r for r in read_jsonl(ctx.data / "korpus.jsonl")}

    def _klasa(row: dict) -> str:
        return str(row.get("klasa_szac_reguly") or row.get("klasa_szacowana") or row.get("klasa") or "")

    def _przedmioty(row: dict) -> list[str]:
        ps = row.get("przedmioty")
        if isinstance(ps, list) and ps:
            return [str(p) for p in ps]
        if row.get("przedmiot"):
            return [str(row["przedmiot"])]
        return []

    for key, rec in singles.items():
        for m in rec["mats_cel"]:
            k = _klasa(meta.get(m, {}))
            if k:
                rec["klasy"].add(k)
        for m in rec["mats_kontrast"]:
            for p in _przedmioty(meta.get(m, {})):
                rec["przedmioty"].add(p)

    # --- wielowyrazowe z wzorców składniowych (tylko korpus docelowy do kandydatów T3;
    #     kontrast liczymy osobno na tych samych formach podstawowych)
    mwu_cel: dict[str, dict[str, Any]] = {}
    mwu_pair_cel: Counter = Counter()  # (w1,w2) for bigram collocations inside phrases
    unigram_cel: Counter = Counter()
    n_tokens_cel = 0

    target = tags[tags["cel"]].copy()
    for (mat, seg, sent), g in target.groupby(["mat", "seg", "sent"], sort=False):
        toks = [Tok(f, l, c, ca, n, ge, bool(k)) for f, l, c, ca, n, ge, k in
                zip(g["form"], g["lemma"], g["cls"], g["case"], g["num"], g["gen"], g["known"])]
        for t in toks:
            if t.cls in CONTENT_CLS and t.known:
                unigram_cel[t.lemma.lower()] += 1
                n_tokens_cel += 1
        for s, e in iter_phrases(toks, max_len):
            span = toks[s:e]
            if len(span) < 2:
                continue
            base, ok = morf.phrase_base(span, plural=False)
            if not base or not ok:
                continue
            key = base.lower()
            rec = mwu_cel.setdefault(key, {
                "forma_podstawowa": key, "dlugosc": len(span), "cls": "mwu",
                "freq_cel": 0, "freq_kontrast": 0, "mats_cel": set(), "mats_kontrast": set(),
                "przedmioty": set(), "klasy": set(), "ok_fraza": True,
            })
            rec["freq_cel"] += 1
            rec["mats_cel"].add(mat)
            k = _klasa(meta.get(mat, {}))
            if k:
                rec["klasy"].add(k)
            # collocations: adjacent content lemmas in the phrase
            lemmas = [t.lemma.lower() for t in span]
            for a, b in zip(lemmas, lemmas[1:]):
                mwu_pair_cel[(a, b)] += 1

    # frekwencja MWU w kontraście (te same formy podstawowe – skan fraz)
    contrast = tags[~tags["cel"]]
    wanted_mwu = set(mwu_cel)
    if wanted_mwu:
        for (mat, seg, sent), g in contrast.groupby(["mat", "seg", "sent"], sort=False):
            toks = [Tok(f, l, c, ca, n, ge, bool(k)) for f, l, c, ca, n, ge, k in
                    zip(g["form"], g["lemma"], g["cls"], g["case"], g["num"], g["gen"], g["known"])]
            for s, e in iter_phrases(toks, max_len):
                span = toks[s:e]
                base, ok = morf.phrase_base(span, plural=False)
                if not ok:
                    continue
                key = base.lower()
                if key not in wanted_mwu:
                    continue
                rec = mwu_cel[key]
                rec["freq_kontrast"] += 1
                rec["mats_kontrast"].add(mat)
                for p in _przedmioty(meta.get(mat, {})):
                    rec["przedmioty"].add(p)

    rows = []
    for src in (singles, mwu_cel):
        for key, rec in src.items():
            n_mat_cel = len(rec["mats_cel"])
            if rec["freq_cel"] < min_f or n_mat_cel < min_m:
                continue
            fr = freq.loc[key] if key in freq.index else None
            rows.append({
                "forma_podstawowa": key,
                "dlugosc": rec["dlugosc"],
                "cls": rec.get("cls", ""),
                "freq_cel": rec["freq_cel"],
                "freq_kontrast": rec["freq_kontrast"],
                "n_mat_cel": n_mat_cel,
                "n_mat_kontrast": len(rec["mats_kontrast"]),
                "n_przedmiotow": len(rec["przedmioty"]),
                "n_klas_cel": len(rec["klasy"]),
                "freq_kwjp": float(fr["freq_kwjp"]) if fr is not None else 0.0,
                "zipf_wordfreq": float(fr["zipf_wordfreq"]) if fr is not None else _zipf(key),
            })
    df = pd.DataFrame(rows)
    extras = {
        "mwu_pair_cel": mwu_pair_cel,
        "unigram_cel": unigram_cel,
        "n_tokens_cel": n_tokens_cel,
    }
    return df, extras


def _zipf(w: str) -> float:
    try:
        import wordfreq
        return float(wordfreq.zipf_frequency(w.split()[0], "pl")) if " " not in w else 0.0
    except Exception:
        return 0.0


def _score_methods(df: pd.DataFrame, extras: dict[str, Any], N_cel: float, N_kon: float) -> pd.DataFrame:
    df = df.copy()
    df["ll_vs_kontrast"] = [
        _ll_score(a, b, N_cel, N_kon) * (1 if a / max(N_cel, 1) >= b / max(N_kon, 1) else -1)
        for a, b in zip(df["freq_cel"], df["freq_kontrast"])
    ]
    df["log_ratio_kontrast"] = [_log_ratio(a, b, N_cel, N_kon) for a, b in zip(df["freq_cel"], df["freq_kontrast"])]
    # względem KWJP: traktujemy freq_kwjp jako frekwencję w „korpusie odniesienia” o umownej wielkości
    # (suma frekwencji KWJP nie jest potrzebna do rankingu względnego – używamy simple maths + log ratio vs ipm)
    kwjp_total = max(float(df["freq_kwjp"].sum()), 1.0)  # niedokładne, ale stałe dla rankingu w tym zbiorze
    df["ll_vs_kwjp"] = [
        _ll_score(a, max(k, 0.0), N_cel, max(kwjp_total, N_cel)) for a, k in zip(df["freq_cel"], df["freq_kwjp"])
    ]
    df["log_ratio_kwjp"] = [_log_ratio(a, max(k, 0.0), N_cel, max(kwjp_total, N_cel))
                            for a, k in zip(df["freq_cel"], df["freq_kwjp"])]
    df["simple_maths_kwjp"] = [_simple_maths(a, max(k, 0.0), N_cel, max(kwjp_total, N_cel))
                               for a, k in zip(df["freq_cel"], df["freq_kwjp"])]
    # TF-IDF przedmiotowy: tf w biologii * idf po przedmiotach (1+n_przedmiotów w kontraście)
    n_subj = max(int(df["n_przedmiotow"].max()) + 1, 2)
    df["tfidf_biol"] = (df["freq_cel"] / N_cel) * np.log1p(n_subj / (1 + df["n_przedmiotow"]))
    df["rozproszenie"] = df["n_przedmiotow"]  # im wyższe, tym bardziej T2

    # kolokacje dla MWU (bigram z pierwszej pary lematów)
    pairs = extras["mwu_pair_cel"]
    uni = extras["unigram_cel"]
    n = float(extras["n_tokens_cel"] or 1)
    pmis, dices = [], []
    for form, L in zip(df["forma_podstawowa"], df["dlugosc"]):
        if L < 2:
            pmis.append(0.0)
            dices.append(0.0)
            continue
        parts = form.split()
        if len(parts) < 2:
            pmis.append(0.0)
            dices.append(0.0)
            continue
        a, b = parts[0], parts[1]
        xy = float(pairs.get((a, b), 0))
        pmis.append(_pmi(xy, float(uni.get(a, 0)), float(uni.get(b, 0)), n))
        dices.append(_logdice(xy, float(uni.get(a, 0)), float(uni.get(b, 0))))
    df["pmi"] = pmis
    df["logdice"] = [x if math.isfinite(x) else 0.0 for x in dices]

    # rangi metod (wyższe = lepsze; NaN → na koniec)
    for col, ascending in [
        ("ll_vs_kontrast", False), ("log_ratio_kontrast", False), ("simple_maths_kwjp", False),
        ("ll_vs_kwjp", False), ("tfidf_biol", False), ("pmi", False), ("logdice", False),
    ]:
        df[f"rank_{col}"] = df[col].rank(ascending=ascending, method="min")
    return df


def _run_termopl(ctx: Ctx) -> pd.DataFrame | None:
    """Uruchom TermoPL na tekstach docelowych; zwróć DataFrame z cvalue albo None przy niepowodzeniu."""
    script = ROOT / "resources" / "tools" / "termopl" / "run_termopl.sh"
    if not script.exists():
        log("s04: brak run_termopl.sh – TermoPL pominięty")
        return None
    txt_dir = ctx.data / "termopl_txt"
    work = ctx.data / "termopl_work"
    out_tsv = ctx.data / "termopl_terms.tsv"
    txt_dir.mkdir(parents=True, exist_ok=True)
    # jeden plik na materiał docelowy
    n = 0
    for row in read_jsonl(ctx.data / "korpus.jsonl"):
        if not row["cel"]:
            continue
        texts = [s["tekst"] for s in row["segmenty"] if s["typ"] in ctx.cfg["czyszczenie"]["segmenty_do_statystyk"]]
        body = "\n\n".join(texts)
        if len(body.split()) < 20:
            continue
        (txt_dir / f"{row['id']}.txt").write_text(body, encoding="utf-8")
        n += 1
    if n == 0:
        return None
    max_len = int(ctx.cfg["kandydaci"]["max_dlugosc"])
    log(f"s04: TermoPL na {n} plikach…")
    try:
        subprocess.run(
            ["bash", str(script), str(txt_dir), str(work), str(out_tsv), str(max_len)],
            check=True, timeout=3600,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        log(f"s04: TermoPL nieudany: {exc}")
        return None
    if not out_tsv.exists():
        return None
    df = pd.read_csv(out_tsv, sep="\t")
    # kolumny z run_termopl.sh
    base_col = "base_form" if "base_form" in df.columns else df.columns[3]
    cv_col = "cvalue" if "cvalue" in df.columns else None
    if cv_col is None:
        return None
    out = df[[base_col, cv_col]].rename(columns={base_col: "forma_podstawowa", cv_col: "cvalue"})
    out["forma_podstawowa"] = out["forma_podstawowa"].astype(str).str.lower().str.strip()
    out = out.groupby("forma_podstawowa", as_index=False)["cvalue"].max()
    return out


def _rule_label(row: pd.Series) -> str:
    """Wstępny podział regułowy (nie ostateczna etykieta)."""
    if row["dlugosc"] >= 2 and row["log_ratio_kontrast"] >= 1.5 and row["n_przedmiotow"] <= 2:
        return "T3?"
    if row["dlugosc"] == 1 and row["log_ratio_kontrast"] >= 2.0 and row["zipf_wordfreq"] < 3.5 and row["n_przedmiotow"] <= 3:
        return "T3?"
    if row["n_przedmiotow"] >= 5 and row["zipf_wordfreq"] < 4.5:
        return "T2?"
    if row["zipf_wordfreq"] >= 4.5:
        return "T1?"
    return "do_llm"


def _silver_sets(ctx: Ctx) -> dict[str, set[str]]:
    gloss: set[str] = set()
    refs: set[str] = set()
    gpath = ctx.data / "srebrny_slowniczek.csv"
    if gpath.exists():
        with open(gpath, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                for col in ("termin", "haslo", "forma_podstawowa", "lemma"):
                    if r.get(col):
                        gloss.add(r[col].strip().lower())
                        break
    rpath = ctx.data / "srebrny_pojecie_ref.csv"
    if rpath.exists():
        with open(rpath, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("cel") == "1" and r.get("forma_podstawowa"):
                    refs.add(r["forma_podstawowa"].strip().lower())
    return {"slowniczek": gloss, "pojecie_ref": refs}


def _precision_at(ranked: list[str], gold: set[str], ks: list[int]) -> dict[str, float]:
    out = {}
    for k in ks:
        top = ranked[:k]
        if not top:
            out[f"p@{k}"] = 0.0
            continue
        out[f"p@{k}"] = round(sum(1 for x in top if x in gold) / len(top), 4)
    # recall vs gold (spośród gold obecnych w ranked)
    in_pool = [g for g in gold if g in set(ranked)]
    if in_pool:
        for k in ks:
            out[f"r@{k}"] = round(sum(1 for x in ranked[:k] if x in gold) / len(in_pool), 4)
    return out


def run(ctx: Ctx) -> None:
    t = Timer()
    log("s04: zbieranie kandydatów…")
    df, extras = _collect_candidates(ctx)
    N_cel = float(df["freq_cel"].sum()) if len(df) else 1.0
    # przybliżenie wielkości kontrastu: z frekwencji lematów
    freq = pq.read_table(ctx.data / "frekwencje_lemat.parquet").to_pandas()
    N_kon = float(freq["freq_kontrast"].sum()) or 1.0
    df = _score_methods(df, extras, N_cel, N_kon)

    termopl = _run_termopl(ctx)
    if termopl is not None:
        df = df.merge(termopl, on="forma_podstawowa", how="left")
        df["cvalue"] = df["cvalue"].fillna(0.0)
        df["rank_cvalue"] = df["cvalue"].rank(ascending=False, method="min")
        df["termopl_ok"] = True
    else:
        df["cvalue"] = 0.0
        df["rank_cvalue"] = np.nan
        df["termopl_ok"] = False

    df["etykieta_regulowa"] = [_rule_label(r) for _, r in df.iterrows()]
    # metody → listy rankingowe
    method_cols = {
        "ll_kontrast": "ll_vs_kontrast",
        "log_ratio_kontrast": "log_ratio_kontrast",
        "simple_maths_kwjp": "simple_maths_kwjp",
        "tfidf_biol": "tfidf_biol",
        "pmi_mwu": "pmi",
        "logdice_mwu": "logdice",
        "cvalue_termopl": "cvalue",
    }
    silver = _silver_sets(ctx)
    gold = silver["slowniczek"] | silver["pojecie_ref"]
    metrics: dict[str, Any] = {
        "n_kandydatow": int(len(df)),
        "n_jednowyrazowych": int((df["dlugosc"] == 1).sum()),
        "n_mwu": int((df["dlugosc"] > 1).sum()),
        "termopl": bool(termopl is not None),
        "srebrny": {k: len(v) for k, v in silver.items()},
        "precyzja_wzgledem_srebrnego": {},
        "etykiety_regulowe": df["etykieta_regulowa"].value_counts().to_dict(),
    }
    for name, col in method_cols.items():
        if col == "cvalue" and termopl is None:
            metrics["precyzja_wzgledem_srebrnego"][name] = {"status": "niedostepne"}
            continue
        ranked = df.sort_values(col, ascending=False)["forma_podstawowa"].tolist()
        metrics["precyzja_wzgledem_srebrnego"][name] = {
            "vs_union": _precision_at(ranked, gold, [100, 300, 1000]),
            "vs_slowniczek": _precision_at(ranked, silver["slowniczek"], [100, 300, 1000]),
            "vs_pojecie_ref": _precision_at(ranked, silver["pojecie_ref"], [100, 300, 1000]),
        }

    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), ctx.data / "kandydaci_stat.parquet",
                   compression="zstd")
    (ctx.data / "kandydaci_stat.parquet.done").write_text("ok\n", encoding="utf-8")
    metrics["czas_s"] = round(t.s, 1)
    ctx.save_metrics("ekstrakcja_42", metrics)
    log(f"s04: {len(df)} kandydatów w {t.s:.1f}s; TermoPL={'tak' if termopl is not None else 'nie'}")
