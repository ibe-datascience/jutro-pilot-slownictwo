"""Krok 4. Ekstrakcja kandydatów na terminy (sekcja 4.2) + kandydaci do puli ogólnej.

Kandydaci przedmiotowi (do puli T3) pochodzą z korpusu docelowego; kandydaci ogólni (do puli T1/T2)
z całego korpusu etapu – słowa i frazy szeroko rozproszone po przedmiotach, niezależnie od tego,
czy występują w biologii.

Metody rankingowe (wszystkie na tych samych danych; żadna nie zastępuje innej po cichu):
  * kontrast między przedmiotami ZPE: log-likelihood, log ratio, TF-IDF po przedmiotach
  * kluczowość względem polszczyzny ogólnej (KWJP100): log-likelihood, log ratio, simple maths
    – tylko dla jednostek jednowyrazowych (KWJP nie ma frekwencji fraz)
  * TermoPL (C-value) na korpusie docelowym, łączony po ciągu lematów
  * wzorce składniowe NP + PMI / logDice dla fraz (najsłabsze ogniwo sąsiednich par lematów)
  * RRF – połączenie rang powyższych metod (reciprocal rank fusion)
  * (ekstrakcja LLM – w s05)

Wyjście:
  kandydaci_stat.parquet       – jeden wiersz na kandydata ze statystykami i rangami metod
  kandydaci_konteksty.parquet  – do 3 zdań z korpusu na kandydata (dla LLM i arkusza złotego zbioru)
  kandydaci_stat.parquet.done
Metryki: ekstrakcja_42.json (precyzja@K i pełność@K względem srebrnego standardu ZPE, pokrycie standardu).
"""
from __future__ import annotations

import csv
import itertools
import math
import re
import subprocess
from collections import Counter
from functools import lru_cache
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
WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)


# --------------------------------------------------------------------------------------
# Miary
# --------------------------------------------------------------------------------------
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


def _signed_ll(a: float, b: float, A: float, B: float) -> float:
    """Log-likelihood ze znakiem: ujemny, gdy jednostka jest względnie rzadsza w korpusie docelowym."""
    return _ll_score(a, b, A, B) * (1 if a / max(A, 1) >= b / max(B, 1) else -1)


def _log_ratio(a: float, b: float, A: float, B: float, smooth: float = 0.5) -> float:
    return math.log2(((a + smooth) / (A + smooth)) / ((b + smooth) / (B + smooth)))


def _simple_maths(a: float, b: float, A: float, B: float, N: float = 1.0) -> float:
    """Simple Maths (Kilgarriff): (f_cel + N) / (f_odn + N) na frekwencjach na milion słów."""
    rf = (a / A * 1e6) if A else 0.0
    rr = (b / B * 1e6) if B else 0.0
    return (rf + N) / (rr + N)


def _pmi(xy: float, x: float, y: float, n: float) -> float:
    if xy <= 0 or x <= 0 or y <= 0 or n <= 0:
        return float("nan")
    return math.log2((xy * n) / (x * y))


def _logdice(xy: float, x: float, y: float) -> float:
    if xy <= 0 or x <= 0 or y <= 0:
        return float("nan")
    return 14.0 + math.log2(2.0 * xy / (x + y))


def _zipf(freq: float, total: float) -> float:
    return math.log10((freq + 1.0) / (total + 1.0) * 1e9)


