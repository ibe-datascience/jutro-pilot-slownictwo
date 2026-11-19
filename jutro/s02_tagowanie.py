"""Krok 2. Tokenizacja, tagowanie i lematyzacja + porównanie narzędzi (sekcja 4.1).

Wyjście (data/...):
  tagi.parquet            – cały korpus (cel + kontrast), tager produkcyjny: spaCy + Morfeusz2 (interpretacja
                            Morfeusza wybierana zgodnie z tagami spaCy); dla korpusu docelowego dodatkowo lematy
                            samego spaCy i Morfeusza „pierwsza interpretacja”
  tagi_stanza.parquet     – korpus docelowy, Stanza (+ wariant Stanza + Morfeusz2)
  ocena_lematyzacji_300.xlsx (w wyniki/) – próbka 300 form do ręcznego sprawdzenia
Metryki: tagowanie_czasy, ocena_41.
"""
from __future__ import annotations

import csv
import re
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from . import morf
from .common import Ctx, Timer, expand, log, read_jsonl
from .frazy import iter_phrases
from .morf import Tok

COLS = ["mat", "cel", "seg", "typ", "sent", "form", "lemma", "cls", "case", "num", "gen", "known", "upos",
        "lemma_tager", "lemma_mfirst", "cls_mfirst", "oov"]
COARSE = {"subst": "rzeczownik", "ger": "rzeczownik", "depr": "rzeczownik", "adj": "przymiotnik", "pact": "przymiotnik",
          "ppas": "przymiotnik", "adja": "przymiotnik", "adjp": "przymiotnik", "adjc": "przymiotnik",
          "adv": "przyslowek", "fin": "czasownik", "praet": "czasownik", "inf": "czasownik", "impt": "czasownik",
          "imps": "czasownik", "bedzie": "czasownik", "pcon": "czasownik", "pant": "czasownik", "pred": "czasownik",
          "winien": "czasownik"}
UPOS_COARSE = {"NOUN": "rzeczownik", "PROPN": "rzeczownik", "ADJ": "przymiotnik", "VERB": "czasownik", "AUX": "czasownik",
               "ADV": "przyslowek"}


@lru_cache(maxsize=50_000)
def parse_feats(s: str) -> dict[str, str]:
    if not s or s == "_":
        return {}
    return dict(kv.split("=", 1) for kv in s.split("|") if "=" in kv)


@lru_cache(maxsize=1_000_000)
def choose_cached(form: str, upos: str, feats: str, lemma: str, mode: str = "guided") -> morf.Choice:
    return morf.choose(form, upos, parse_feats(feats), lemma, mode=mode)


def iter_segments(ctx: Ctx, only_target: bool = False) -> Iterator[tuple[str, tuple[str, bool, int, str]]]:
    stat_types = set(ctx.cfg["czyszczenie"]["segmenty_do_statystyk"])
    for row in read_jsonl(ctx.data / "korpus.jsonl"):
        if only_target and not row["cel"]:
            continue
        for k, seg in enumerate(row["segmenty"]):
            if seg["typ"] in stat_types:
                yield seg["tekst"], (row["id"], row["cel"], k, seg["typ"])


class Writer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.buf: dict[str, list] = {c: [] for c in COLS}
        self.writer: pq.ParquetWriter | None = None
        self.n = 0

    def add(self, **kw: Any) -> None:
        for c in COLS:
            self.buf[c].append(kw.get(c, ""))
        self.n += 1
        if len(self.buf["form"]) >= 400_000:
            self.flush()

    def flush(self) -> None:
        if not self.buf["form"]:
            return
        table = pa.table(self.buf)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
        self.writer.write_table(table)
        self.buf = {c: [] for c in COLS}

    def close(self) -> None:
        self.flush()
        if self.writer:
            self.writer.close()


