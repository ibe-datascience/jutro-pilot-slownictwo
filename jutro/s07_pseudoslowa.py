"""Krok 7. Generowanie, filtrowanie i ocena pseudosłów (zadanie B / sekcja 4.4 i 6).

1. Szablony: prawdziwe słowa w formie podstawowej – wyłącznie rzeczowniki i czasowniki – losowane z puli
   ogólnej i przedmiotowej, tak by pseudosłowa przypominały kształtem słowa prawdziwe z testu.
2. Generatory (porównywane, żaden nie zastępuje innego):
     wuggy           – Wuggy (orthographic_polish): te same długości segmentów podsylabowych, 2/3 segmentów
                       wspólnych ze wzorcem, podobne częstości przejść; zakończenie dowolne
     wuggy_koncowka  – jak wyżej, ale z zachowanym zakończeniem wzorca (podejście Dołżyckiej i in. 2022)
     unipseudo       – łańcuch trigramów/bigramów literowych UniPseudo na słowach WorldLex-Polish tej samej
                       długości i części mowy (pseudosłowo jest dopasowane do szablonu, nie z niego wyprowadzone)
     llm             – model językowy z opisem wymagań
     imbir           – gotowa lista Imbir i in. (2015), tylko pozycje zaakceptowane przez sędziów (dopasowane długością)
3. Filtry twarde (każde odrzucenie ma powód): istniejące słowo, kształt niezgodny ze wzorcem, ortotaktyka
   (trigramy, nagłos, wygłos, zbitki), literówka częstego słowa (odległość Damerau-Levenshteina 1), homofon,
   przejrzysta budowa słowotwórcza, skojarzenie wulgarne, słowo ukraińskie/rosyjskie w polskim zapisie.
4. Miary deterministyczne: OLD20 i liczba sąsiadów względem pełnego leksykonu lematów, średni log
   prawdopodobieństwa bigramów; te same miary dla szablonów.
5. Ocena modelem (zastępcza wobec sędziów-ludzi): wymawialność, najbliższe skojarzenie i jego siła,
   istnienie słowa, skojarzenia niestosowne. Na tej podstawie lista rekomendowana (`wybrane`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any

import numpy as np
import pandas as pd

from . import morf, pseudo
from .common import Ctx, ROOT, Timer, log, read_jsonl

METHODS = ["wuggy_koncowka", "wuggy", "unipseudo", "llm", "imbir"]
DERIVED = {"wuggy", "wuggy_koncowka", "llm"}


# --------------------------------------------------------------------------------------
# Szablony
# --------------------------------------------------------------------------------------
def lemma_pos(word: str) -> str | None:
    """„rzeczownik” / „czasownik”, jeśli słowo jest formą podstawową rzeczownika albo bezokolicznikiem."""
    ints = morf.analyse(word)
    if any(i.cls == "inf" for i in ints):
        return "czasownik"
    # bez odsłowników (pisanie) i bez przymiotników używanych rzeczownikowo (chory, kolorowy)
    if any(i.cls == "subst" and "nom" in i.case and "sg" in i.num and i.lemma.lower() == word for i in ints) \
            and not any(i.cls in ("ger", "adj", "ppas", "pact") for i in ints):
        return "rzeczownik"
    return None


VERB_RIMES = {"ać", "eć", "ić", "yć", "ąć", "uć"}


def verb_like(word: str) -> bool:
    """Zakończenie typowe dla bezokolicznika (-ać, -eć, -ić, -yć, -ąć, -uć); „-ość” czy „-iść” nim nie są."""
    return pseudo.final_rime(word) in VERB_RIMES


def _templates(ctx: Ctx, lex: pseudo.Lexicon) -> pd.DataFrame:
    cfg = ctx.cfg["pseudoslowa"]
    lo, hi = cfg.get("dlugosc_szablonu", [4, 12])
    n = int(cfg["n_szablonow"])
    share = float(cfg.get("udzial_przedmiotowych", 0.35))
    pools = cfg.get("szablony_z_pul", ["ogolna"])
    frames = []
    for name, fname in (("ogolna", "pula_ogolna.csv"), ("przedmiotowa", "pula_przedmiotowa.csv")):
        if name not in pools:
            continue
        path = ctx.out / fname
        if not path.exists():
            raise FileNotFoundError(f"Brak {fname} – uruchom najpierw krok `pule`")
        df = pd.read_csv(path)
        df = df[(df["dlugosc"] == 1) & df["forma_podstawowa"].str.fullmatch(r"[a-ząćęłńóśźż]+")].copy()
        df = df[df["forma_podstawowa"].str.len().between(lo, hi)]
        df["pos"] = df["forma_podstawowa"].map(lemma_pos)
        df = df[df["pos"].notna() & df["forma_podstawowa"].isin(lex.lemmas)]
        df["pula_szablonu"] = name
        frames.append(df[[c for c in ("forma_podstawowa", "pula_szablonu", "pos", "kategoria", "zipf_kwjp") if c in df]])
    by = {f["pula_szablonu"].iloc[0]: f for f in frames if len(f)}
    want = {"przedmiotowa": int(round(n * share)) if "ogolna" in by else n, "ogolna": n}
    picked = []
    left = n
    for name in ("przedmiotowa", "ogolna"):
        if name not in by:
            continue
        k = min(len(by[name]), want[name], left)
        # losowanie przez skrót (ziarno + słowo): drobna zmiana puli zmienia tylko pojedyncze szablony, nie całą próbę
        order = by[name]["forma_podstawowa"].map(lambda w: hashlib.sha256(f"{ctx.seed}:{w}".encode("utf-8")).hexdigest())
        picked.append(by[name].assign(_h=order).sort_values("_h").head(k).drop(columns="_h"))
        left -= k
    out = pd.concat(picked).drop_duplicates("forma_podstawowa").rename(columns={"forma_podstawowa": "szablon"})
    out["dlugosc"] = out["szablon"].str.len()
    out["syl"] = out["szablon"].map(pseudo.syllables)
    return out.sort_values(["dlugosc", "szablon"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Generatory
# --------------------------------------------------------------------------------------
_WUGGY = None


def _wuggy_gen():
    global _WUGGY
    if _WUGGY is None:
        plug = ROOT / "resources" / "pseudo" / "wuggy_plugins"
        sys.path.insert(0, str(plug))
        spec = importlib.util.spec_from_file_location("load_local_plugin", plug / "load_local_plugin.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        _WUGGY = mod.load_generator("orthographic_polish")
    return _WUGGY


def _wuggy_pool(args: tuple[str, int, float, int]) -> tuple[str, list[tuple[str, int]]]:
    """Kandydaci Wuggy dla jednego wzorca: (pseudosłowo, pasmo częstości przejść – im niższe, tym bliżej wzorca).

    Ustawienia jak w `generate_classic`: zgodne długości segmentów podsylabowych, 2/3 segmentów wspólnych,
    wyszukiwanie koncentryczne po odchyleniu częstości przejść (±2, ±4, …), tylko nie-słowa.
    """
    word, seed, max_time, cap = args
    g = _wuggy_gen()
    seg = g.lookup_reference_segments(word)
    if seg is None:
        return word, []
    random.seed(seed)  # Wuggy tasuje klucze startowe globalnym generatorem
    g.clear_attribute_filters()
    g.clear_frequency_filter()
    g.set_reference_sequence(seg)
    g.set_output_mode("plain")
    g.set_attribute_filter("segment_length")
    g.clear_statistics()
    g.set_statistics(["overlap_ratio", "lexicality"])
    out: list[tuple[str, int]] = []
    t0, first = time.time(), True
    try:
        for exponent in range(1, 14):
            g.set_frequency_filter(2 ** exponent, 2 ** exponent)
            for pw in g.generate_advanced(clear_cache=first):
                first = False
                if time.time() - t0 > max_time:
                    return word, out
                if g.statistics["lexicality"] == "W" or g.statistics["overlap_ratio"] != Fraction(2, 3):
                    continue
                out.append((pw.lower(), exponent))
                if len(out) >= cap:
                    return word, out
    except Exception as exc:  # noqa: BLE001
        log(f"  wuggy: {word}: {type(exc).__name__}: {exc}")
    return word, out


def _diverse(cands: list[tuple[str, int]], n: int, rng: random.Random) -> list[tuple[str, int]]:
    """Do n kandydatów różniących się między sobą co najmniej dwiema literami (Wuggy zwraca serie o 1 literę)."""
    from rapidfuzz.distance import Levenshtein

    pool = cands[:]
    rng.shuffle(pool)
    pool.sort(key=lambda x: x[1])  # najpierw pasma najbliższe wzorcowi; w paśmie kolejność losowa
    out: list[tuple[str, int]] = []
    for pw, band in pool:
        if all(Levenshtein.distance(pw, o) >= 2 for o, _ in out):
            out.append((pw, band))
            if len(out) >= n:
                break
    return out


def _gen_wuggy(ctx: Ctx, templates: pd.DataFrame, n_each: int) -> list[dict[str, Any]]:
    from concurrent.futures import ProcessPoolExecutor

    cfg = ctx.cfg["pseudoslowa"]
    max_time = float(cfg.get("wuggy_czas_s", 3.0))
    jobs = [(w, ctx.seed + i, max_time, 400) for i, w in enumerate(templates["szablon"])]
    workers = max(1, min(int(cfg.get("wuggy_procesy", 4)), len(jobs)))
    log(f"s07: Wuggy – {len(jobs)} wzorców, {workers} procesy, do {max_time:.0f} s na wzorzec…")
    if workers == 1:
        results = [_wuggy_pool(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_wuggy_pool, jobs, chunksize=4))
    rows = []
    rng = ctx.rng("wuggy")
    n_missing = 0
    for word, cands in results:
        if not cands:
            n_missing += 1
            continue
        rime = pseudo.final_rime(word)
        keep = [(p, b) for p, b in cands if p.endswith(rime) and p != word]
        free = [(p, b) for p, b in cands if not p.endswith(rime)]
        for method, pool in (("wuggy_koncowka", keep), ("wuggy", free)):
            for pw, band in _diverse(pool, n_each, rng):
                rows.append({"szablon": word, "pseudoslowo": pw, "metoda": method, "relacja": "pochodne",
                             "wuggy_pasmo": band})
    if n_missing:
        log(f"s07: Wuggy – {n_missing} wzorców bez kandydatów (spoza leksykonu Wuggy lub brak czasu)")
    return rows


def _load_unipseudo():
    port = ROOT / "resources" / "pseudo" / "unipseudo" / "openlexicon_django_dev_5d6f5188" / "unipseudo"
    mods = {}
    for name in ("generator", "filters"):
        spec = importlib.util.spec_from_file_location(f"unipseudo_port_{name}", port / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["generator"], mods["filters"]


def _gen_unipseudo(ctx: Ctx, templates: pd.DataFrame, n_each: int) -> list[dict[str, Any]]:
    """UniPseudo: modele = słowa WorldLex-Polish (BlogFreqPm > 0,5) tej samej długości i części mowy co szablony."""
    wl = pseudo.PSEUDO_DIR / "unipseudo" / "data" / "worldlex_polish_words.tsv"
    if not wl.exists():
        log("s07: brak worldlex_polish_words.tsv (uruchom resources/pseudo/unipseudo/export_worldlex.R) – UniPseudo pominięty")
        return []
    generator, filters = _load_unipseudo()
    lengths = set(templates["dlugosc"])
    words = pd.read_csv(wl, sep="\t", dtype={"word": str}, keep_default_na=False)
    words = words[words["nbcar"].isin(lengths)]
    words["word"] = words["word"].str.lower()
    words = words[words["word"].str.fullmatch(r"[a-ząćęłńóśźż]+")]
    exclude_by_len = {L: sorted(set(g["word"])) for L, g in words.groupby(words["word"].str.len())}
    models = words[words["BlogFreqPm"].astype(float) > 0.5].drop_duplicates("word").copy()
    models["pos"] = models["word"].map(lemma_pos)
    models = models[models["pos"].notna()]
    checks = filters.build_checks({"filterConsonants": 3, "filterSameLetter": 2})  # ustawienia aplikacji R dla języków łacińskich
    rows = []
    rng = ctx.rng("unipseudo")
    for (L, pos), tg in templates.groupby(["dlugosc", "pos"]):
        m = sorted(models.loc[(models["word"].str.len() == L) & (models["pos"] == pos), "word"])
        if len(m) < 50:
            continue
        algo = generator.default_algorithm(int(L))
        try:
            res = generator.generate_pseudowords(len(tg) * n_each, int(L), m, algo, exclude=exclude_by_len.get(L, []),
                                                 checks=checks, time_out=2.0, rng=random.Random(rng.randint(0, 10 ** 9)))
        except Exception as exc:  # noqa: BLE001
            log(f"  unipseudo: długość {L}, {pos}: {type(exc).__name__}: {exc}")
            continue
        tmpl = list(tg["szablon"])
        for i, p in enumerate(res.pseudowords):
            rows.append({"szablon": tmpl[i % len(tmpl)], "pseudoslowo": p.pseudoword.lower(), "metoda": "unipseudo",
                         "relacja": "dopasowane", "unipseudo_algorytm": algo, "unipseudo_modeli": len(m)})
    return rows


def _gen_imbir(ctx: Ctx, templates: pd.DataFrame, n_each: int) -> list[dict[str, Any]]:
    path = pseudo.PSEUDO_DIR / "imbir2015" / "Polish_pseudo-words_List_dataset.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    df.columns = ["pseudoslowo", "indeks_zgodnosci", "n_sedziow", "dlugosc"][:len(df.columns)]
    min_j = int(ctx.cfg["pseudoslowa"].get("imbir_min_sedziow", 4))
    df = df[df["n_sedziow"] >= min_j].copy()
    df["pseudoslowo"] = df["pseudoslowo"].astype(str).str.lower().str.strip()
    df["verbish"] = df["pseudoslowo"].map(verb_like)
    rng = ctx.rng("imbir")
    rows = []
    for (L, pos), tg in templates.groupby(["dlugosc", "pos"]):
        pool = df[(df["pseudoslowo"].str.len() == L) & (df["verbish"] == (pos == "czasownik"))]
        words = sorted(pool["pseudoslowo"])
        rng.shuffle(words)
        tmpl = list(tg["szablon"])
        for i, w in enumerate(words[:len(tmpl) * n_each]):
            rows.append({"szablon": tmpl[i % len(tmpl)], "pseudoslowo": w, "metoda": "imbir", "relacja": "dopasowane",
                         "imbir_n_sedziow": int(pool.loc[pool["pseudoslowo"] == w, "n_sedziow"].iloc[0])})
    return rows


GEN_SYSTEM = """Tworzysz pseudosłowa do testu decyzji leksykalnej (typu LexTALE) dla uczniów klas 5–8: ciągi liter, które wyglądają i brzmią jak polskie słowa, ale w polszczyźnie nie istnieją. Dla podanego słowa-wzorca podaj żądaną liczbę pseudosłów.

