"""Krok 6. Pule przedmiotowa / ogólna, pojęcia, złoty zbiór do oznaczenia, kandydaci.csv."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from .common import Ctx, Timer, log


def _match_key(row: pd.Series) -> tuple:
    return (int(row["dlugosc"]), int(row.get("zipf_bin", 0)), str(row.get("cls_bin", "x")))


def run(ctx: Ctx) -> None:
    t = Timer()
    stat = pq.read_table(ctx.data / "kandydaci_stat.parquet").to_pandas()
    # forma, dla której policzono statystyki (krok 4); `forma_podstawowa` może niżej zostać
    # zastąpiona formą zwróconą przez LLM, więc zachowujemy oryginał w osobnej kolumnie
    stat.insert(1, "forma_kandydata", stat["forma_podstawowa"])
    llm_path = ctx.data / "llm_klasyfikacja.parquet"
    if llm_path.exists():
        lab = pq.read_table(llm_path).to_pandas()
        # mapuj po forma_wejsciowa
        lab = lab.rename(columns={"forma_wejsciowa": "forma_join"})
        merged = stat.merge(
            lab[["forma_join", "kategoria_final", "forma_podstawowa", "pojecie", "obrazowalnosc", "do_przegladu"]
                + [c for c in lab.columns if c.endswith("_kategoria") or c.endswith("_pewnosc")]],
            left_on="forma_podstawowa", right_on="forma_join", how="left", suffixes=("", "_llm"),
        )
        if "forma_podstawowa_llm" in merged.columns:
            merged["forma_podstawowa"] = merged["forma_podstawowa_llm"].fillna(merged["forma_podstawowa"])
        merged["kategoria"] = merged["kategoria_final"].fillna(
            merged["etykieta_regulowa"].str.replace("?", "", regex=False)
        )
    else:
        log("s06: brak llm_klasyfikacja.parquet – używam etykiet regułowych")
        merged = stat.copy()
        merged["kategoria"] = merged["etykieta_regulowa"].str.replace("?", "", regex=False)
        merged["pojecie"] = merged["forma_podstawowa"]
        merged["obrazowalnosc"] = ""
        merged["do_przegladu"] = False

    # pule
    pred = merged[merged["kategoria"] == "T3"].copy()
    ogol = merged[merged["kategoria"].isin(["T1", "T2"])].copy()
    # dopasowanie: zipf bin + długość
    for df in (pred, ogol):
        df["zipf_bin"] = (df["zipf_wordfreq"].fillna(0).clip(0, 7) * 2).astype(int)
        df["cls_bin"] = df["cls"].where(df["dlugosc"] == 1, "mwu")

    # dla każdego T3 znajdź najbliższy T1/T2 o tej samej długości i zbliżonym zipf
    used = set()
    keys = []
    for _, r in pred.iterrows():
        cands = ogol[(ogol["dlugosc"] == r["dlugosc"]) & ~ogol["forma_podstawowa"].isin(used)]
        if cands.empty:
            cands = ogol[~ogol["forma_podstawowa"].isin(used)]
        if cands.empty:
            keys.append("")
            continue
        cands = cands.assign(_d=(cands["zipf_wordfreq"] - r["zipf_wordfreq"]).abs())
        pick = cands.nsmallest(1, "_d").iloc[0]
        used.add(pick["forma_podstawowa"])
        keys.append(pick["forma_podstawowa"])
    pred["dopasowanie_ogolne"] = keys
    ogol["dopasowanie_przedmiotowe"] = ogol["forma_podstawowa"].map(
        {v: k for k, v in zip(pred["forma_podstawowa"], pred["dopasowanie_ogolne"]) if v}
    )

    # pojęcia: grupuj po polu pojecie (z LLM) lub forma
    poj_map: dict[str, list[str]] = defaultdict(list)
    obraz: dict[str, str] = {}
    def _s(v: Any) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(v).strip()

    for _, r in pred.iterrows():
        p = (_s(r.get("pojecie")) or _s(r.get("forma_podstawowa"))).lower()
        if not p:
            continue
        form = _s(r.get("forma_podstawowa"))
        if not form:
            continue
        poj_map[p].append(form)
        ob = _s(r.get("obrazowalnosc"))
        if ob:
            obraz[p] = ob
    pojecia = pd.DataFrame([
        {"pojecie": p, "terminy": "; ".join(sorted(set(ts))), "n_terminow": len(set(ts)),
         "obrazowalnosc": obraz.get(p, "")}
        for p, ts in sorted(poj_map.items())
    ])

    # złoty zbiór 400 warstwowo (bez etykiet modeli)
    rng = ctx.rng("zloty")
    n_gold = int(ctx.cfg.get("zloty_zbior", {}).get("n", 400))
    if ctx.probka:
        n_gold = min(n_gold, 200)
    pool = merged.copy()
    pool["warstwa_dl"] = pd.cut(pool["dlugosc"].clip(1, 4), bins=[0, 1, 2, 4], labels=["1", "2", "3-4"])
    pool["warstwa_freq"] = pd.qcut(pool["freq_cel"].rank(method="first"), q=4, labels=["q1", "q2", "q3", "q4"])
    # metoda: najwyższa ranga wśród metod
    rank_cols = [c for c in pool.columns if c.startswith("rank_")]
    if rank_cols:
        pool["metoda_top"] = pool[rank_cols].idxmin(axis=1).str.replace("rank_", "", regex=False)
    else:
        pool["metoda_top"] = "brak"
    gold_rows = []
    groups = list(pool.groupby(["metoda_top", "warstwa_freq", "warstwa_dl"], observed=True))
    per = max(1, n_gold // max(len(groups), 1))
    for _, g in groups:
        take = g.sample(n=min(per, len(g)), random_state=ctx.seed)
        gold_rows.append(take)
    gold = pd.concat(gold_rows).drop_duplicates("forma_podstawowa")
    if len(gold) < n_gold:
        extra = pool[~pool["forma_podstawowa"].isin(gold["forma_podstawowa"])].sample(
            n=min(n_gold - len(gold), len(pool)), random_state=ctx.seed + 1
        )
        gold = pd.concat([gold, extra])
    gold = gold.head(n_gold).copy()
    gold_out = gold[["forma_podstawowa", "dlugosc", "freq_cel", "freq_kontrast", "n_przedmiotow",
                     "zipf_wordfreq", "metoda_top", "warstwa_freq", "warstwa_dl"]].copy()
    gold_out.insert(0, "id", [f"G{i+1:03d}" for i in range(len(gold_out))])
    gold_out["kategoria_oceniajacy_A"] = ""
    gold_out["kategoria_oceniajacy_B"] = ""
    gold_out["uwagi"] = ""

    out = ctx.out
    cols_k = [c for c in merged.columns if not c.startswith("forma_join")]
    merged[cols_k].to_csv(out / "kandydaci.csv", index=False)
    pred.to_csv(out / "pula_przedmiotowa.csv", index=False)
    ogol.to_csv(out / "pula_ogolna.csv", index=False)
    pojecia.to_csv(out / "pojecia.csv", index=False)
    gold_out.to_excel(out / "zloty_zbior_do_oznaczenia.xlsx", index=False)

    (ctx.data / "pule.done").write_text("ok\n", encoding="utf-8")
    ctx.save_metrics("pule_6", {
        "n_kandydaci_csv": int(len(merged)),
        "n_pula_przedmiotowa": int(len(pred)),
        "n_pula_ogolna": int(len(ogol)),
        "n_pojec": int(len(pojecia)),
        "n_zloty": int(len(gold_out)),
        "rozklad_kategorii": merged["kategoria"].value_counts().to_dict(),
        "czas_s": round(t.s, 1),
    })
    log(f"s06: T3={len(pred)} T1/T2={len(ogol)} pojęcia={len(pojecia)} złoty={len(gold_out)}")
