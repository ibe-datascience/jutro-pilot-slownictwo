"""Krok 7. Generowanie i filtrowanie pseudosłów (zadanie B / sekcja 4.4 i 6)."""
from __future__ import annotations

import csv
import math
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from . import morf
from .common import Ctx, ROOT, Timer, log

# transliteracje uproszczone UA/RU → łacińskie (wskazówka, nie filtr)
CYR_MAP = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh",
    "з": "z", "и": "y", "і": "i", "ї": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu", "я": "ia", "ы": "y", "э": "e", "ё": "io",
})


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _phon_norm(s: str) -> str:
    s = s.lower().replace("ó", "u").replace("rz", "ż").replace("ch", "h")
    # ubezdźwięcznienie końcowe (przybliżenie)
    if s.endswith(("b", "d", "g", "w", "z", "ź", "ż")):
        s = s[:-1] + {"b": "p", "d": "t", "g": "k", "w": "f", "z": "s", "ź": "ś", "ż": "sz"}[s[-1]]
    return s


def _syllables(word: str) -> int:
    return max(1, len(re.findall(r"[aąeęioóuy]+", word.lower())))


def _cluster_complexity(word: str) -> int:
    return max((len(m.group(0)) for m in re.finditer(r"[bcćdfghjklłmnńprsśtwzźż]+", word.lower())), default=0)


def _old20(word: str, lexicon: list[str], sample: int = 2000) -> float:
    """Przybliżone OLD20 względem próbki leksykonu (Levenshtein)."""
    from rapidfuzz.distance import Levenshtein

    if not lexicon:
        return float("nan")
    rng = random.Random(hash(word) & 0xFFFFFFFF)
    pool = lexicon if len(lexicon) <= sample else rng.sample(lexicon, sample)
    dists = sorted(Levenshtein.distance(word, w) for w in pool)
    k = min(20, len(dists))
    return sum(dists[:k]) / k


def _templates(ctx: Ctx) -> pd.DataFrame:
    path = ctx.out / "pula_ogolna.csv"
    if not path.exists():
        raise FileNotFoundError("Brak pula_ogolna.csv – uruchom najpierw s06")
    df = pd.read_csv(path)
    # rzeczowniki i czasowniki; inne POS osobno
    main = df[df["cls"].isin(["subst", "ger", "inf", "fin", "praet"]) | (df["dlugosc"] == 1)].copy()
    main = main[main["dlugosc"] == 1]
    n = int(ctx.cfg["pseudoslowa"]["n_szablonow"])
    if ctx.probka:
        n = min(n, 80)
    # warstwowanie po długości i sylabach
    main["syl"] = main["forma_podstawowa"].map(_syllables)
    main["len"] = main["forma_podstawowa"].str.len()
    rng = ctx.rng("szablony")
    picked = []
    for (L, S), g in main.groupby(["len", "syl"]):
        if len(g) == 0:
            continue
        picked.append(g.sample(n=min(3, len(g)), random_state=rng.randint(0, 10**9)))
    out = pd.concat(picked).drop_duplicates("forma_podstawowa") if picked else main.head(0)
    if len(out) < n:
        extra = main[~main["forma_podstawowa"].isin(out["forma_podstawowa"])]
        out = pd.concat([out, extra.sample(n=min(n - len(out), len(extra)), random_state=ctx.seed)])
    return out.head(n).reset_index(drop=True)


_WUGGY = None