Wymagania:
1. Ten sam „wygląd” części mowy i ta sama forma: zachowaj zakończenie wzorca (ostatnią sylabę albo co najmniej końcówkę: czasownik kończy się tak jak wzorzec na -ać, -ić, -yć, -ować, -nąć; rzeczownik na tę samą samogłoskę albo na spółgłoskę).
2. Ta sama liczba sylab; długość różni się od wzorca najwyżej o jedną literę.
3. Zmień rdzeń tak, żeby pseudosłowo różniło się od wzorca i od KAŻDEGO istniejącego słowa co najmniej dwiema literami. Nie może być błędną pisownią ani homofonem prawdziwego słowa (ó/u, rz/ż, ch/h, ą/om, ę/en).
4. Tylko sylaby i zbitki liter typowe dla polszczyzny, łatwe do wymówienia; polskie znaki są dozwolone tam, gdzie są naturalne.
5. Bez przejrzystej budowy: żadnych istniejących rdzeni z produktywnym przedrostkiem lub przyrostkiem (nie: „przedkotować”, „domownia”), żadnych zrostów dwóch słów.
6. Bez słów istniejących w ukraińskim, rosyjskim lub angielskim (także w polskim zapisie), bez skojarzeń wulgarnych i śmiesznych.
7. Pseudosłowa mają się różnić między sobą: nie podawaj serii różniących się jedną literą.