# --------------------------------------------------------------------------------------
# Zbieranie kandydatów
# --------------------------------------------------------------------------------------
class Rec:
    """Liczniki jednej jednostki (lematu albo frazy)."""

    __slots__ = ("lem", "n", "cls", "f_cel", "f_kon", "m_cel", "m_kon", "last", "subj", "klasy", "propn",
                 "ex_cel", "ex_kon", "ex_last", "ex_subj")

    def __init__(self, lem: tuple[str, ...], cls: str) -> None:
        self.lem, self.n, self.cls = lem, len(lem), cls
        self.f_cel = self.f_kon = self.m_cel = self.m_kon = 0
        self.last = -1
        self.subj = 0      # maska bitowa przedmiotów kontrastu
        self.klasy = 0     # maska bitowa szacowanych klas materiałów docelowych
        self.propn = 0
        self.ex_cel: list[int] = []
        self.ex_kon: list[int] = []
        self.ex_last = -1
        self.ex_subj = 0

    def add(self, cel: bool, mat: int, subj_mask: int, klasa_bit: int, sid: int, ex_ok: bool) -> None:
        new_mat = mat != self.last
        self.last = mat
        if cel:
            self.f_cel += 1
            if new_mat:
                self.m_cel += 1
            self.klasy |= klasa_bit
            if ex_ok and len(self.ex_cel) < 3 and (mat != self.ex_last or len(self.ex_cel) == 1 and self.f_cel > 2):
                self.ex_cel.append(sid)
                self.ex_last = mat
        else:
            self.f_kon += 1
            if new_mat:
                self.m_kon += 1
            self.subj |= subj_mask
            # przykłady z kontrastu: po jednym na nowy przedmiot
            if ex_ok and len(self.ex_kon) < 3 and (subj_mask & ~self.ex_subj):
                self.ex_kon.append(sid)
                self.ex_subj |= subj_mask


@lru_cache(maxsize=400_000)
def _phrase_base(span: tuple[Tok, ...]) -> tuple[str, bool]:
    return morf.phrase_base(list(span), plural=False)


def _detok(forms: list[str]) -> str:
    s = " ".join(forms)
    s = re.sub(r"\s+([,.;:!?%…)\]”])", r"\1", s)
    s = re.sub(r"([(\[„])\s+", r"\1", s)
    return s


