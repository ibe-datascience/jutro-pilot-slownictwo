"""Krok 6. Pule przedmiotowa / ogólna, dopasowanie, pojęcia, złoty zbiór do oznaczenia, kandydaci.csv.

Pule powstają wyłącznie z etykiet końcowych kroku 5 (LLM): T3 → pula przedmiotowa, T1/T2 → pula ogólna.
Kandydaci bez etykiety LLM zostają w `kandydaci.csv` jako `nieklasyfikowany` i nie trafiają do pul.

Dopasowanie: każdemu terminowi T3 szukamy w puli ogólnej jednostki o tej samej liczbie wyrazów i tej samej
części mowy, najbliższej pod względem frekwencji ogólnej (skala Zipfa) i długości w literach. Przypisanie jest
optymalne (algorytm węgierski, bez powtórzeń) i ograniczone progami („caliper”): para o zbyt dużej różnicy
nie powstaje, a termin zostaje bez pary.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .common import Ctx, Timer, log
from .s05_llm import context_lines

POS = {"subst": "rzeczownik", "ger": "rzeczownik", "depr": "rzeczownik", "adj": "przymiotnik", "pact": "przymiotnik",
       "ppas": "przymiotnik", "fin": "czasownik", "inf": "czasownik", "praet": "czasownik", "adv": "przysłówek",
       "mwu": "fraza"}
CATS = ["T3", "T3_INNY", "T2", "T1", "SZUM"]


def _merge(ctx: Ctx) -> pd.DataFrame:
    stat = pq.read_table(ctx.data / "kandydaci_stat.parquet").to_pandas()
    stat.insert(1, "forma_kandydata", stat["forma_podstawowa"])
    stat["pos"] = stat["cls"].map(POS).fillna("inne")
    llm_path = ctx.data / "llm_klasyfikacja.parquet"
    if not llm_path.exists():
        log("s06: brak llm_klasyfikacja.parquet – wszystkie wiersze pozostają nieklasyfikowane")
        stat["kategoria"] = "nieklasyfikowany"
        for c in ("kategoria_final", "typ_szumu", "pelny_termin", "obrazowalnosc", "zgodnosc_glosow"):
            stat[c] = None
        stat["do_przegladu"] = False
        return stat
    lab = pq.read_table(llm_path).to_pandas()
    keep = ["forma_wejsciowa", "kategoria_final", "typ_szumu", "forma_poprawna", "pelny_termin", "obrazowalnosc",
            "zgodnosc_glosow", "do_przegladu", "model_sedzia"]
    keep += [c for c in lab.columns if c.endswith(("_kategoria", "_pewnosc", "_uzasadnienie")) and c not in keep]
    m = stat.merge(lab[keep], left_on="forma_kandydata", right_on="forma_wejsciowa", how="left").drop(columns="forma_wejsciowa")
    m["forma_podstawowa"] = m["forma_poprawna"].fillna(m["forma_kandydata"])
    m = m.drop(columns="forma_poprawna")
    m["kategoria"] = m["kategoria_final"].fillna("nieklasyfikowany")
    m["do_przegladu"] = m["do_przegladu"].fillna(False).astype(bool)
    # Po poprawce formy kilka wierszy może nazywać tę samą jednostkę (np. „odwłoka” i „odwłok” – jeden lemat rozbity
    # przez błąd tagera). Wiersz główny: z etykietą modelu, w pierwszej kolejności ten, którego forma nie wymagała
    # poprawki, potem najczęstszy. Pozostałe wskazują go w `duplikat_formy` i nie wchodzą do pul.
    m["_native"] = m["forma_kandydata"] == m["forma_podstawowa"]
    m["_lab"] = m["kategoria_final"].notna()
    order = m.sort_values(["_lab", "_native", "freq_cel", "freq_kontrast"], ascending=False)
    first = order.drop_duplicates("forma_podstawowa", keep="first")
    main = dict(zip(first["forma_podstawowa"], first["forma_kandydata"]))
    m["duplikat_formy"] = [None if main[f] == k else main[f] for f, k in zip(m["forma_podstawowa"], m["forma_kandydata"])]
    # łączna frekwencja wszystkich wariantów jednostki (statystyki metod pozostają policzone dla `forma_kandydata`)
    grp = m.groupby("forma_podstawowa")
    m["freq_cel_laczna"] = grp["freq_cel"].transform("sum")
    m["freq_kontrast_laczna"] = grp["freq_kontrast"].transform("sum")
    var = grp["forma_kandydata"].agg(lambda s: "; ".join(sorted(s)) if len(s) > 1 else "")
    m["warianty"] = m["forma_podstawowa"].map(var)
    m = m.drop(columns=["_native", "_lab"])

    # jednowyrazowa forma poprawiona: część mowy i frekwencja ogólna mają dotyczyć formy poprawionej
    from . import morf
    from .s03_frekwencje import _load_kwjp_lemma, kwjp_freq, zipf_from_freq

    changed = m.index[(m["forma_podstawowa"] != m["forma_kandydata"]) & (m["dlugosc"] == 1)]
    if len(changed):
        kwjp_l, kwjp_cls, kwjp_total = _load_kwjp_lemma()
        cls2pos = {"inf": "czasownik", "subst": "rzeczownik", "adj": "przymiotnik", "adv": "przysłówek"}
        for i in changed:
            w = m.at[i, "forma_podstawowa"]
            ints = [x for x in morf.analyse(w) if x.lemma.lower() == w and x.cls in cls2pos]
            if ints:
                # przy kilku odczytaniach zostaje część mowy kandydata, jeśli jest wśród nich
                poss = [cls2pos[x.cls] for x in ints]
                m.at[i, "pos"] = m.at[i, "pos"] if m.at[i, "pos"] in poss else poss[0]
            f = kwjp_freq(w, kwjp_l, kwjp_cls)
            m.at[i, "freq_kwjp"] = f
            m.at[i, "zipf_kwjp"] = round(zipf_from_freq(f, kwjp_total), 3)
    return m


def _zipf_key(df: pd.DataFrame) -> pd.Series:
    """Frekwencja do dopasowania: KWJP (lemat) dla słów, korpus ZPE etapu dla fraz (KWJP nie ma frekwencji fraz)."""
    return df["zipf_kwjp"].where(df["dlugosc"] == 1, df["zipf_zpe"])


def _match(pred: pd.DataFrame, ogol: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    from scipy.optimize import linear_sum_assignment

    max_dz = float(cfg.get("max_roznica_zipf", 1.0))
    max_dl = int(cfg.get("max_roznica_liter", 3))
    w_len = float(cfg.get("waga_dlugosci", 0.25))
    pred, ogol = pred.copy(), ogol.copy()
    for df in (pred, ogol):
        df["zipf_dopasowania"] = _zipf_key(df).round(3)
        df["n_liter"] = df["forma_podstawowa"].str.replace(" ", "", regex=False).str.len()
        df["warstwa"] = np.where(df["dlugosc"] == 1, df["pos"], "fraza " + df["dlugosc"].clip(upper=3).astype(str))
    pred["dopasowanie_ogolne"] = None
    pred["dopasowanie_delta_zipf"] = np.nan
    pred["dopasowanie_delta_liter"] = np.nan
    ogol["dopasowanie_przedmiotowe"] = None
    BIG = 1e6
    per_stratum = {}
    for st, p in pred.groupby("warstwa"):
        g = ogol[ogol["warstwa"] == st]
        info = {"terminy": int(len(p)), "pula_ogolna": int(len(g)), "dopasowane": 0}
        if len(g):
            dz = np.abs(p["zipf_dopasowania"].to_numpy()[:, None] - g["zipf_dopasowania"].to_numpy()[None, :])
            dl = np.abs(p["n_liter"].to_numpy()[:, None] - g["n_liter"].to_numpy()[None, :])
            lim = max_dl if st in POS.values() and not st.startswith("fraza") else max_dl * 2
            cost = dz + w_len * dl
            cost[(dz > max_dz) | (dl > lim) | np.isnan(dz)] = BIG
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if cost[r, c] >= BIG:
                    continue
                pi, gi = p.index[r], g.index[c]
                pred.at[pi, "dopasowanie_ogolne"] = g.at[gi, "forma_podstawowa"]
                pred.at[pi, "dopasowanie_delta_zipf"] = round(float(p.at[pi, "zipf_dopasowania"] - g.at[gi, "zipf_dopasowania"]), 3)
                pred.at[pi, "dopasowanie_delta_liter"] = int(p.at[pi, "n_liter"] - g.at[gi, "n_liter"])
                ogol.at[gi, "dopasowanie_przedmiotowe"] = p.at[pi, "forma_podstawowa"]
                info["dopasowane"] += 1
        info["udzial"] = round(info["dopasowane"] / info["terminy"], 4) if info["terminy"] else None
        per_stratum[str(st)] = info
    mt = pred[pred["dopasowanie_ogolne"].notna()]
    part = ogol[ogol["dopasowanie_przedmiotowe"].notna()]

    def smd(a: pd.Series, b: pd.Series) -> float | None:
        s = np.sqrt((a.var() + b.var()) / 2)
        return round(float((a.mean() - b.mean()) / s), 3) if len(a) > 1 and len(b) > 1 and s > 0 else None

    metrics = {
        "progi": {"max_roznica_zipf": max_dz, "max_roznica_liter": max_dl, "max_roznica_liter_frazy": max_dl * 2,
                  "waga_dlugosci": w_len},
        "n_terminow": int(len(pred)), "n_dopasowanych": int(len(mt)),
        "udzial_dopasowanych": round(len(mt) / len(pred), 4) if len(pred) else None,
        "wg_warstwy": per_stratum,
        "srednia_abs_delta_zipf": round(float(mt["dopasowanie_delta_zipf"].abs().mean()), 3) if len(mt) else None,
        "srednia_abs_delta_liter": round(float(mt["dopasowanie_delta_liter"].abs().mean()), 3) if len(mt) else None,
        # standaryzowana różnica średnich: przed dopasowaniem (całe pule) i po (tylko pary)
        "smd_zipf_przed": smd(pred["zipf_dopasowania"].dropna(), ogol["zipf_dopasowania"].dropna()),
        "smd_zipf_po": smd(mt["zipf_dopasowania"], part["zipf_dopasowania"]),
        "smd_liter_przed": smd(pred["n_liter"], ogol["n_liter"]),
        "smd_liter_po": smd(mt["n_liter"], part["n_liter"]),
        "zipf_srednia": {"terminy": round(float(pred["zipf_dopasowania"].mean()), 3) if len(pred) else None,
                         "pula_ogolna": round(float(ogol["zipf_dopasowania"].mean()), 3) if len(ogol) else None},
    }
    return pred, ogol, metrics


def _concepts(ctx: Ctx, pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = ctx.data / "llm_pojecia.json"
    groups = json.loads(path.read_text(encoding="utf-8")).get("grupy", []) if path.exists() else []
    concept = {}
    for g in groups:
        for term in g["terminy"]:
            concept[term] = g["pojecie"]
    pred = pred.copy()
    pred["pojecie"] = [concept.get(f, f) for f in pred["forma_podstawowa"]]
    rank = {"tak": 0, "czesciowo": 1, "nie": 2}
    rows = []
    for p, g in pred.groupby("pojecie", sort=True):
        ob = sorted((x for x in g["obrazowalnosc"].dropna()), key=lambda x: rank.get(x, 9))
        rows.append({
            "pojecie": p,
            "terminy": "; ".join(g.sort_values("freq_cel", ascending=False)["forma_podstawowa"]),
            "n_terminow": int(len(g)),
            "obrazowalnosc": ob[0] if ob else "",
            "freq_cel_suma": int(g["freq_cel"].sum()),
            "n_mat_cel_max": int(g["n_mat_cel"].max()),
            "dopasowanie_ogolne": "; ".join(x for x in g["dopasowanie_ogolne"].dropna()),
        })
    return pred, pd.DataFrame(rows)


def _gold(ctx: Ctx, merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Arkusz do podwójnego oznaczenia: warstwowo po etykiecie końcowej i trudności, bez etykiet modeli."""
    n_gold = int(ctx.cfg.get("zloty_zbior", {}).get("n", 400))
    pool = merged[merged["kategoria"].isin(CATS) & merged["duplikat_formy"].isna()].copy()
    if pool.empty:
        pool = merged.copy()
        pool["kategoria"] = "nieklasyfikowany"
    pool["trudny"] = pool["do_przegladu"] | pool.get("sedzia_kategoria", pd.Series(index=pool.index, dtype=object)).notna()
    pool["warstwa"] = pool["kategoria"] + np.where(pool["trudny"], " / rozstrzygany", " / zgodny")
    cats = [c for c in CATS if (pool["kategoria"] == c).any()] or ["nieklasyfikowany"]
    per_cat = n_gold // len(cats)
    picks = []
    for i, cat in enumerate(cats):
        g = pool[pool["kategoria"] == cat]
        hard, easy = g[g["trudny"]], g[~g["trudny"]]
        n_hard = min(len(hard), per_cat // 2)
        n_easy = min(len(easy), per_cat - n_hard)
        n_hard = min(len(hard), per_cat - n_easy)
        if n_hard:
            picks.append(hard.sample(n=n_hard, random_state=ctx.seed + i))
        if n_easy:
            picks.append(easy.sample(n=n_easy, random_state=ctx.seed + 100 + i))
    gold = pd.concat(picks) if picks else pool.head(0)
    if len(gold) < n_gold:
        rest = pool.drop(gold.index)
        gold = pd.concat([gold, rest.sample(n=min(n_gold - len(gold), len(rest)), random_state=ctx.seed + 999)])
    gold = gold.sample(frac=1.0, random_state=ctx.seed).reset_index(drop=True)  # kolejność nie zdradza warstwy
    sizes = pool["warstwa"].value_counts()
    taken = gold["warstwa"].value_counts()
    gold["waga"] = [round(sizes[w] / taken[w], 4) for w in gold["warstwa"]]
    gold.insert(0, "id", [f"G{i + 1:03d}" for i in range(len(gold))])

    k = pq.read_table(ctx.data / "kandydaci_konteksty.parquet").to_pandas() if (ctx.data / "kandydaci_konteksty.parquet").exists() \
        else pd.DataFrame(columns=["forma_podstawowa", "cel", "przedmiot", "tekst"])
    by_form: dict[str, list[tuple[bool, str, str]]] = {}
    for f, cel, subj, text in zip(k["forma_podstawowa"], k["cel"], k["przedmiot"], k["tekst"]):
        by_form.setdefault(f, []).append((bool(cel), subj, text))
    sents = [context_lines(by_form.get(f, []), bool(s)) for f, s in zip(gold["forma_kandydata"], gold["kand_przedmiotowy"])]
    sheet = pd.DataFrame({
        "id": gold["id"],
        "kandydat": gold["forma_kandydata"],
        "liczba_wyrazow": gold["dlugosc"],
        "wystapienia_biologia": gold["freq_cel"],
        "wystapienia_inne_przedmioty": gold["freq_kontrast"],
        "liczba_innych_przedmiotow": gold["n_przedmiotow"],
        "zdanie_1": [s[0] if len(s) > 0 else "" for s in sents],
        "zdanie_2": [s[1] if len(s) > 1 else "" for s in sents],
        "zdanie_3": [s[2] if len(s) > 2 else "" for s in sents],
        "kategoria_oceniajacy_A": "",
        "kategoria_oceniajacy_B": "",
        "forma_poprawna_jesli_inna": "",
        "uwagi": "",
    })
    key_cols = ["id", "forma_kandydata", "forma_podstawowa", "kategoria", "typ_szumu", "warstwa", "waga", "do_przegladu"] + \
        [c for c in gold.columns if c.endswith("_kategoria")]
    return sheet, gold[key_cols]


INSTRUKCJA = [
    ("Zadanie", "W kolumnie kategoria_oceniajacy_A (druga osoba: _B) wpisz jedną z etykiet: T3, T3_INNY, T2, T1, SZUM. "
                "Oceniaj znaczenie, w jakim kandydat występuje w podanych zdaniach. Nie konsultuj etykiet z drugą osobą."),
    ("T3", "Termin biologiczny: pojęcie poznawane na lekcjach biologii lub przyrody (chloroplast, fotosynteza, stawonóg, "
           "samożywny, łańcuch pokarmowy), także pojęcia chemii i fizyki nauczane w biologii (dwutlenek węgla, enzym)."),
    ("T3_INNY", "Termin innego przedmiotu szkolnego, spoza treści biologii (mianownik, epitet, południk)."),
    ("T2", "Słownictwo szkolno-akademickie wspólne dla wielu przedmiotów (analizować, wniosek, cecha, czynnik, występować)."),
    ("T1", "Słownictwo codzienne znane dziecku niezależnie od szkoły (pies, drzewo, serce, woda, jeść), w tym powszechnie "
           "znane nazwy zwierząt, roślin i części ciała."),
    ("SZUM", "Jednostka nie nadaje się na pozycję testu: fragment większego terminu (gębowy ← aparat gębowy), luźne "
             "połączenie słów (organizm człowieka), nazwa własna, błąd ekstrakcji, tekst interfejsu platformy."),
    ("forma_poprawna_jesli_inna", "Wypełnij tylko wtedy, gdy forma podstawowa kandydata jest błędna (np. odwłoka → odwłok)."),
    ("Statystyki", "Liczby wystąpień pochodzą z próbki materiałów ZPE i są tylko wskazówką."),
]


def _gold_evaluation(ctx: Ctx) -> dict[str, Any] | None:
    """Jeśli obok leży wypełniony arkusz `zloty_zbior_oznaczony.xlsx`, porównaj etykiety modeli z ludzkimi."""
    path, key_path = ctx.out / "zloty_zbior_oznaczony.xlsx", ctx.data / "zloty_zbior_klucz.csv"
    if not path.exists() or not key_path.exists():
        return None
    sheet = pd.read_excel(path)
    key = pd.read_csv(key_path)
    d = sheet.merge(key, on="id", how="inner")
    a, b = d["kategoria_oceniajacy_A"].astype(str).str.strip(), d["kategoria_oceniajacy_B"].astype(str).str.strip()
    ok_a, ok_b = a.isin(CATS), b.isin(CATS)
    out: dict[str, Any] = {"n_wierszy": int(len(d)), "n_oznaczonych_A": int(ok_a.sum()), "n_oznaczonych_B": int(ok_b.sum())}
    if not ok_a.any():
        return out
    from .s05_llm import _cohen_kappa

    both = ok_a & ok_b
    if both.any():
        out["zgodnosc_A_B"] = {"n": int(both.sum()), "prosta": round(float((a[both] == b[both]).mean()), 4),
                               "kappa": _cohen_kappa(a[both].tolist(), b[both].tolist())}
    w = d.loc[ok_a, "waga"]
    hit = (d.loc[ok_a, "kategoria"] == a[ok_a])
    out["trafnosc_etykiety_koncowej_vs_A"] = {"prosta": round(float(hit.mean()), 4),
                                              "wazona": round(float((hit * w).sum() / w.sum()), 4)}
    per = {}
    for c in CATS:
        pred_c, true_c = d.loc[ok_a, "kategoria"] == c, a[ok_a] == c
        tp = float((w * (pred_c & true_c)).sum())
        p = tp / float((w * pred_c).sum()) if pred_c.any() else None
        r = tp / float((w * true_c).sum()) if true_c.any() else None
        per[c] = {"precyzja": round(p, 4) if p is not None else None, "pelnosc": round(r, 4) if r is not None else None,
                  "f1": round(2 * p * r / (p + r), 4) if p and r else None, "n_A": int(true_c.sum())}
    out["wg_kategorii_wazone"] = per
    return out


def run(ctx: Ctx) -> None:
    t = Timer()
    merged = _merge(ctx)
    main = merged[merged["duplikat_formy"].isna()] if "duplikat_formy" in merged else merged
    pred = main[main["kategoria"] == "T3"].copy()
    ogol = main[main["kategoria"].isin(["T1", "T2"])].copy()
    pred, ogol, match_metrics = _match(pred, ogol, ctx.cfg.get("dopasowanie", {}) or {})
    pred, pojecia = _concepts(ctx, pred)
    merged["pojecie"] = merged["forma_podstawowa"].map(dict(zip(pred["forma_podstawowa"], pred["pojecie"])))
    sheet, key = _gold(ctx, merged)

    out = ctx.out
    front = ["forma_podstawowa", "forma_kandydata", "kategoria", "typ_szumu", "pelny_termin", "pojecie", "obrazowalnosc",
             "do_przegladu", "zgodnosc_glosow", "duplikat_formy", "kand_przedmiotowy", "kand_ogolny", "dlugosc", "pos", "cls"]
    front = [c for c in front if c in merged.columns]
    merged[front + [c for c in merged.columns if c not in front]].to_csv(out / "kandydaci.csv", index=False)
    pfront = ["forma_podstawowa", "pojecie", "obrazowalnosc", "dopasowanie_ogolne", "dopasowanie_delta_zipf",
              "dopasowanie_delta_liter", "dlugosc", "pos", "n_liter", "zipf_dopasowania"]
    pred[pfront + [c for c in pred.columns if c not in pfront]].to_csv(out / "pula_przedmiotowa.csv", index=False)
    ofront = ["forma_podstawowa", "kategoria", "dopasowanie_przedmiotowe", "dlugosc", "pos", "n_liter", "zipf_dopasowania"]
    ogol[ofront + [c for c in ogol.columns if c not in ofront]].to_csv(out / "pula_ogolna.csv", index=False)
    pojecia.to_csv(out / "pojecia.csv", index=False)
    with pd.ExcelWriter(out / "zloty_zbior_do_oznaczenia.xlsx") as xw:
        sheet.to_excel(xw, sheet_name="do_oznaczenia", index=False)
        pd.DataFrame(INSTRUKCJA, columns=["pole", "opis"]).to_excel(xw, sheet_name="instrukcja", index=False)
    key.to_csv(ctx.data / "zloty_zbior_klucz.csv", index=False)

    (ctx.data / "pule.done").write_text("ok\n", encoding="utf-8")
    metrics = {
        "n_kandydaci_csv": int(len(merged)),
        "n_pula_przedmiotowa": int(len(pred)),
        "n_pula_przedmiotowa_wielowyrazowe": int((pred["dlugosc"] > 1).sum()),
        "n_pula_ogolna": int(len(ogol)),
        "n_pula_ogolna_T1": int((ogol["kategoria"] == "T1").sum()),
        "n_pula_ogolna_T2": int((ogol["kategoria"] == "T2").sum()),
        "n_pojec": int(len(pojecia)),
        "n_pojec_wieloterminowych": int((pojecia["n_terminow"] > 1).sum()) if len(pojecia) else 0,
        "n_zloty": int(len(sheet)),
        "zloty_warstwy": key["warstwa"].value_counts().to_dict() if len(key) else {},
        "n_duplikatow_formy": int(merged["duplikat_formy"].notna().sum()) if "duplikat_formy" in merged else 0,
        "n_do_przegladu_w_pulach": int(pred["do_przegladu"].sum() + ogol["do_przegladu"].sum()),
        "rozklad_kategorii": merged["kategoria"].value_counts().to_dict(),
        "pula_przedmiotowa_pos": pred["pos"].value_counts().to_dict(),
        "pula_ogolna_pos": ogol["pos"].value_counts().to_dict(),
        "obrazowalnosc_T3": pred["obrazowalnosc"].value_counts().to_dict(),
        "dopasowanie": match_metrics,
        "zloty_ocena": _gold_evaluation(ctx),
        "czas_s": round(t.s, 1),
    }
    ctx.save_metrics("pule_6", metrics)
    log(f"s06: T3={len(pred)} T1/T2={len(ogol)} dopasowane={match_metrics['n_dopasowanych']} "
        f"pojęcia={len(pojecia)} złoty={len(sheet)}")