Przykłady dobrych pseudosłów: komora → talora, bemira; wynik → dorak, pulit; kiełkować → miałpować, trzylkować; zjawisko → brzanisko, plutysko.
Zwróć same pseudosłowa, małymi literami."""
GEN_SCHEMA = {
    "type": "object",
    "properties": {"pseudoslowa": {"type": "array", "items": {"type": "string"}}},
    "required": ["pseudoslowa"],
    "additionalProperties": False,
}


def _gen_llm(ctx: Ctx, templates: pd.DataFrame, n_each: int) -> list[dict[str, Any]]:
    from . import llm

    if getattr(ctx, "bez_llm", False) and not (llm.llm_dir(ctx) / "koszty.jsonl").exists():
        return []
    model = ctx.cfg["llm"].get("model_pseudoslow") or ctx.cfg["llm"]["modele_porownywane"][-1]
    items = [(f"P{i:04d}", f"Wzorzec: {r.szablon} ({r.pos}, liczba sylab: {r.syl}). Liczba pseudosłów: {n_each}.")
             for i, r in enumerate(templates.itertuples())]
    # limit obejmuje tokeny myślenia modelu: przy 600 część odpowiedzi kończyła się przed wypisaniem listy
    res = llm.run_requests(ctx, "pseudoslowa_v2", model, GEN_SYSTEM, items, GEN_SCHEMA, max_tokens=4000,
                           batch=bool(ctx.cfg["llm"].get("batch", True)), est_out_tokens=600)
    missing = [w for (cid, _), w in zip(items, templates["szablon"]) if not (res.get(cid) or {}).get("pseudoslowa")]
    if missing:
        log(f"s07: llm – brak odpowiedzi dla {len(missing)} szablonów")
    rows = []
    for (cid, _), w in zip(items, templates["szablon"]):
        for p in (res.get(cid) or {}).get("pseudoslowa", [])[:n_each]:
            rows.append({"szablon": w, "pseudoslowo": str(p).strip().lower(), "metoda": "llm", "relacja": "pochodne"})
    return rows


# --------------------------------------------------------------------------------------
# Filtry
# --------------------------------------------------------------------------------------
def _shape_problem(cand: str, tmpl: str, pos: str, derived: bool) -> str | None:
    if abs(len(cand) - len(tmpl)) > 1:
        return f"długość {len(cand)} vs {len(tmpl)}"
    if pseudo.syllables(cand) != pseudo.syllables(tmpl):
        return f"sylaby {pseudo.syllables(cand)} vs {pseudo.syllables(tmpl)}"
    ec, et = pseudo.ending_class(cand), pseudo.ending_class(tmpl)
    if pos == "czasownik":
        rc, rt = pseudo.final_rime(cand), pseudo.final_rime(tmpl)
        if rt in VERB_RIMES and rc not in VERB_RIMES:
            return f"zakończenie „-{rc}” nie jest zakończeniem bezokolicznika"
        if rt not in VERB_RIMES and rc != rt:
            return f"zakończenie „-{rc}” vs „-{rt}”"
    if pos == "rzeczownik" and (ec != et or verb_like(cand) != verb_like(tmpl)):
        return f"zakończenie „{cand[-1]}” vs „{tmpl[-1]}”"
    return None


def _filter(cand: str, tmpl: str, pos: str, derived: bool, lex: pseudo.Lexicon, ua_ru: dict[str, str],
            min_types: int) -> tuple[str, str] | None:
    """(powód, szczegół) pierwszego niespełnionego warunku albo None."""
    from rapidfuzz.distance import Levenshtein

    if not cand or not pseudo.ALPHA_RE.match(cand):
        return "znaki_spoza_alfabetu", ""
    real = lex.is_real(cand)
    if real:
        return "istniejace_slowo", real
    shape = _shape_problem(cand, tmpl, pos, derived)
    if shape:
        return "ksztalt_niezgodny_ze_wzorcem", shape
    if Levenshtein.distance(cand, tmpl) < 2:
        return "za_blisko_wzorca", tmpl
    orth = lex.orthotactic_problem(cand, min_types)
    if orth:
        return "ortotaktyka", orth
    near = lex.nearest_frequent(cand, 1)
    if near:
        return "literowka_czestego_slowa", near[0]
    ph = pseudo.phon(cand)
    if ph in lex.phon_index:
        return "homofon", lex.phon_index[ph]
    tr = pseudo.transparent_structure(cand, lex)
    if tr:
        return "przejrzysta_budowa", tr
    vg = pseudo.vulgar(cand)
    if vg:
        return "skojarzenie_wulgarne", vg
    if ph in ua_ru:
        return "slowo_ukrainskie_lub_rosyjskie", ua_ru[ph]
    return None


# --------------------------------------------------------------------------------------
# Ocena modelem
# --------------------------------------------------------------------------------------
RATE_SYSTEM = """Oceniasz kandydatów na pseudosłowa do testu decyzji leksykalnej dla uczniów klas 5–8 polskiej szkoły podstawowej; część uczniów zna ukraiński lub rosyjski. Dobre pseudosłowo wygląda i brzmi jak możliwe polskie słowo, ale nie istnieje i nie przypomina wyraźnie żadnego konkretnego słowa.