def _collect(ctx: Ctx) -> dict[str, Any]:
    cols = ["mat", "cel", "seg", "sent", "form", "lemma", "cls", "case", "num", "gen", "known", "upos"]
    tags = pq.read_table(ctx.data / "tagi.parquet", columns=cols).to_pandas()
    max_len = int(ctx.cfg["kandydaci"]["max_dlugosc"])

    meta = {r["id"]: r for r in read_jsonl(ctx.data / "korpus.jsonl")}
    mat_codes, mat_names = pd.factorize(tags["mat"], sort=False)
    subjects: dict[str, int] = {}
    mat_subj_mask: list[int] = []
    mat_subj_name: list[str] = []
    mat_klasa_bit: list[int] = []
    for m in mat_names:
        row = meta.get(m, {})
        ps = row.get("przedmioty") if isinstance(row.get("przedmioty"), list) else [row.get("przedmiot")]
        ps = [str(p) for p in ps if p]
        mask = 0
        if not row.get("cel"):
            for p in ps:
                mask |= 1 << subjects.setdefault(p, len(subjects))
        mat_subj_mask.append(mask)
        mat_subj_name.append(ps[0] if ps else "")
        k = row.get("klasa_szac_reguly")
        mat_klasa_bit.append(1 << int(k) if isinstance(k, (int, float)) and k == k and k else 0)

    form = tags["form"].to_numpy(dtype=object)
    lemma = tags["lemma"].to_numpy(dtype=object)
    cls = tags["cls"].to_numpy(dtype=object)
    case = tags["case"].fillna("").to_numpy(dtype=object)
    num = tags["num"].fillna("").to_numpy(dtype=object)
    gen = tags["gen"].fillna("").to_numpy(dtype=object)
    known = tags["known"].to_numpy(dtype=bool)
    propn = (tags["upos"] == "PROPN").to_numpy(dtype=bool)
    cel = tags["cel"].to_numpy(dtype=bool)
    alpha = tags["form"].str.replace("-", "", regex=False).str.isalpha().to_numpy(dtype=bool)
    seg = tags["seg"].to_numpy()
    sent = tags["sent"].to_numpy()
    n = len(tags)
    change = (mat_codes[1:] != mat_codes[:-1]) | (seg[1:] != seg[:-1]) | (sent[1:] != sent[:-1])
    starts = np.concatenate(([0], np.nonzero(change)[0] + 1))
    ends = np.concatenate((starts[1:], [n]))
    del tags

    singles: dict[str, Rec] = {}
    mwus: dict[str, Rec] = {}
    uni_cel: Counter = Counter()     # lemat → frekwencja wśród wszystkich wyrazów korpusu docelowego
    pair_cel: Counter = Counter()    # (lemat, lemat) sąsiednich wyrazów w zdaniu, korpus docelowy
    n_cel = n_kon = 0

    for sid in range(len(starts)):
        s, e = int(starts[sid]), int(ends[sid])
        m = int(mat_codes[s])
        is_cel = bool(cel[s])
        smask, kbit = mat_subj_mask[m], mat_klasa_bit[m]
        n_alpha = int(alpha[s:e].sum())
        if is_cel:
            n_cel += n_alpha
        else:
            n_kon += n_alpha
        ex_ok = 6 <= n_alpha <= 40
        lem_lc = [str(lemma[k]).lower() for k in range(s, e)]

        prev = None
        for k in range(s, e):
            if not alpha[k]:
                prev = None  # interpunkcja i liczby przerywają sąsiedztwo
                continue
            l = lem_lc[k - s]
            if is_cel:
                uni_cel[l] += 1
                if prev is not None:
                    pair_cel[(prev, l)] += 1
            prev = l
            if cls[k] not in CONTENT_CLS or not known[k] or len(l) < 3:
                continue
            rec = singles.get(l)
            if rec is None:
                rec = singles[l] = Rec((l,), cls[k])
            rec.add(is_cel, m, smask, kbit, sid, ex_ok)
            if propn[k]:
                rec.propn += 1

        # frazy: na pełnym ciągu tokenów zdania (interpunkcja ma klasę `interp` i nie pasuje do wzorca)
        toks = [Tok(form[k], lemma[k], cls[k], case[k], num[k], gen[k], bool(known[k])) for k in range(s, e)]
        for ps, pe in iter_phrases(toks, max_len):
            if pe - ps < 2:
                continue
            base, ok = _phrase_base(tuple(toks[ps:pe]))
            if not base or not ok:
                continue
            key = base.lower()
            rec = mwus.get(key)
            if rec is None:
                rec = mwus[key] = Rec(tuple(lem_lc[ps:pe]), "mwu")
            rec.add(is_cel, m, smask, kbit, sid, ex_ok)

    return {
        "singles": singles, "mwus": mwus, "uni_cel": uni_cel, "pair_cel": pair_cel, "n_cel": n_cel, "n_kon": n_kon,
        "subjects": subjects, "starts": starts, "ends": ends, "form": form, "mat_codes": mat_codes,
        "mat_subj_name": mat_subj_name, "cel": cel,
    }