def tag_spacy(ctx: Ctx) -> dict[str, Any]:
    import spacy

    model = ctx.cfg["narzedzia"]["spacy_model"]
    procs = int(ctx.cfg["narzedzia"].get("procesy", 4))
    nlp = spacy.load(model, disable=["ner"])
    out = Writer(ctx.data / "tagi.parquet")
    t = Timer()
    n_tok = n_alpha = n_unknown = n_oov = n_target_alpha = n_target_unknown = n_target_oov = 0
    unknown_forms: Counter = Counter()
    for doc, (mat, cel, seg, typ) in nlp.pipe(iter_segments(ctx), as_tuples=True, n_process=procs, batch_size=256):
        for si, sent in enumerate(doc.sents):
            for tok in sent:
                if tok.is_space:
                    continue
                form = tok.text
                upos = tok.pos_
                feats = str(tok.morph)
                ch = choose_cached(form, upos, feats, tok.lemma_)
                alpha = form.replace("-", "").isalpha()
                rec = dict(mat=mat, cel=cel, seg=seg, typ=typ, sent=si, form=form, lemma=ch.lemma, cls=ch.cls,
                           case=ch.case, num=ch.num, gen=ch.gen, known=ch.known, upos=upos, lemma_tager=tok.lemma_,
                           lemma_mfirst="", cls_mfirst="", oov=bool(tok.is_oov))
                if cel:
                    c1 = choose_cached(form, "", "", "", "first")
                    rec["lemma_mfirst"], rec["cls_mfirst"] = c1.lemma, c1.cls
                out.add(**rec)
                n_tok += 1
                if alpha:
                    n_alpha += 1
                    n_unknown += not ch.known
                    n_oov += bool(tok.is_oov)
                    if cel:
                        n_target_alpha += 1
                        n_target_oov += bool(tok.is_oov)
                        if not ch.known:
                            n_target_unknown += 1
                            unknown_forms[form.lower()] += 1
        if n_tok and n_tok % 1_000_000 < 300:
            log(f"  spaCy: {n_tok / 1e6:.1f} M tokenów ({t.s:.0f}s)")
    out.close()
    return {
        "narzedzie": f"spaCy {spacy.__version__} / {model} {nlp.meta['version']} + Morfeusz2 {morf.dict_id()}",
        "tokeny": n_tok, "tokeny_alfabetyczne": n_alpha, "czas_s": round(t.s, 1), "procesy": procs,
        "nierozpoznane_morfeusz_udzial_caly_korpus": round(n_unknown / max(n_alpha, 1), 5),
        "cel_tokeny_alfabetyczne": n_target_alpha,
        "cel_nierozpoznane_morfeusz_udzial": round(n_target_unknown / max(n_target_alpha, 1), 5),
        "cel_nierozpoznane_morfeusz_rozne_formy": len(unknown_forms),
        "cel_spacy_oov_udzial": round(n_target_oov / max(n_target_alpha, 1), 5),
        "cel_najczestsze_nierozpoznane": unknown_forms.most_common(40),
    }


def _stanza_pipeline(ctx: Ctx):
    import stanza

    return stanza.Pipeline("pl", dir=str(expand(ctx.cfg["narzedzia"]["stanza_dir"])), processors="tokenize,mwt,pos,lemma",
                           use_gpu=False, download_method=None, logging_level="ERROR")