Dla KAŻDEGO ciągu z listy podaj:
- wymawialnosc: 1–5. 5 = brzmi jak naturalne polskie słowo; 4 = poprawne, lekko nietypowe; 3 = wymawialne, ale wyraźnie sztuczne lub obco brzmiące; 2 = trudne do wymówienia; 1 = niepolski układ liter.
- skojarzenie: jedno prawdziwe polskie słowo, które najsilniej przychodzi na myśl (forma podstawowa), albo pusty napis.
- podobienstwo: 0–3. 0 = brak wyraźnego skojarzenia; 1 = luźne podobieństwo do jakiegoś słowa; 2 = wyraźnie przypomina konkretne słowo (uczeń może uznać to za jego odmianę, zdrobnienie lub błąd w pisowni); 3 = to w praktyce istniejące słowo: forma fleksyjna, wariant, literówka lub zapis fonetyczny.
- istniejace: true, jeśli ciąg jest istniejącym słowem polskim (także rzadkim, potocznym, gwarowym, specjalistycznym, formą odmiany, nazwą własną lub marką).
- slowo_obce: jeśli ciąg jest lub brzmi jak istniejące słowo ukraińskie, rosyjskie, angielskie albo niemieckie – podaj to słowo i język (np. „робота, ukraiński”); w przeciwnym razie pusty napis.
- niestosowne: true, jeśli ciąg budzi skojarzenia wulgarne, obraźliwe lub ośmieszające.