def _candidate_table(ctx: Ctx, c: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    kc = ctx.cfg["kandydaci"]
    min_f, min_m = int(kc["min_frekw_cel"]), int(kc["min_materialow"])
    min_f1 = int(kc.get("min_frekw_jeden_material", 5))
    og_subj, og_mat, og_f = int(kc.get("ogolne_min_przedmiotow", 4)), int(kc.get("ogolne_min_materialow", 5)), \
        int(kc.get("ogolne_min_frekw", 10))
    max_propn = float(kc.get("max_udzial_nazw_wlasnych", 0.5))
    freq = pq.read_table(ctx.data / "frekwencje_lemat.parquet").to_pandas().set_index("lemma_lc")
    n_all = c["n_cel"] + c["n_kon"]

    rows, ctx_rows = [], []
    n_propn = 0
    for src in (c["singles"], c["mwus"]):
        for key, r in src.items():
            # termin skupiony w jednym materiale też jest kandydatem, jeśli jest w nim częsty
            subj = r.f_cel >= min_f and (r.m_cel >= min_m or r.f_cel >= min_f1)
            n_subj = bin(r.subj).count("1")
            gen_ = n_subj >= og_subj and r.m_kon >= og_mat and (r.f_cel + r.f_kon) >= og_f
            if not (subj or gen_):
                continue
            total = r.f_cel + r.f_kon
            share_propn = r.propn / total if total else 0.0
            if r.n == 1 and share_propn > max_propn:
                n_propn += 1
                continue
            fr = freq.loc[key] if (r.n == 1 and key in freq.index) else None
            rows.append({
                "forma_podstawowa": key,
                "lematy": " ".join(r.lem),
                "dlugosc": r.n,
                "cls": r.cls,
                "kand_przedmiotowy": subj,
                "kand_ogolny": gen_,
                "freq_cel": r.f_cel,
                "freq_kontrast": r.f_kon,
                "n_mat_cel": r.m_cel,
                "n_mat_kontrast": r.m_kon,
                "n_przedmiotow": n_subj,
                "n_klas_cel": bin(r.klasy).count("1"),
                "udzial_nazw_wlasnych": round(share_propn, 3),
                "freq_kwjp": float(fr["freq_kwjp"]) if fr is not None else float("nan"),
                "zipf_kwjp": float(fr["zipf_kwjp"]) if fr is not None else float("nan"),
                "zipf_wordfreq": float(fr["zipf_wordfreq"]) if fr is not None else float("nan"),
                "zipf_zpe": round(_zipf(total, n_all), 3),
            })
            for sid in r.ex_cel + r.ex_kon:
                s, e = int(c["starts"][sid]), int(c["ends"][sid])
                m = int(c["mat_codes"][s])
                ctx_rows.append({
                    "forma_podstawowa": key, "cel": bool(c["cel"][s]),
                    "przedmiot": c["mat_subj_name"][m], "tekst": _detok([str(x) for x in c["form"][s:e]]),
                })
    df = pd.DataFrame(rows)
    df.attrs["n_odrzuconych_nazw_wlasnych"] = n_propn
    return df, pd.DataFrame(ctx_rows)


def _score_methods(df: pd.DataFrame, c: dict[str, Any], kwjp_total: float, n_subj_total: int) -> pd.DataFrame:
    df = df.copy()
    N_cel, N_kon = float(c["n_cel"]), float(c["n_kon"])
    a, b = df["freq_cel"].to_numpy(float), df["freq_kontrast"].to_numpy(float)
    df["ll_vs_kontrast"] = [_signed_ll(x, y, N_cel, N_kon) for x, y in zip(a, b)]
    df["log_ratio_kontrast"] = [_log_ratio(x, y, N_cel, N_kon) for x, y in zip(a, b)]

    # względem KWJP100: mianownikiem jest suma frekwencji całej listy KWJP; tylko jednostki jednowyrazowe
    single = (df["dlugosc"] == 1).to_numpy()
    k = df["freq_kwjp"].fillna(0.0).to_numpy(float)
    nan = float("nan")
    df["ll_vs_kwjp"] = [_signed_ll(x, y, N_cel, kwjp_total) if s else nan for x, y, s in zip(a, k, single)]
    df["log_ratio_kwjp"] = [_log_ratio(x, y, N_cel, kwjp_total) if s else nan for x, y, s in zip(a, k, single)]
    df["simple_maths_kwjp"] = [_simple_maths(x, y, N_cel, kwjp_total) if s else nan for x, y, s in zip(a, k, single)]

    # TF-IDF po przedmiotach: tf w biologii * idf liczony na przedmiotach kontrastu
    df["tfidf_biol"] = (df["freq_cel"] / N_cel) * np.log((1 + n_subj_total) / (1 + df["n_przedmiotow"]))
    df["rozproszenie"] = df["n_przedmiotow"]

    # siła kolokacji fraz: PMI i logDice sąsiednich par lematów, dla frazy – najsłabsza para
    pairs, uni = c["pair_cel"], c["uni_cel"]
    pmis, dices = [], []
    for lem, L, f in zip(df["lematy"], df["dlugosc"], df["freq_cel"]):
        parts = lem.split()
        if L < 2 or len(parts) < 2 or f <= 0:
            pmis.append(nan)
            dices.append(nan)
            continue
        p, d = [], []
        for x, y in zip(parts, parts[1:]):
            xy = float(pairs.get((x, y), 0))
            p.append(_pmi(xy, float(uni.get(x, 0)), float(uni.get(y, 0)), N_cel))
            d.append(_logdice(xy, float(uni.get(x, 0)), float(uni.get(y, 0))))
        pmis.append(min(p) if all(v == v for v in p) else nan)
        dices.append(min(d) if all(v == v for v in d) else nan)
    df["pmi"] = pmis
    df["logdice"] = dices
    return df


def _add_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """Rangi metod liczone wśród kandydatów przedmiotowych (1 = najlepszy; brak wartości = brak rangi)."""
    df = df.copy()
    subj = df["kand_przedmiotowy"]
    cols = ["ll_vs_kontrast", "log_ratio_kontrast", "simple_maths_kwjp", "ll_vs_kwjp", "tfidf_biol", "pmi", "logdice", "cvalue"]
    for col in cols:
        df[f"rank_{col}"] = df.loc[subj & df[col].notna(), col].rank(ascending=False, method="min")
    # RRF: 1/(60+ranga) po metodach dostępnych dla danej jednostki, uśrednione
    use = ["ll_vs_kontrast", "tfidf_biol", "cvalue", "simple_maths_kwjp", "logdice"]
    rr = pd.DataFrame({u: 1.0 / (60.0 + df[f"rank_{u}"]) for u in use})
    df["rrf"] = rr.mean(axis=1, skipna=True).where(subj)
    df["rank_rrf"] = df.loc[subj, "rrf"].rank(ascending=False, method="min")
    return df


def _run_termopl(ctx: Ctx) -> pd.DataFrame | None:
    """Uruchom TermoPL na tekstach docelowych; zwróć DataFrame (lematy, forma, cvalue) albo None."""
    script = ROOT / "resources" / "tools" / "termopl" / "run_termopl.sh"
    if not script.exists():
        log("s04: brak run_termopl.sh – TermoPL pominięty")
        return None
    txt_dir = ctx.data / "termopl_txt"
    work = ctx.data / "termopl_work"
    out_tsv = ctx.data / "termopl_terms.tsv"
    txt_dir.mkdir(parents=True, exist_ok=True)
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
    if out_tsv.exists() and out_tsv.stat().st_mtime > (ctx.data / "korpus.jsonl").stat().st_mtime \
            and not ctx.cfg["kandydaci"].get("termopl_od_nowa", False):
        log("s04: TermoPL – używam zapisanego wyniku (nowszy niż korpus)")
    else:
        log(f"s04: TermoPL na {n} plikach…")
        try:
            subprocess.run(
                ["bash", str(script), str(txt_dir), str(work), str(out_tsv), str(max_len)],
                check=True, timeout=3 * 3600,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            log(f"s04: TermoPL nieudany: {exc}")
            return None
    if not out_tsv.exists():
        return None
    df = pd.read_csv(out_tsv, sep="\t")
    if not {"simplified_form", "base_form", "cvalue"} <= set(df.columns):
        return None
    out = pd.DataFrame({
        "lematy": df["simplified_form"].astype(str).str.lower().str.strip(),
        "forma": df["base_form"].astype(str).str.lower().str.strip(),
        "cvalue": df["cvalue"].astype(float),
    })
    return out


def _rule_label(row: pd.Series) -> str:
    """Podział regułowy – punkt odniesienia dla klasyfikacji LLM (nie trafia do promptu ani do pul)."""
    z = row["zipf_kwjp"] if row["zipf_kwjp"] == row["zipf_kwjp"] else 0.0
    if not row["kand_przedmiotowy"]:
        return "T1?" if z >= 4.5 else "T2?"
    if row["dlugosc"] >= 2 and row["log_ratio_kontrast"] >= 1.5 and row["n_przedmiotow"] <= 2:
        return "T3?"
    if row["dlugosc"] == 1 and row["log_ratio_kontrast"] >= 2.0 and z < 3.5 and row["n_przedmiotow"] <= 3:
        return "T3?"
    if row["n_przedmiotow"] >= 5 and z < 4.5:
        return "T2?"
    if row["dlugosc"] == 1 and z >= 4.5:
        return "T1?"
    return "nierozstrzygniete"


# --------------------------------------------------------------------------------------
# Srebrny standard
# --------------------------------------------------------------------------------------
def _lemma_options(token: str) -> set[str]:
    low = token.lower()
    opts = {low}
    for i in morf.analyse(low) + morf.analyse(token):
        if i.cls == "ign":
            continue
        opts.add(i.lemma.lower())
        opts.add(morf.nominal_lemma(i, low).lower())
    return opts


def term_lemma_keys(term: str, limit: int = 512) -> set[str]:
    """Możliwe ciągi lematów hasła (np. „bakterie” → „bakteria”; „tkanki roślinne” → „tkanka roślinny”)."""
    toks = WORD_RE.findall(term)
    if not toks or len(toks) > 6:
        return set()
    opts = [sorted(_lemma_options(t)) for t in toks]
    out = set()
    for combo in itertools.islice(itertools.product(*opts), limit):
        out.add(" ".join(combo))
    return out


def _split_terms(raw: str) -> list[str]:
    raw = re.sub(r"\([^)]*\)", " ", raw)
    return [t.strip().lower() for t in re.split(r"[,;/]", raw) if t.strip()]


def _silver_terms(ctx: Ctx) -> dict[str, set[str]]:
    """Hasła srebrnego standardu z materiałów DOCELOWYCH (słowniczki i formy podstawowe redakcji ZPE)."""
    gloss: set[str] = set()
    refs: set[str] = set()
    gpath = ctx.data / "srebrny_slowniczek.csv"
    if gpath.exists():
        with open(gpath, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("cel") == "1" and r.get("termin"):
                    gloss.update(_split_terms(r["termin"]))
    rpath = ctx.data / "srebrny_pojecie_ref.csv"
    if rpath.exists():
        with open(rpath, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("cel") == "1" and r.get("forma_podstawowa"):
                    refs.update(_split_terms(r["forma_podstawowa"]))
    return {"slowniczek": gloss, "pojecie_ref": refs}


def _match_silver(terms: set[str], by_lem: dict[str, str], by_form: set[str]) -> dict[str, str]:
    """hasło → forma_podstawowa kandydata (dopasowanie po formie albo po ciągu lematów)."""
    out = {}
    for t in terms:
        if t in by_form:
            out[t] = t
            continue
        for key in term_lemma_keys(t):
            if key in by_lem:
                out[t] = by_lem[key]
                break
    return out


def _precision_at(ranked: list[str], gold: set[str], ks: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_ranking": len(ranked), "n_srebrnych_w_rankingu": sum(1 for x in ranked if x in gold)}
    n_gold = out["n_srebrnych_w_rankingu"]
    for k in ks:
        top = ranked[:k]
        hit = sum(1 for x in top if x in gold)
        out[f"p@{k}"] = round(hit / len(top), 4) if top else None
        out[f"r@{k}"] = round(hit / n_gold, 4) if n_gold else None
    return out


# --------------------------------------------------------------------------------------
def run(ctx: Ctx) -> None:
    t = Timer()
    log("s04: zbieranie kandydatów (słowa, frazy, sąsiedztwa)…")
    c = _collect(ctx)
    df, konteksty = _candidate_table(ctx, c)
    n_propn = df.attrs.get("n_odrzuconych_nazw_wlasnych", 0)
    m43 = ctx.load_metrics("frekwencje_43", {}) or {}
    kwjp_total = float((m43.get("korpus") or {}).get("kwjp_suma_listy") or 0.0)
    if kwjp_total <= 0:
        raise RuntimeError("Brak sumy listy KWJP w metrykach kroku 3 – uruchom ponownie krok `frekwencje`.")
    df = _score_methods(df, c, kwjp_total, len(c["subjects"]))

    termopl = _run_termopl(ctx)
    n_termopl_join = 0
    if termopl is not None:
        cv_lem = termopl.groupby("lematy")["cvalue"].max()
        cv_form = termopl.groupby("forma")["cvalue"].max()
        a = df["lematy"].map(cv_lem)
        b = df["forma_podstawowa"].map(cv_form)
        df["cvalue"] = a.fillna(b).where(df["freq_cel"] > 0)
        n_termopl_join = int(df["cvalue"].notna().sum())
        df["termopl_ok"] = True
    else:
        df["cvalue"] = float("nan")
        df["termopl_ok"] = False
    df = _add_ranks(df)
    df["etykieta_regulowa"] = [_rule_label(r) for _, r in df.iterrows()]

    # --- srebrny standard: dopasowanie haseł po ciągu lematów
    silver = _silver_terms(ctx)
    subj = df[df["kand_przedmiotowy"]]
    by_lem_c = dict(zip(subj["lematy"], subj["forma_podstawowa"]))
    by_form_c = set(subj["forma_podstawowa"])
    # wszystkie jednostki wydobyte z korpusu docelowego (przed progami frekwencji)
    by_lem_all: dict[str, str] = {}
    for src in (c["singles"], c["mwus"]):
        for key, r in src.items():
            if r.f_cel > 0:
                by_lem_all[" ".join(r.lem)] = key
    by_form_all = set(by_lem_all.values())
    matched: dict[str, dict[str, str]] = {}
    coverage = {}
    for name, terms in silver.items():
        m_c = _match_silver(terms, by_lem_c, by_form_c)
        m_all = _match_silver(terms, by_lem_all, by_form_all)
        matched[name] = m_c
        multi = {x for x in terms if " " in x}
        coverage[name] = {
            "hasla": len(terms),
            "hasla_wielowyrazowe": len(multi),
            "wydobyte_z_korpusu_docelowego": len(m_all),
            "wsrod_kandydatow_po_progach": len(m_c),
            "wsrod_kandydatow_po_progach_wielowyrazowe": sum(1 for x in m_c if x in multi),
            "udzial_wsrod_kandydatow": round(len(m_c) / len(terms), 4) if terms else None,
        }
    gold_sets = {k: set(v.values()) for k, v in matched.items()}
    gold_sets["union"] = gold_sets["slowniczek"] | gold_sets["pojecie_ref"]
    df["srebrny_slowniczek"] = df["forma_podstawowa"].isin(gold_sets["slowniczek"]) & df["kand_przedmiotowy"]
    df["srebrny_pojecie_ref"] = df["forma_podstawowa"].isin(gold_sets["pojecie_ref"]) & df["kand_przedmiotowy"]

    methods = {
        "ll_kontrast": "ll_vs_kontrast", "log_ratio_kontrast": "log_ratio_kontrast", "tfidf_biol": "tfidf_biol",
        "simple_maths_kwjp": "simple_maths_kwjp", "ll_kwjp": "ll_vs_kwjp",
        "pmi_mwu": "pmi", "logdice_mwu": "logdice", "cvalue_termopl": "cvalue", "rrf": "rrf",
        "frekwencja_cel": "freq_cel",
    }
    universes = {"wszystkie": subj, "jednowyrazowe": subj[subj["dlugosc"] == 1], "wielowyrazowe": subj[subj["dlugosc"] > 1]}
    ks = [100, 300, 1000]
    prec: dict[str, Any] = {}
    for name, col in methods.items():
        if col == "cvalue" and termopl is None:
            prec[name] = {"status": "niedostepne"}
            continue
        prec[name] = {}
        for uname, u in universes.items():
            ranked = u[u[col].notna()].sort_values(col, ascending=False)["forma_podstawowa"].tolist()
            if len(ranked) < 50:
                continue
            prec[name][uname] = {f"vs_{g}": _precision_at(ranked, gs, ks) for g, gs in gold_sets.items()}
    # poziom odniesienia: udział jednostek srebrnych wśród kandydatów (precyzja losowego rankingu)
    base = {uname: {f"vs_{g}": round(float(u["forma_podstawowa"].isin(gs).mean()), 4) if len(u) else None
                    for g, gs in gold_sets.items()} for uname, u in universes.items()}

    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), ctx.data / "kandydaci_stat.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pandas(konteksty, preserve_index=False), ctx.data / "kandydaci_konteksty.parquet",
                   compression="zstd")
    (ctx.data / "kandydaci_stat.parquet.done").write_text("ok\n", encoding="utf-8")

    mw = subj[subj["dlugosc"] > 1]
    metrics: dict[str, Any] = {
        "n_kandydatow": int(len(subj)),
        "n_jednowyrazowych": int((subj["dlugosc"] == 1).sum()),
        "n_mwu": int(len(mw)),
        "n_kandydatow_ogolnych": int(df["kand_ogolny"].sum()),
        "n_kandydatow_ogolnych_tylko": int((df["kand_ogolny"] & ~df["kand_przedmiotowy"]).sum()),
        "n_wierszy": int(len(df)),
        "n_odrzuconych_nazw_wlasnych": int(n_propn),
        "n_kandydatow_z_jednego_materialu": int((subj["n_mat_cel"] == 1).sum()),
        "mianowniki": {"slowa_cel": int(c["n_cel"]), "slowa_kontrast": int(c["n_kon"]), "kwjp_suma_listy": kwjp_total,
                       "przedmioty_kontrastu": len(c["subjects"])},
        "kolokacje_mwu": {"z_pmi": int(mw["pmi"].notna().sum()), "bez_pmi": int(mw["pmi"].isna().sum())},
        "termopl": bool(termopl is not None),
        "termopl_terminow": int(len(termopl)) if termopl is not None else 0,
        "termopl_dopasowanych_kandydatow": n_termopl_join,
        "srebrny": {k: len(v) for k, v in silver.items()},
        "srebrny_pokrycie": coverage,
        "precyzja_poziom_odniesienia": base,
        "precyzja_wzgledem_srebrnego": prec,
        "etykiety_regulowe": subj["etykieta_regulowa"].value_counts().to_dict(),
        "progi": {k: ctx.cfg["kandydaci"].get(k) for k in
                  ["min_frekw_cel", "min_materialow", "min_frekw_jeden_material", "ogolne_min_przedmiotow",
                   "ogolne_min_materialow", "ogolne_min_frekw", "max_udzial_nazw_wlasnych", "max_dlugosc"]},
    }
    metrics["czas_s"] = round(t.s, 1)
    ctx.save_metrics("ekstrakcja_42", metrics)
    log(f"s04: {len(subj)} kandydatów przedmiotowych ({len(mw)} fraz), {int(df['kand_ogolny'].sum())} ogólnych "
        f"w {t.s:.1f}s; TermoPL={'tak' if termopl is not None else 'nie'}")