def tag_stanza(ctx: Ctx) -> dict[str, Any]:
    import stanza

    nlp = _stanza_pipeline(ctx)
    out = Writer(ctx.data / "tagi_stanza.parquet")
    t = Timer()
    n_tok = 0
    cur: tuple | None = None
    batch: list[tuple[str, tuple]] = []

    def flush_batch() -> None:
        nonlocal n_tok
        if not batch:
            return
        docs = nlp.bulk_process([stanza.Document([], text=txt) for txt, _ in batch])
        for d, (_, (mat, cel, seg, typ)) in zip(docs, batch):
            for si, sent in enumerate(d.sentences):
                for w in sent.words:
                    form = w.text
                    upos = w.upos or ""
                    feats = w.feats or ""
                    ch = choose_cached(form, upos, feats, w.lemma or form)
                    out.add(mat=mat, cel=cel, seg=seg, typ=typ, sent=si, form=form, lemma=ch.lemma, cls=ch.cls,
                            case=ch.case, num=ch.num, gen=ch.gen, known=ch.known, upos=upos,
                            lemma_tager=w.lemma or "", lemma_mfirst="", cls_mfirst="", oov=False)
                    n_tok += 1
        batch.clear()

    for txt, meta in iter_segments(ctx, only_target=True):
        batch.append((txt, meta))
        if len(batch) >= 400:
            flush_batch()
            if n_tok % 100_000 < 6000:
                log(f"  Stanza: {n_tok / 1e3:.0f} tys. tokenów ({t.s:.0f}s)")
    flush_batch()
    out.close()
    return {"narzedzie": f"Stanza {stanza.__version__} (pl, pakiet domyślny)", "tokeny": n_tok, "czas_s": round(t.s, 1),
            "procesy": 1, "urzadzenie": "cpu"}


def timing_benchmark(ctx: Ctx, n_words: int = 60_000) -> dict[str, Any]:
    """Czas przetwarzania tych samych ~n_words słów korpusu docelowego, jeden proces, CPU."""
    import spacy

    texts, total = [], 0
    for txt, _ in iter_segments(ctx, only_target=True):
        texts.append(txt)
        total += len(txt.split())
        if total >= n_words:
            break
    res: dict[str, Any] = {"slowa_w_probie": total, "segmenty": len(texts)}
    nlp = spacy.load(ctx.cfg["narzedzia"]["spacy_model"], disable=["ner"])
    t0 = time.perf_counter()
    forms = []
    for d in nlp.pipe(texts, batch_size=256):
        forms.extend(tok.text for tok in d if not tok.is_space)
    res["spacy_s"] = round(time.perf_counter() - t0, 2)
    m = morf.morf()
    t0 = time.perf_counter()
    for f in forms:
        m.analyse(f)
    res["morfeusz_analiza_s"] = round(time.perf_counter() - t0, 2)
    try:
        import stanza

        snlp = _stanza_pipeline(ctx)
        t0 = time.perf_counter()
        snlp.bulk_process([stanza.Document([], text=t) for t in texts])
        res["stanza_s"] = round(time.perf_counter() - t0, 2)
    except Exception as exc:  # noqa: BLE001
        res["stanza_blad"] = f"{type(exc).__name__}: {exc}"[:200]
    for k in ("spacy_s", "morfeusz_analiza_s", "stanza_s"):
        if k in res:
            res[k.replace("_s", "_slow_na_s")] = round(total / max(res[k], 1e-9))
    return res


def run(ctx: Ctx) -> None:
    times: dict[str, Any] = {}
    log("s02: spaCy + Morfeusz2 na całym korpusie…")
    times["spacy_morfeusz"] = tag_spacy(ctx)
    log(f"s02: {times['spacy_morfeusz']['tokeny']} tokenów w {times['spacy_morfeusz']['czas_s']}s")
    try:
        log("s02: Stanza na korpusie docelowym…")
        times["stanza"] = tag_stanza(ctx)
    except Exception as exc:  # noqa: BLE001
        times["stanza"] = {"blad": f"{type(exc).__name__}: {exc}"[:300]}
        log(f"s02: Stanza niedostępna: {times['stanza']['blad']}")
    log("s02: pomiar czasu (jeden proces, ta sama próbka)…")
    times["benchmark"] = timing_benchmark(ctx)
    times["morfeusz_slownik"] = morf.dict_id()
    ctx.save_metrics("tagowanie_czasy", times)
    (ctx.data / "tagi_produkcyjne.done").write_text("ok", encoding="utf-8")
    from . import s02b_ocena_lematyzacji

    s02b_ocena_lematyzacji.run(ctx)