def _wuggy_gen():
    global _WUGGY
    if _WUGGY is not None:
        return _WUGGY
    import importlib.util
    import sys

    plug = ROOT / "resources" / "pseudo" / "wuggy_plugins"
    sys.path.insert(0, str(plug))
    spec = importlib.util.spec_from_file_location("load_local_plugin", plug / "load_local_plugin.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    _WUGGY = mod.load_generator("orthographic_polish")
    return _WUGGY


def _gen_wuggy(word: str, n: int, rng: random.Random) -> list[str]:
    try:
        gen = _wuggy_gen()
        if not gen.lookup_reference_segments(word):
            return []
        random.seed(rng.randint(0, 10**9))
        matches = gen.generate_classic([word], ncandidates_per_sequence=n, max_search_time_per_sequence=10)
        out = []
        for m in matches:
            cand = m.get("pseudoword") if isinstance(m, dict) else None
            if cand and cand.lower() != word.lower():
                out.append(cand.lower())
        return out[:n]
    except Exception as exc:
        log(f"  wuggy fail {word}: {exc}")
        return []


def _gen_unipseudo(word: str, n: int, rng: random.Random) -> list[str]:
    script = ROOT / "resources" / "pseudo" / "unipseudo" / "run_unipseudo_python_port.py"
    if not script.exists():
        return []
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.csv"
        try:
            subprocess.run(
                [str(ROOT / ".venv" / "bin" / "python"), str(script), str(n), str(len(word)), "1", "none"],
                cwd=str(script.parent), capture_output=True, timeout=60, check=False,
            )
            # script writes fixed name sometimes
            cands = []
            for p in script.parent.glob("*.csv"):
                try:
                    df = pd.read_csv(p)
                    col = df.columns[0]
                    cands = [str(x).lower() for x in df[col].head(n)]
                    break
                except Exception:
                    continue
            return [c for c in cands if c and c != word.lower()][:n]
        except Exception:
            return []


def _gen_imbir_sample(n: int, rng: random.Random) -> list[str]:
    path = ROOT / "resources" / "pseudo" / "imbir2015" / "polish_pseudowords.csv"
    if not path.exists():
        # find any csv
        cands = list((ROOT / "resources" / "pseudo" / "imbir2015").glob("*.csv"))
        path = cands[0] if cands else None
    if not path:
        return []
    df = pd.read_csv(path)
    col = next((c for c in df.columns if "pseudo" in c.lower() or "word" in c.lower() or "stimulus" in c.lower()), df.columns[0])
    words = [str(w).lower() for w in df[col].dropna()]
    return rng.sample(words, min(n, len(words)))


def _gen_llm(ctx: Ctx, templates: list[str], n_each: int) -> dict[str, list[str]]:
    from . import llm

    schema = {
        "type": "object",
        "properties": {
            "pseudoslowa": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["pseudoslowa"],
        "additionalProperties": False,
    }
    system = (
        "Generujesz polskie pseudosłowa (nieistniejące wyrazy) do testu LexTALE. "
        "Zachowaj końcówkę fleksyjną szablonu, zmień rdzeń. Bez istniejących słów polskich."
    )
    items = []
    for i, w in enumerate(templates):
        items.append((f"P{i:03d}", f"Szablon: {w}\nPodaj {n_each} pseudosłów podobnej długości."))
    model = ctx.cfg["llm"]["modele_porownywane"][0]
    if getattr(ctx, "bez_llm", False):
        return {}
    res = llm.run_requests(ctx, "pseudoslowa", model, system, items, schema, max_tokens=200, batch=True)
    out = {}
    for (cid, _), w in zip(items, templates):
        ps = res.get(cid, {}).get("pseudoslowa") or []
        out[w] = [str(x).lower() for x in ps][:n_each]
    return out


def _filter_reason(cand: str, template: str, freq_forms: dict[str, float], zipf_thr: float,
                   lexicon: set[str]) -> str | None:
    if not cand or not re.fullmatch(r"[a-ząćęłńóśźż\-]+", cand):
        return "niealfabetyczne"
    if morf.is_known(cand):
        return "znane_morfeusz"
    if cand in lexicon:
        return "w_leksykonie_korpusu"
    # literówka: odległość 1 od częstego słowa
    from rapidfuzz.distance import Levenshtein
    da = _deaccent(cand)
    for w, z in list(freq_forms.items())[:0]:  # placeholder
        pass
    # check against high-zipf via wordfreq neighbors is expensive; sample check
    import wordfreq
    if wordfreq.zipf_frequency(cand, "pl") >= zipf_thr:
        return "wordfreq_istnieje"
    # edit distance 1 to template's frequent lookalikes – check deaccented against wordfreq
    # homofony
    pn = _phon_norm(cand)
    if wordfreq.zipf_frequency(pn, "pl") >= zipf_thr:
        return "homofon_wordfreq"
    # produktywny afiks na istniejącym rdzeniu (heurystyka)
    for pref in ("nie", "anty", "pseudo", "nad", "pod", "prze", "wy", "za", "od", "do"):
        if cand.startswith(pref) and len(cand) > len(pref) + 3:
            stem = cand[len(pref):]
            if morf.is_known(stem) or wordfreq.zipf_frequency(stem, "pl") >= zipf_thr:
                return "prefiks_na_istniejacym"
    for suf in ("owy", "owa", "owe", "ność", "anie", "enie", "ować", "ić", "ać"):
        if cand.endswith(suf) and len(cand) > len(suf) + 3:
            stem = cand[: -len(suf)]
            if morf.is_known(stem) or wordfreq.zipf_frequency(stem, "pl") >= 4.0:
                return "sufiks_na_istniejacym"
    # literówka edit-1 względem szablonu po deaccent – jeśli cand jest 1 od prawdziwego częstego
    # (sprawdź kilka wariantów)
    for variant in {cand, da, cand.replace("u", "ó"), cand.replace("ż", "rz")}:
        if variant != cand and (morf.is_known(variant) or wordfreq.zipf_frequency(variant, "pl") >= zipf_thr):
            if Levenshtein.distance(cand, variant) <= 1:
                return "literowka_edit1"
    return None


def _ua_ru_flag(cand: str, wordlists: list[str]) -> bool:
    """Czy pseudosłowo jest podobne do słowa UA/RU po transliteracji (OLD≤2)."""
    from rapidfuzz.distance import Levenshtein
    for w in wordlists:
        if Levenshtein.distance(cand, w) <= 2:
            return True
    return False


def run(ctx: Ctx) -> None:
    t = Timer()
    templates = _templates(ctx)
    n_each = int(ctx.cfg["pseudoslowa"]["kandydatow_na_szablon"])
    if ctx.probka:
        n_each = min(n_each, 4)
    zipf_thr = float(ctx.cfg["pseudoslowa"]["czeste_slowo_zipf"])
    rng = ctx.rng("pseudo")

    # leksykon form z korpusu (do filtra)
    freq = pq_safe = None
    try:
        import pyarrow.parquet as pq
        forms = pq.read_table(ctx.data / "frekwencje_forma.parquet").to_pandas()
        lexicon = set(forms["form_lc"].astype(str))
        freq_map = dict(zip(forms["form_lc"], forms.get("freq_kwjp_orth", forms.get("freq_cel", 0))))
    except Exception:
        lexicon, freq_map = set(), {}

    # mała lista UA/RU transliterowanych (wbudowana próbka + opcjonalny plik)
    ua_ru = ["hata", "voda", "dytyna", "shkola", "kniga", "rabota", "zhizn", "chelovek", "gorod", "derevo"]
    extra = ROOT / "resources" / "pseudo" / "ua_ru_translit_sample.txt"
    if extra.exists():
        ua_ru += [ln.strip().lower() for ln in extra.read_text(encoding="utf-8").splitlines() if ln.strip()]

    accepted = []
    rejected = []
    methods_order = ["wuggy", "unipseudo", "imbir", "llm"]

    llm_map = {}
    try:
        llm_map = _gen_llm(ctx, templates["forma_podstawowa"].tolist(), n_each)
    except Exception as exc:
        log(f"s07: LLM pseudo pominięte: {exc}")

    imbir_pool = _gen_imbir_sample(max(50, len(templates) * n_each), rng)
    imbir_i = 0

    for _, row in templates.iterrows():
        tmpl = str(row["forma_podstawowa"]).lower()
        gens = {
            "wuggy": _gen_wuggy(tmpl, n_each, rng),
            "unipseudo": _gen_unipseudo(tmpl, n_each, rng),
            "imbir": [],
            "llm": llm_map.get(tmpl, []),
        }
        for _ in range(n_each):
            if imbir_i < len(imbir_pool):
                gens["imbir"].append(imbir_pool[imbir_i])
                imbir_i += 1
        for method, cands in gens.items():
            for cand in cands:
                reason = _filter_reason(cand, tmpl, freq_map, zipf_thr, lexicon)
                rec = {
                    "szablon": tmpl,
                    "pseudoslowo": cand,
                    "metoda": method,
                    "dlugosc_szablon": len(tmpl),
                    "dlugosc": len(cand),
                    "syl_szablon": _syllables(tmpl),
                    "syl": _syllables(cand),
                    "zbitka": _cluster_complexity(cand),
                    "diakryty": sum(1 for c in cand if c in "ąćęłńóśźż"),
                    "para_blokada": f"{tmpl}::{cand}",
                    "podobne_ua_ru": _ua_ru_flag(cand, ua_ru),
                }
                if reason:
                    rec["powod_odrzucenia"] = reason
                    rejected.append(rec)
                else:
                    accepted.append(rec)

    # OLD20 na akceptowanych (względem próbki form korpusu)
    lex_sample = list(lexicon)
    rng.shuffle(lex_sample)
    lex_sample = lex_sample[:3000]
    for rec in accepted:
        rec["old20"] = round(_old20(rec["pseudoslowo"], lex_sample), 3)

    acc = pd.DataFrame(accepted)
    rej = pd.DataFrame(rejected)
    if not acc.empty:
        acc.to_csv(ctx.out / "pseudoslowa.csv", index=False)
    else:
        pd.DataFrame(columns=["szablon", "pseudoslowo", "metoda"]).to_csv(ctx.out / "pseudoslowa.csv", index=False)
    if not rej.empty:
        rej.to_csv(ctx.out / "pseudoslowa_odrzucone.csv", index=False)
    else:
        pd.DataFrame(columns=["szablon", "pseudoslowo", "metoda", "powod_odrzucenia"]).to_csv(
            ctx.out / "pseudoslowa_odrzucone.csv", index=False
        )

    # rozkłady porównawcze
    real = templates.assign(
        pul="prawdziwe", dlugosc=templates["forma_podstawowa"].str.len(),
        syl=templates["forma_podstawowa"].map(_syllables),
        zbitka=templates["forma_podstawowa"].map(_cluster_complexity),
        diakryty=templates["forma_podstawowa"].map(lambda w: sum(1 for c in w if c in "ąćęłńóśźż")),
    )[["pul", "dlugosc", "syl", "zbitka", "diakryty"]]
    if not acc.empty:
        fake = acc.assign(pul="pseudoslowa")[["pul", "dlugosc", "syl", "zbitka", "diakryty"]]
        dist = pd.concat([real, fake])
    else:
        dist = real
    dist_summary = dist.groupby("pul")[["dlugosc", "syl", "zbitka", "diakryty"]].agg(["mean", "std"]).round(3)
    dist_summary.to_csv(ctx.out / "pseudoslowa_rozklady.csv")
    rozklady = {
        str(pul): {f"{col}_{stat}": float(dist_summary.loc[pul, (col, stat)])
                   for col in ["dlugosc", "syl", "zbitka", "diakryty"] for stat in ["mean", "std"]
                   if pul in dist_summary.index}
        for pul in dist_summary.index
    }

    (ctx.data / "pseudoslowa.done").write_text("ok\n", encoding="utf-8")
    ctx.save_metrics("pseudoslowa_7", {
        "n_szablonow": int(len(templates)),
        "n_zaakceptowanych": int(len(acc)),
        "n_odrzuconych": int(len(rej)),
        "odrzucenia_powody": {str(k): int(v) for k, v in (rej["powod_odrzucenia"].value_counts().items() if len(rej) else [])},
        "metody_akceptowane": {str(k): int(v) for k, v in (acc["metoda"].value_counts().items() if len(acc) else [])},
        "rozklady": rozklady,
        "czas_s": round(t.s, 1),
    })
    log(f"s07: OK={len(acc)} odrzucone={len(rej)} w {t.s:.1f}s")