Oceń wszystkie pozycje, w kolejności z listy, przepisując ciąg dokładnie."""
RATE_SCHEMA = {
    "type": "object",
    "properties": {"oceny": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "pseudoslowo": {"type": "string"},
            "wymawialnosc": {"type": "integer"},
            "skojarzenie": {"type": "string"},
            "podobienstwo": {"type": "integer"},
            "istniejace": {"type": "boolean"},
            "slowo_obce": {"type": "string"},
            "niestosowne": {"type": "boolean"},
        },
        "required": ["pseudoslowo", "wymawialnosc", "skojarzenie", "podobienstwo", "istniejace", "slowo_obce", "niestosowne"],
        "additionalProperties": False,
    }}},
    "required": ["oceny"],
    "additionalProperties": False,
}


def _rate(ctx: Ctx, words: list[str]) -> dict[str, dict[str, Any]]:
    from . import llm

    if not words or (getattr(ctx, "bez_llm", False) and not (llm.llm_dir(ctx) / "koszty.jsonl").exists()):
        return {}
    model = ctx.cfg["llm"].get("model_oceny_pseudoslow") or ctx.cfg["llm"]["model_rozstrzygajacy"]
    words = sorted(set(words))
    # Oceny są pamiętane dla pojedynczych pseudosłów (klucz: model + prompt), bo żądania grupują po 30 ciągów:
    # bez tego każda zmiana listy kandydatów zmieniałaby skład wszystkich żądań i wymagała ponownej oceny całości.
    key = llm._hash(model, RATE_SYSTEM, json.dumps(RATE_SCHEMA, sort_keys=True))
    cache_path = llm.llm_dir(ctx) / "pseudoslowa_oceny_slowa.json"
    store = llm.llm_dir(ctx) / f"pseudoslowa_ocena_v2__{model}.jsonl"
    if cache_path.exists():
        cache_all = json.loads(cache_path.read_text(encoding="utf-8"))
    else:  # pierwsze uruchomienie po wprowadzeniu pamięci ocen: odpowiedzi już zapisane dla tego promptu
        cache_all = {key: {}}
        if store.exists():
            for rec in read_jsonl(store):
                for r in (rec.get("output") or {}).get("oceny", []):
                    cache_all[key][str(r.get("pseudoslowo", "")).strip().lower()] = r
    cache: dict[str, dict[str, Any]] = cache_all.setdefault(key, {})
    todo = [w for w in words if w not in cache]
    if todo:
        rng = ctx.rng("ocena_pseudoslow")
        rng.shuffle(todo)
        size = 30
        items = [(f"R{i:04d}", "Ciągi do oceny:\n" + "\n".join(todo[s:s + size])) for i, s in enumerate(range(0, len(todo), size))]
        log(f"s07: ocena {len(todo)} pseudosłów modelem {model} ({len(items)} żądań; {len(words) - len(todo)} ocen już zapisanych)…")
        res = llm.run_requests(ctx, "pseudoslowa_ocena_v2", model, RATE_SYSTEM, items, RATE_SCHEMA, max_tokens=8000,
                               batch=bool(ctx.cfg["llm"].get("batch", True)), est_out_tokens=1500)
        wanted = set(todo)
        for payload in res.values():
            for r in (payload or {}).get("oceny", []):
                w = str(r.get("pseudoslowo", "")).strip().lower()
                if w in wanted:
                    cache[w] = r
        cache_path.write_text(json.dumps(cache_all, ensure_ascii=False), encoding="utf-8")
    else:
        log(f"s07: wszystkie {len(words)} oceny pseudosłów są już zapisane")
    return {w: cache[w] for w in words if w in cache}


# --------------------------------------------------------------------------------------
def _smd(a: pd.Series, b: pd.Series) -> float | None:
    s = float(np.sqrt((a.var() + b.var()) / 2)) if len(a) > 1 and len(b) > 1 else 0.0
    return round(float((b.mean() - a.mean()) / s), 3) if s > 0 else None


def run(ctx: Ctx) -> None:
    from rapidfuzz import process
    from rapidfuzz.distance import Levenshtein

    t = Timer()
    cfg = ctx.cfg["pseudoslowa"]
    n_each = int(cfg["kandydatow_na_szablon"])
    min_types = int(cfg.get("min_typow_ngramu", 5))
    try:
        import pyarrow.parquet as pq

        corpus_forms = set(pq.read_table(ctx.data / "frekwencje_forma.parquet", columns=["form_lc"]).to_pandas()["form_lc"])
    except Exception:  # noqa: BLE001
        corpus_forms = set()
    log("s07: leksykon odniesienia (KWJP100, WorldLex, statystyki ortotaktyczne)…")
    lex = pseudo.Lexicon(float(cfg["czeste_slowo_zipf"]), corpus_forms)
    ua_ru = pseudo.ua_ru_index()
    ua_ru_by_len: dict[int, list[str]] = defaultdict(list)
    for k in ua_ru:
        ua_ru_by_len[len(k)].append(k)

    templates = _templates(ctx, lex)
    templates["old20"] = lex.old20(list(templates["szablon"]), exclude_self=True)
    templates["bigram_lp"] = [lex.bigram_logprob(w) for w in templates["szablon"]]
    tinfo = templates.set_index("szablon")
    log(f"s07: {len(templates)} szablonów ({templates['pula_szablonu'].value_counts().to_dict()}, "
        f"{templates['pos'].value_counts().to_dict()})")

    rows: list[dict[str, Any]] = []
    for name, fn in (("wuggy", _gen_wuggy), ("unipseudo", _gen_unipseudo), ("llm", _gen_llm), ("imbir", _gen_imbir)):
        try:
            got = fn(ctx, templates, n_each)
        except Exception as exc:  # noqa: BLE001
            log(f"s07: generator {name} nieudany: {type(exc).__name__}: {exc}")
            got = []
        log(f"s07: {name}: {len(got)} kandydatów")
        rows += got
    cand = pd.DataFrame(rows)
    if cand.empty:
        raise RuntimeError("Żaden generator nie zwrócił kandydatów")
    cand = cand.drop_duplicates(["szablon", "pseudoslowo", "metoda"]).reset_index(drop=True)
    generated = cand["metoda"].value_counts().to_dict()

    # --- filtry twarde
    reasons, details = [], []
    for r in cand.itertuples():
        ti = tinfo.loc[r.szablon]
        res = _filter(r.pseudoslowo, r.szablon, ti["pos"], r.metoda in DERIVED, lex, ua_ru, min_types)
        reasons.append(res[0] if res else None)
        details.append(res[1] if res else "")
    cand["powod_odrzucenia"], cand["szczegol"] = reasons, details
    for col in ("pula_szablonu", "pos"):
        cand[col] = cand["szablon"].map(tinfo[col])
    cand["dlugosc_szablon"] = cand["szablon"].str.len()
    cand["dlugosc"] = cand["pseudoslowo"].str.len()
    rej = cand[cand["powod_odrzucenia"].notna()].copy()
    acc = cand[cand["powod_odrzucenia"].isna()].drop(columns=["powod_odrzucenia", "szczegol"]).copy()

    # to samo pseudosłowo z kilku metod lub szablonów: jeden wiersz, lista metod
    acc["_m"] = acc["metoda"].map({m: i for i, m in enumerate(METHODS)})
    allm = acc.groupby("pseudoslowo")["metoda"].agg(lambda s: "; ".join(sorted(set(s))))
    acc = acc.sort_values(["_m", "szablon"]).drop_duplicates("pseudoslowo", keep="first").drop(columns="_m")
    acc["metody_wszystkie"] = acc["pseudoslowo"].map(allm)

    # --- miary deterministyczne
    acc["syl_szablon"] = acc["szablon"].map(tinfo["syl"])
    acc["syl"] = acc["pseudoslowo"].map(pseudo.syllables)
    acc["odleglosc_od_szablonu"] = [Levenshtein.distance(a, b) for a, b in zip(acc["pseudoslowo"], acc["szablon"])]
    acc["koncowka_zachowana"] = [p.endswith(pseudo.final_rime(s)) for p, s in zip(acc["pseudoslowo"], acc["szablon"])]
    acc["zbitka"] = acc["pseudoslowo"].map(pseudo.max_cluster)
    acc["diakryty"] = acc["pseudoslowo"].map(pseudo.n_diacritics)
    acc["old20"] = np.round(lex.old20(list(acc["pseudoslowo"])), 3)
    acc["old20_szablon"] = acc["szablon"].map(tinfo["old20"]).round(3)
    acc["bigram_lp"] = [round(lex.bigram_logprob(w), 3) for w in acc["pseudoslowo"]]
    acc["bigram_lp_szablon"] = acc["szablon"].map(tinfo["bigram_lp"]).round(3)
    acc["min_trigram_typow"] = acc["pseudoslowo"].map(lex.min_trigram)
    neigh = [lex.neighbours(w) for w in acc["pseudoslowo"]]
    acc["n_sasiadow_1"] = [len(x) for x in neigh]
    acc["sasiedzi_1"] = ["; ".join(x[:5]) for x in neigh]
    near2 = [lex.nearest_frequent(w, 2) for w in acc["pseudoslowo"]]
    acc["najblizsze_czeste_slowo"] = [x[0] if x else "" for x in near2]
    flags = []
    for w in acc["pseudoslowo"]:
        ph, hit = pseudo.phon(w), None
        if len(ph) >= 5:
            for L in (len(ph) - 1, len(ph), len(ph) + 1):
                if ua_ru_by_len.get(L):
                    h = process.extractOne(ph, ua_ru_by_len[L], scorer=Levenshtein.distance, score_cutoff=1)
                    if h:
                        hit = ua_ru[h[0]]
                        break
        flags.append(hit or "")
    acc["podobne_ua_ru"] = flags
    acc["para_blokada"] = acc["szablon"] + "::" + acc["pseudoslowo"]

    # --- ranking w szablonie: bliskość OLD20 i prawdopodobieństwa bigramów do wzorca, kara za sąsiadów i UA/RU
    sd_o = float(acc["old20"].std()) or 1.0
    sd_b = float(acc["bigram_lp"].std()) or 1.0
    acc["odstep_od_szablonu"] = ((acc["old20"] - acc["old20_szablon"]).abs() / sd_o
                                 + (acc["bigram_lp"] - acc["bigram_lp_szablon"]).abs() / sd_b
                                 + 0.5 * (acc["n_sasiadow_1"] > 0) + 0.5 * (acc["podobne_ua_ru"] != "")).round(3)
    acc = acc.sort_values(["szablon", "odstep_od_szablonu", "pseudoslowo"]).reset_index(drop=True)
    acc["ranga_w_szablonie"] = acc.groupby("szablon").cumcount() + 1

    # --- kandydaci do oceny modelem: do N na szablon, różni między sobą, najwyżej połowa z jednej metody
    n_rate = int(cfg.get("ocenianych_na_szablon", 6))
    to_rate = []
    for _tmpl, g in acc.groupby("szablon", sort=False):
        chosen: list[int] = []
        per_method: Counter = Counter()
        for idx, r in g.iterrows():
            if per_method[r["metoda"]] >= max(1, n_rate // 2):
                continue
            if any(Levenshtein.distance(r["pseudoslowo"], acc.at[c, "pseudoslowo"]) < 2 for c in chosen):
                continue
            chosen.append(idx)
            per_method[r["metoda"]] += 1
            if len(chosen) >= n_rate:
                break
        to_rate += chosen
    acc["oceniane"] = acc.index.isin(to_rate)
    try:
        ratings = _rate(ctx, list(acc.loc[acc["oceniane"], "pseudoslowo"]))
    except Exception as exc:  # noqa: BLE001
        log(f"s07: ocena modelem nieudana: {type(exc).__name__}: {exc}")
        ratings = {}
    for col, key in (("ocena_wymawialnosc", "wymawialnosc"), ("ocena_skojarzenie", "skojarzenie"),
                     ("ocena_podobienstwo", "podobienstwo"), ("ocena_istniejace", "istniejace"),
                     ("ocena_slowo_obce", "slowo_obce"), ("ocena_niestosowne", "niestosowne")):
        acc[col] = [ratings.get(w, {}).get(key) if o else None for w, o in zip(acc["pseudoslowo"], acc["oceniane"])]
    min_pron = int(cfg.get("min_wymawialnosc", 4))
    max_sim = int(cfg.get("max_podobienstwo", 1))
    rated = acc["ocena_wymawialnosc"].notna()
    acc["ocena_pozytywna"] = (rated & (acc["ocena_wymawialnosc"].fillna(0) >= min_pron)
                              & (acc["ocena_podobienstwo"].fillna(9) <= max_sim)
                              & (acc["ocena_istniejace"] != True) & (acc["ocena_niestosowne"] != True)  # noqa: E712
                              & (acc["ocena_slowo_obce"].fillna("") == ""))
    # lista rekomendowana: najlepsze pozytywnie ocenione; bez oceny modelu – najlepsze wg rangi
    n_sel = int(cfg.get("wybrane_na_szablon", 2))
    base = acc[acc["ocena_pozytywna"]] if ratings else acc[acc["oceniane"]]
    acc["wybrane"] = acc.index.isin(base.groupby("szablon").head(n_sel).index)

    front = ["szablon", "pseudoslowo", "metoda", "wybrane", "pula_szablonu", "pos", "relacja", "ranga_w_szablonie",
             "odstep_od_szablonu", "oceniane", "ocena_pozytywna", "ocena_wymawialnosc", "ocena_skojarzenie",
             "ocena_podobienstwo", "ocena_istniejace", "ocena_slowo_obce", "ocena_niestosowne"]
    acc = acc[front + [c for c in acc.columns if c not in front]]
    acc.to_csv(ctx.out / "pseudoslowa.csv", index=False)
    rfront = ["szablon", "pseudoslowo", "metoda", "powod_odrzucenia", "szczegol"]
    rej[rfront + [c for c in rej.columns if c not in rfront]].to_csv(ctx.out / "pseudoslowa_odrzucone.csv", index=False)

    # --- porównanie rozkładów: szablony vs pseudosłowa (wszystkie przyjęte i rekomendowane)
    real = pd.DataFrame({
        "dlugosc": templates["dlugosc"], "syl": templates["syl"], "zbitka": templates["szablon"].map(pseudo.max_cluster),
        "diakryty": templates["szablon"].map(pseudo.n_diacritics), "old20": templates["old20"], "bigram_lp": templates["bigram_lp"],
    })
    feats = ["dlugosc", "syl", "zbitka", "diakryty", "old20", "bigram_lp"]
    groups = {"szablony": real, "pseudoslowa_przyjete": acc[feats], "pseudoslowa_wybrane": acc.loc[acc["wybrane"], feats]}
    dist_rows = []
    for gname, g in groups.items():
        for f in feats:
            dist_rows.append({"grupa": gname, "cecha": f, "n": int(len(g)), "srednia": round(float(g[f].mean()), 3) if len(g) else None,
                              "odch_std": round(float(g[f].std()), 3) if len(g) > 1 else None,
                              "smd_wzgledem_szablonow": None if gname == "szablony" else _smd(real[f], g[f])})
    dist = pd.DataFrame(dist_rows)
    dist.to_csv(ctx.out / "pseudoslowa_rozklady.csv", index=False)
    templates.to_csv(ctx.out / "pseudoslowa_szablony.csv", index=False)

    by_method = {}
    for m in METHODS:
        a, r = acc[acc["metoda"] == m], rej[rej["metoda"] == m]
        n_gen = int(generated.get(m, 0))
        if not n_gen:
            continue
        ra = a[a["ocena_wymawialnosc"].notna()]
        by_method[m] = {
            "wygenerowane": n_gen, "odrzucone": int(len(r)), "przyjete": int(len(a)),
            "udzial_przyjetych": round((n_gen - len(r)) / n_gen, 4),
            "oceniane": int(len(ra)), "ocena_pozytywna": int(ra["ocena_pozytywna"].sum()),
            "udzial_pozytywnych": round(float(ra["ocena_pozytywna"].mean()), 4) if len(ra) else None,
            "srednia_wymawialnosc": round(float(ra["ocena_wymawialnosc"].mean()), 3) if len(ra) else None,
            "srednie_podobienstwo": round(float(ra["ocena_podobienstwo"].mean()), 3) if len(ra) else None,
            "wybrane": int(a["wybrane"].sum()),
            "srednie_old20": round(float(a["old20"].mean()), 3) if len(a) else None,
            "powody": {str(k): int(v) for k, v in r["powod_odrzucenia"].value_counts().items()},
        }
    sel = acc[acc["wybrane"]]
    (ctx.data / "pseudoslowa.done").write_text("ok\n", encoding="utf-8")
    ctx.save_metrics("pseudoslowa_7", {
        "n_szablonow": int(len(templates)),
        "szablony_wg_puli": templates["pula_szablonu"].value_counts().to_dict(),
        "szablony_wg_pos": templates["pos"].value_counts().to_dict(),
        "n_wygenerowanych": int(len(cand)),
        "n_zaakceptowanych": int(len(acc)),
        "n_odrzuconych": int(len(rej)),
        "n_ocenianych": int(acc["ocena_wymawialnosc"].notna().sum()),
        "n_ocena_pozytywna": int(acc["ocena_pozytywna"].sum()),
        "n_wybranych": int(len(sel)),
        "n_szablonow_z_wybranym": int(sel["szablon"].nunique()),
        "ocena_modelem": bool(ratings),
        "model_generujacy": ctx.cfg["llm"].get("model_pseudoslow"),
        "model_oceniajacy": ctx.cfg["llm"].get("model_oceny_pseudoslow"),
        "odrzucenia_powody": {str(k): int(v) for k, v in rej["powod_odrzucenia"].value_counts().items()},
        "wg_metody": by_method,
        "leksykon": {"lematy_kwjp": len(lex.lemmas), "czeste_formy": len(lex.frequent), "prog_zipf": lex.zipf_frequent,
                     "worldlex": len(lex.worldlex), "slowa_ua_ru": len(ua_ru), "min_typow_ngramu": min_types},
        "progi_oceny": {"min_wymawialnosc": min_pron, "max_podobienstwo": max_sim},
        "rozklady": dist_rows,
        "czas_s": round(t.s, 1),
    })
    log(f"s07: przyjęte={len(acc)} odrzucone={len(rej)} ocenione={int(acc['ocena_wymawialnosc'].notna().sum())} "
        f"wybrane={len(sel)} w {t.s:.1f}s")
