"""Sekcja 4.1: ocena lematyzacji i tagowania na próbce 300 form z korpusu docelowego.

Skład próbki: 150 rzadkich terminów (jednowyrazowych), 100 wyrażeń wielowyrazowych, 50 pozostałych form.
Referencja:
  * „redakcja ZPE”  – forma podstawowa wpisana przez redaktorów ZPE w odwołaniu do słowniczka (`pojecie-ref`);
                      to referencja stworzona przez ludzi, ale nie na potrzeby tego badania;
  * „tymczasowa”    – propozycja modelu claude-opus-5-5, DO RĘCZNEGO SPRAWDZENIA (arkusz xlsx).
Po ręcznym sprawdzeniu arkusza (kolumny *_czlowiek) i zapisaniu go jako
`ocena_lematyzacji_300_sprawdzone.xlsx` krok przelicza miary względem etykiet ludzkich.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from . import llm, morf
from .common import Ctx, log, read_jsonl
from .frazy import iter_phrases
from .morf import Tok
from .s01_korpus import split_sentences
from .s02_tagowanie import COARSE, UPOS_COARSE, _stanza_pipeline, choose_cached

POS_ENUM = ["rzeczownik", "przymiotnik", "czasownik", "przyslowek", "inna"]
LEMMA_SCHEMA = {
    "type": "object",
    "properties": {
        "lemat": {"type": "string", "description": "forma podstawowa (mianownik; dla wyrażeń poprawna fraza w mianowniku)"},
        "czesc_mowy": {"type": "string", "enum": POS_ENUM},
    },
    "required": ["lemat", "czesc_mowy"],
    "additionalProperties": False,
}
LEMMA_SYSTEM = (
    "Jesteś narzędziem do lematyzacji polskich tekstów szkolnych z biologii. Dostajesz formę (słowo lub wyrażenie "
    "wielowyrazowe) i zdanie, w którym wystąpiła. Podaj formę podstawową: dla rzeczownika mianownik liczby pojedynczej "
    "(liczba mnoga tylko dla rzeczowników bez liczby pojedynczej), dla przymiotnika i imiesłowu przymiotnikowego "
    "mianownik liczby pojedynczej rodzaju męskiego, dla czasownika bezokolicznik, dla rzeczownika odczasownikowego "
    "(np. „oddychanie”) mianownik tego rzeczownika. Dla wyrażenia wielowyrazowego podaj poprawną frazę w mianowniku "
    "liczby pojedynczej, z przymiotnikami uzgodnionymi z rzeczownikiem nadrzędnym i członami dopełniaczowymi bez "
    "zmian (np. „układu krwionośnego” → „układ krwionośny”, „narządów wymiany gazowej” → „narząd wymiany gazowej”). "
    "Pisz małymi literami, chyba że to nazwa własna. Część mowy dotyczy całej formy (dla wyrażenia: członu nadrzędnego)."
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _lemma_set(word: str) -> set[str]:
    ints = morf.analyse(word) or ()
    s = {i.lemma.lower() for i in ints if i.cls != "ign"}
    s |= {morf.nominal_lemma(i, word).lower() for i in ints if i.cls in ("ger", "pact", "ppas")}
    if word != word.lower():
        s |= _lemma_set(word.lower())
    return s or {word.lower()}


def component_match(a: str, b: str) -> bool:
    """Zgodność lematów składników (bez wymagania poprawnej formy mianownikowej całej frazy)."""
    wa, wb = _norm(a).split(), _norm(b).split()
    if len(wa) != len(wb):
        return False
    return all(x == y or (_lemma_set(x) & _lemma_set(y)) for x, y in zip(wa, wb))


def _find_context(row: dict[str, Any], form: str, stat_types: set[str]) -> str | None:
    pat = re.compile(r"(?<![\w-])" + re.escape(form) + r"(?![\w-])")
    for seg in row["segmenty"]:
        if seg["typ"] not in stat_types or seg["typ"] == "tytul":
            continue
        if pat.search(seg["tekst"]):
            for s in split_sentences(seg["tekst"]):
                if pat.search(s) and 4 <= len(s.split()) <= 60:
                    return s
    return None


def build_sample(ctx: Ctx) -> pd.DataFrame:
    rng = ctx.rng("proba_lematyzacji")
    stat_types = set(ctx.cfg["czyszczenie"]["segmenty_do_statystyk"])
    corpus = {r["id"]: r for r in read_jsonl(ctx.data / "korpus.jsonl") if r["cel"]}
    tags = pq.read_table(ctx.data / "tagi.parquet", filters=[("cel", "=", True)]).to_pandas()
    lemma_freq = Counter(tags["lemma"].str.lower())
    quota = {"rzadki termin": 150, "wielowyrazowe": 100, "pozostale": 50}

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(stratum: str, src: str, mat: str, form: str, ref: str | None) -> bool:
        key = _norm(form)
        if key in seen:
            return False
        ctxt = _find_context(corpus[mat], form, stat_types)
        if not ctxt:
            return False
        seen.add(key)
        items.append({"warstwa": stratum, "zrodlo_referencji": src, "material_id": mat, "forma": form,
                      "kontekst": ctxt, "lemat_ref": ref})
        return True

    # --- pary z redakcji ZPE
    refs = []
    with open(ctx.data / "srebrny_pojecie_ref.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["cel"] == "1" and r["forma"] and r["forma_podstawowa"] and r["material_id"] in corpus:
                refs.append(r)
    rng.shuffle(refs)
    n_ref = {"rzadki termin": 100, "wielowyrazowe": 70, "pozostale": 25}
    got = Counter()
    for r in refs:
        form, lem = r["forma"].strip(), r["forma_podstawowa"].strip()
        multi = " " in form
        if multi != (" " in lem):
            continue
        if multi:
            st = "wielowyrazowe"
        else:
            st = "rzadki termin" if lemma_freq.get(lem.lower(), 0) <= 10 else "pozostale"
        if got[st] < min(n_ref[st], quota[st]) and add(st, "redakcja ZPE", r["material_id"], form, lem):
            got[st] += 1

    # --- losowe formy z korpusu (referencja tymczasowa)
    tags["alpha"] = tags["form"].str.match(r"^[^\W\d_]+$")
    single = tags[tags.alpha & tags.upos.isin(["NOUN", "ADJ", "VERB", "ADV"]) & (tags.form.str.len() >= 4)]
    rare = single[single.upos.isin(["NOUN", "ADJ"]) & (single.form.str.len() >= 6)
                  & (single.lemma.str.lower().map(lemma_freq) <= 3) & ~single.form.str[0].str.isupper()]
    rare = rare.drop_duplicates("form")
    for _, r in rare.sample(frac=1.0, random_state=ctx.seed).iterrows():
        if got["rzadki termin"] >= quota["rzadki termin"]:
            break
        if add("rzadki termin", "tymczasowa", r["mat"], r["form"], None):
            got["rzadki termin"] += 1
    common = single[single.lemma.str.lower().map(lemma_freq) >= 20].drop_duplicates("form")
    for _, r in common.sample(frac=1.0, random_state=ctx.seed + 1).iterrows():
        if got["pozostale"] >= quota["pozostale"]:
            break
        if add("pozostale", "tymczasowa", r["mat"], r["form"], None):
            got["pozostale"] += 1
    # losowe wyrażenia wielowyrazowe wg wzorców składniowych
    phr: list[tuple[str, str]] = []
    for (mat, seg, sent), g in tags.groupby(["mat", "seg", "sent"], sort=False):
        toks = [Tok(f, l, c, ca, n, ge, k) for f, l, c, ca, n, ge, k in
                zip(g["form"], g["lemma"], g["cls"], g["case"], g["num"], g["gen"], g["known"])]
        for s, e in iter_phrases(toks, 3):
            phr.append((mat, " ".join(t.form for t in toks[s:e])))
        if len(phr) > 60_000:
            break
    rng.shuffle(phr)
    for mat, form in phr:
        if got["wielowyrazowe"] >= quota["wielowyrazowe"]:
            break
        if add("wielowyrazowe", "tymczasowa", mat, form, None):
            got["wielowyrazowe"] += 1
    df = pd.DataFrame(items)
    df.insert(0, "id", [f"L{n + 1:03d}" for n in range(len(df))])
    return df


def _span_tokens(doc_tokens: list[tuple[int, int, Any]], start: int, end: int) -> list[Any]:
    return [t for s, e, t in doc_tokens if s < end and e > start]


def evaluate_tools(ctx: Ctx, df: pd.DataFrame) -> pd.DataFrame:
    import spacy

    nlp = spacy.load(ctx.cfg["narzedzia"]["spacy_model"], disable=["ner"])
    try:
        snlp = _stanza_pipeline(ctx)
    except Exception as exc:  # noqa: BLE001
        log(f"  Stanza niedostępna w ocenie: {exc}")
        snlp = None
    cols: dict[str, list] = defaultdict(list)
    for _, it in df.iterrows():
        sent, form = it["kontekst"], it["forma"]
        m = re.search(r"(?<![\w-])" + re.escape(form) + r"(?![\w-])", sent)
        start, end = (m.start(), m.end()) if m else (0, 0)
        multi = " " in form
        # --- spaCy
        d = nlp(sent)
        toks = _span_tokens([(t.idx, t.idx + len(t.text), t) for t in d if not t.is_space], start, end)
        raw = [(t.text, t.lemma_, t.pos_, str(t.morph)) for t in toks]
        _fill(cols, "spacy", raw, multi)
        # --- Stanza
        if snlp is not None:
            sd = snlp(sent)
            st = []
            for s_ in sd.sentences:
                for tk in s_.tokens:
                    for w in tk.words:
                        st.append((tk.start_char, tk.end_char, w))
            stoks = _span_tokens(st, start, end)
            raw_s = [(w.text, w.lemma or w.text, w.upos or "", w.feats or "") for w in stoks]
            _fill(cols, "stanza", raw_s, multi)
        # --- Morfeusz, pierwsza interpretacja (tokenizacja spaCy)
        ch = [choose_cached(f, "", "", "", "first") for f, _, _, _ in raw]
        tk = [Tok(f, c.lemma, c.cls, c.case, c.num, c.gen, c.known) for (f, _, _, _), c in zip(raw, ch)]
        cols["morfeusz_pierwsza_lemat"].append(_phrase_or_single(tk, multi))
        cols["morfeusz_pierwsza_pos"].append(COARSE.get(tk[0].cls, "inna") if tk and not multi else "")
    for k, v in cols.items():
        df[k] = v
    return df


def _phrase_or_single(tk: list[Tok], multi: bool) -> str:
    if not tk:
        return ""
    if not multi and len(tk) == 1:
        return tk[0].lemma
    base, _ok = morf.phrase_base(tk, plural=False)
    return base


def _fill(cols: dict[str, list], name: str, raw: list[tuple[str, str, str, str]], multi: bool) -> None:
    # tager „surowy”: lemat tagera; dla wyrażeń – sklejka lematów
    cols[f"{name}_lemat"].append(" ".join(l for _, l, _, _ in raw))
    cols[f"{name}_pos"].append(UPOS_COARSE.get(raw[0][2], "inna") if raw and not multi else "")
    # tager + Morfeusz2 (interpretacja zgodna z tagami) + budowanie frazy w mianowniku
    ch = [choose_cached(f, u, fe, l) for f, l, u, fe in raw]
    tk = [Tok(f, c.lemma, c.cls, c.case, c.num, c.gen, c.known) for (f, _, _, _), c in zip(raw, ch)]
    cols[f"{name}_morfeusz_lemat"].append(_phrase_or_single(tk, multi))
    cols[f"{name}_morfeusz_pos"].append(COARSE.get(tk[0].cls, "inna") if tk and not multi else "")


def run(ctx: Ctx) -> None:
    log("s02b: budowa próbki 300 form…")
    df = build_sample(ctx)
    df = evaluate_tools(ctx, df)
    items = [(r["id"], f"Forma: {r['forma']}\nZdanie: {r['kontekst']}") for _, r in df.iterrows()]
    llm_models = list(ctx.cfg["llm"]["modele_porownywane"])
    for model in llm_models:
        res = llm.run_requests(ctx, "lematyzacja_proba", model, LEMMA_SYSTEM, items, LEMMA_SCHEMA, max_tokens=120, batch=False)
        short = model.replace("claude-", "").replace("-", "_")
        df[f"llm_{short}_lemat"] = [res.get(i, {}).get("lemat", "") for i in df["id"]]
        df[f"llm_{short}_pos"] = [res.get(i, {}).get("czesc_mowy", "") if " " not in f else "" for i, f in zip(df["id"], df["forma"])]
    # referencja tymczasowa (Opus) – dla wszystkich pozycji; używana tam, gdzie brak referencji redakcji ZPE
    opus = ctx.cfg["llm"]["model_rozstrzygajacy"]
    ref = llm.run_requests(ctx, "lematyzacja_referencja", opus, LEMMA_SYSTEM, items, LEMMA_SCHEMA, max_tokens=120, batch=False)
    df["lemat_ref_tymczasowy_opus"] = [ref.get(i, {}).get("lemat", "") for i in df["id"]]
    df["pos_ref_tymczasowy_opus"] = [ref.get(i, {}).get("czesc_mowy", "") for i in df["id"]]
    df["lemat_ref"] = [a if isinstance(a, str) and a else b for a, b in zip(df["lemat_ref"], df["lemat_ref_tymczasowy_opus"])]
    df["lemat_poprawny_czlowiek"] = ""
    df["pos_poprawny_czlowiek"] = ""
    df["uwagi"] = ""

    checked = ctx.out / "ocena_lematyzacji_300_sprawdzone.xlsx"
    human = False
    if checked.exists():
        h = pd.read_excel(checked).set_index("id")
        hl = h["lemat_poprawny_czlowiek"].fillna("").astype(str)
        if (hl.str.len() > 0).mean() > 0.9:
            human = True
            df["lemat_ref"] = [hl.get(i, "") or r for i, r in zip(df["id"], df["lemat_ref"])]
            hp = h["pos_poprawny_czlowiek"].fillna("").astype(str)
            df["pos_ref_tymczasowy_opus"] = [hp.get(i, "") or r for i, r in zip(df["id"], df["pos_ref_tymczasowy_opus"])]

    tools = [c[:-6] for c in df.columns if c.endswith("_lemat")]
    metrics: dict[str, Any] = {"n": len(df), "sklad": df.groupby(["warstwa", "zrodlo_referencji"]).size().reset_index(name="n").to_dict("records"),
                               "referencja_ludzka_z_arkusza": human, "narzedzia": {}}
    single = ~df["forma"].str.contains(" ")
    zpe = df["zrodlo_referencji"] == "redakcja ZPE"
    for tname in tools:
        strict = pd.Series([_norm(a) == _norm(b) for a, b in zip(df[f"{tname}_lemat"], df["lemat_ref"])])
        comp = pd.Series([component_match(a, b) for a, b in zip(df[f"{tname}_lemat"], df["lemat_ref"])])
        pos_ok = pd.Series([a == b for a, b in zip(df[f"{tname}_pos"], df["pos_ref_tymczasowy_opus"])])
        df[f"{tname}_ok"] = strict.astype(int).values
        m = {
            "lemat_dokladny_wszystkie": round(float(strict.mean()), 4),
            "lemat_skladniki_wszystkie": round(float(comp.mean()), 4),
            "lemat_dokladny_ref_redakcja_ZPE": round(float(strict[zpe.values].mean()), 4) if zpe.any() else None,
            "lemat_skladniki_ref_redakcja_ZPE": round(float(comp[zpe.values].mean()), 4) if zpe.any() else None,
            "n_ref_redakcja_ZPE": int(zpe.sum()),
            "lemat_dokladny_ref_tymczasowa": round(float(strict[~zpe.values].mean()), 4) if (~zpe).any() else None,
            "pos_jednowyrazowe_ref_tymczasowa": round(float(pos_ok[single.values].mean()), 4),
            "n_jednowyrazowe": int(single.sum()),
        }
        for st in df["warstwa"].unique():
            mask = (df["warstwa"] == st).values
            m[f"lemat_dokladny__{st}"] = round(float(strict[mask].mean()), 4)
            m[f"lemat_skladniki__{st}"] = round(float(comp[mask].mean()), 4)
        metrics["narzedzia"][tname] = m
    ctx.save_metrics("ocena_41", metrics)
    front = ["id", "warstwa", "zrodlo_referencji", "forma", "kontekst", "lemat_ref", "pos_ref_tymczasowy_opus",
             "lemat_poprawny_czlowiek", "pos_poprawny_czlowiek", "uwagi"]
    df[front + [c for c in df.columns if c not in front]].to_excel(ctx.out / "ocena_lematyzacji_300.xlsx", index=False)
    log("s02b: " + "; ".join(f"{k}: {v['lemat_dokladny_wszystkie']:.2f}" for k, v in metrics["narzedzia"].items()))
