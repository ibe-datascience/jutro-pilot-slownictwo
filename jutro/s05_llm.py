"""Krok 5. Czyszczenie i klasyfikacja kandydatów przez LLM + ekstrakcja referencyjna (sekcja 5 / 4.2).

Wejście: kandydaci_stat.parquet (top N z każdej metody) + konteksty z korpusu.
Wyjście:
  llm_klasyfikacja.parquet – etykiety haiku/sonnet/opus, forma_podstawowa poprawiona, pojęcie, obrazowalność
  llm_ekstrakcja.jsonl – terminy wypisane bezpośrednio z próbek materiałów (model ekstrakcji)
  llm.done
Metryki: llm_5.json (zgodność między modelami, koszty; NIE trafność – brak etykiet ludzkich).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import llm
from .common import Ctx, Timer, log, read_jsonl

CAT_ENUM = ["T3", "T2", "T1", "SZUM"]
CLASS_SCHEMA = {
    "type": "object",
    "properties": {
        "kategoria": {"type": "string", "enum": CAT_ENUM},
        "forma_podstawowa": {"type": "string"},
        "pojecie": {"type": "string"},
        "obrazowalnosc": {"type": "string", "enum": ["tak", "czesciowo", "nie"]},
        "pewnosc": {"type": "string", "enum": ["wysoka", "srednia", "niska"]},
        "uzasadnienie": {"type": "string"},
    },
    "required": ["kategoria", "forma_podstawowa", "pojecie", "obrazowalnosc", "pewnosc", "uzasadnienie"],
    "additionalProperties": False,
}
CLASS_SYSTEM = (
    "Klasyfikujesz kandydatów na słownictwo do testu JUTRO (biologia, szkoła podstawowa, ZPE). "
    "Kategorie: T3 = termin biologiczny przedmiotowy; T2 = słownictwo szkolno-akademickie / język poleceń "
    "obecne w wielu przedmiotach; T1 = słownictwo codzienne; SZUM = błąd ekstrakcji, nazwa własna, fragment frazy, "
    "słowo interfejsu. Popraw formę podstawową, jeśli lematyzacja zawiodła (fraza w mianowniku). "
    "`pojecie` to krótka etykieta wspólna dla wariantów/synonimów. `obrazowalnosc`: czy da się pokazać obrazkiem "
    "lub schematem. Odpowiadaj po polsku w polu uzasadnienie (jedno zdanie)."
)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "terminy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "forma_podstawowa": {"type": "string"},
                    "kategoria": {"type": "string", "enum": ["T3", "T2"]},
                },
                "required": ["forma_podstawowa", "kategoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["terminy"],
    "additionalProperties": False,
}
EXTRACT_SYSTEM = (
    "Z tekstu materiału ZPE z biologii wypisz terminy przedmiotowe (T3) i ważne słownictwo szkolne (T2). "
    "Forma podstawowa w mianowniku; pomiń słowa codzienne i elementy interfejsu. Maks. 40 pozycji."
)


def _contexts(ctx: Ctx, forms: list[str], n_per: int = 2) -> dict[str, list[str]]:
    """Do 2 zdań kontekstu na kandydata z korpusu docelowego."""
    import re

    need = set(forms)
    found: dict[str, list[str]] = {f: [] for f in forms}
    stat = set(ctx.cfg["czyszczenie"]["segmenty_do_statystyk"])
    for row in read_jsonl(ctx.data / "korpus.jsonl"):
        if not row["cel"]:
            continue
        text = " ".join(s["tekst"] for s in row["segmenty"] if s["typ"] in stat)
        low = text.lower()
        for f in list(need):
            if f not in low:
                continue
            # zdanie zawierające formę (przybliżenie)
            for sent in re.split(r"(?<=[.!?])\s+", text):
                if f in sent.lower() and 4 <= len(sent.split()) <= 50:
                    found[f].append(sent.strip())
                    if len(found[f]) >= n_per:
                        need.discard(f)
                        break
        if not need:
            break
    return found


def _select_for_llm(df: pd.DataFrame, top: int) -> pd.DataFrame:
    methods = ["ll_vs_kontrast", "simple_maths_kwjp", "tfidf_biol", "cvalue", "logdice", "pmi"]
    chosen: set[str] = set()
    for col in methods:
        if col not in df.columns:
            continue
        for f in df.sort_values(col, ascending=False)["forma_podstawowa"].head(top):
            chosen.add(f)
    # też szeroko rozproszone (pula ogólna)
    og = int(df.attrs.get("ogolne_do_llm", top)) if False else top
    wide = df[df["n_przedmiotow"] >= 4].sort_values("freq_kontrast", ascending=False).head(top)
    chosen |= set(wide["forma_podstawowa"])
    return df[df["forma_podstawowa"].isin(chosen)].copy()


def _prompt_item(form: str, row: pd.Series, ctxs: list[str]) -> str:
    stats = (
        f"freq_biol={int(row['freq_cel'])}, freq_kontrast={int(row['freq_kontrast'])}, "
        f"n_przedmiotow={int(row['n_przedmiotow'])}, zipf={row['zipf_wordfreq']:.2f}, "
        f"dlugosc={int(row['dlugosc'])}, etykieta_regulowa={row.get('etykieta_regulowa','')}"
    )
    ctx = "\n".join(f"- {c}" for c in (ctxs or ["(brak kontekstu)"]))
    return f"Kandydat: {form}\nStatystyki: {stats}\nKonteksty:\n{ctx}"


def _cohen_kappa(a: list[str], b: list[str]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    pa_ = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = 0.0
    for c in cats:
        pe += (sum(x == c for x in a) / n) * (sum(x == c for x in b) / n)
    if pe >= 1:
        return 1.0
    return round((pa_ - pe) / (1 - pe), 4)


def run(ctx: Ctx) -> None:
    t = Timer()
    if getattr(ctx, "bez_llm", False):
        log("s05: --bez-llm – pomijam wywołania API")
        (ctx.data / "llm.done").write_text("skipped\n", encoding="utf-8")
        return

    df = pq.read_table(ctx.data / "kandydaci_stat.parquet").to_pandas()
    top = int(ctx.cfg["kandydaci"]["top_do_llm"])
    og = int(ctx.cfg["kandydaci"].get("ogolne_do_llm", top))
    # ograniczenie na próbce: nie więcej niż 400 łącznie, żeby nie rozsadzić budżetu
    if ctx.probka:
        top = min(top, 250)
        og = min(og, 250)
    sub = _select_for_llm(df, top)
    # dołóż szerokie
    wide = df[df["n_przedmiotow"] >= 4].sort_values("freq_kontrast", ascending=False).head(og)
    sub = pd.concat([sub, wide]).drop_duplicates("forma_podstawowa")
    log(f"s05: klasyfikacja {len(sub)} kandydatów…")

    forms = sub["forma_podstawowa"].tolist()
    ctx_map = _contexts(ctx, forms)
    items = []
    for _, row in sub.iterrows():
        f = row["forma_podstawowa"]
        cid = "C" + __import__("hashlib").sha1(f.encode()).hexdigest()[:15]
        items.append((cid, _prompt_item(f, row, ctx_map.get(f, []))))
    id_by_form = {f: i for (i, _), f in zip(items, forms)}
    form_by_id = {i: f for f, i in id_by_form.items()}

    models = list(ctx.cfg["llm"]["modele_porownywane"])
    judge = ctx.cfg["llm"]["model_rozstrzygajacy"]
    results: dict[str, dict[str, dict]] = {}
    for model in models:
        results[model] = llm.run_requests(
            ctx, "klasyfikacja", model, CLASS_SYSTEM, items, CLASS_SCHEMA,
            max_tokens=300, batch=bool(ctx.cfg["llm"].get("batch", True)),
        )

    # rozbieżności + niska pewność → opus
    need_judge = []
    for cid, form in form_by_id.items():
        labs = [results[m].get(cid, {}).get("kategoria") for m in models]
        pew = [results[m].get(cid, {}).get("pewnosc") for m in models]
        if len(set(x for x in labs if x)) > 1 or any(p == "niska" for p in pew):
            need_judge.append((cid, next(t for i, t in items if i == cid)))
    log(f"s05: opus rozstrzyga {len(need_judge)} przypadków…")
    judged = {}
    if need_judge:
        judged = llm.run_requests(
            ctx, "klasyfikacja_rozstrzygniecie", judge, CLASS_SYSTEM, need_judge, CLASS_SCHEMA,
            max_tokens=300, batch=bool(ctx.cfg["llm"].get("batch", True)),
        )

    rows = []
    for cid, form in form_by_id.items():
        row = {"id": cid, "forma_wejsciowa": form}
        for model in models:
            r = results[model].get(cid, {})
            short = model.replace("claude-", "").replace("-", "_")
            for k, v in r.items():
                row[f"{short}_{k}"] = v
        if cid in judged:
            r = judged[cid]
            for k, v in r.items():
                row[f"opus_5_5_{k}"] = v
            row["do_przegladu"] = True
            row["kategoria_final"] = r.get("kategoria")
            row["forma_podstawowa"] = r.get("forma_podstawowa") or form
            row["pojecie"] = r.get("pojecie", "")
            row["obrazowalnosc"] = r.get("obrazowalnosc", "")
        else:
            # zgoda modeli – bierz sonnet jeśli jest, inaczej pierwszy
            primary = models[-1] if models else None
            r = results.get(primary, {}).get(cid, {}) or results[models[0]].get(cid, {})
            row["do_przegladu"] = False
            row["kategoria_final"] = r.get("kategoria")
            row["forma_podstawowa"] = r.get("forma_podstawowa") or form
            row["pojecie"] = r.get("pojecie", "")
            row["obrazowalnosc"] = r.get("obrazowalnosc", "")
        # doklej statystyki
        st = sub[sub["forma_podstawowa"] == form].iloc[0]
        for c in ("freq_cel", "freq_kontrast", "n_przedmiotow", "zipf_wordfreq", "dlugosc", "etykieta_regulowa"):
            row[c] = st[c]
        rows.append(row)
    out = pd.DataFrame(rows)
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), ctx.data / "llm_klasyfikacja.parquet",
                   compression="zstd")

    # --- ekstrakcja LLM z próbki materiałów
    rng = ctx.rng("llm_ekstrakcja")
    mats = [r for r in read_jsonl(ctx.data / "korpus.jsonl") if r["cel"]]
    rng.shuffle(mats)
    n_ext = min(30 if ctx.probka else 80, len(mats))
    ext_items = []
    for r in mats[:n_ext]:
        text = "\n".join(s["tekst"] for s in r["segmenty"] if s["typ"] in ("tresc", "definicja", "tytul"))
        text = text[:4000]
        ext_items.append((r["id"][:64], f"Tytuł: {r['tytul']}\n\n{text}"))
    ext_model = ctx.cfg["llm"]["model_ekstrakcji"]
    log(f"s05: ekstrakcja LLM z {len(ext_items)} materiałów ({ext_model})…")
    ext = llm.run_requests(
        ctx, "ekstrakcja_terminow", ext_model, EXTRACT_SYSTEM, ext_items, EXTRACT_SCHEMA,
        max_tokens=800, batch=bool(ctx.cfg["llm"].get("batch", True)),
    )
    with open(ctx.data / "llm_ekstrakcja.jsonl", "w", encoding="utf-8") as fh:
        for mid, payload in ext.items():
            fh.write(json.dumps({"material_id": mid, **payload}, ensure_ascii=False) + "\n")

    # zgodność między modelami (nie trafność!)
    short = [m.replace("claude-", "").replace("-", "_") for m in models]
    labs = {s: out[f"{s}_kategoria"].fillna("").tolist() for s in short if f"{s}_kategoria" in out.columns}
    kappas = {}
    if len(short) >= 2:
        kappas[f"{short[0]}_vs_{short[1]}"] = _cohen_kappa(labs[short[0]], labs[short[1]])
    agree = None
    if len(short) >= 2:
        a, b = labs[short[0]], labs[short[1]]
        agree = round(sum(x == y for x, y in zip(a, b)) / max(len(a), 1), 4)

    metrics = {
        "n_klasyfikowanych": int(len(out)),
        "n_rozstrzyganych_opus": int(out["do_przegladu"].sum()) if "do_przegladu" in out else 0,
        "rozklad_final": out["kategoria_final"].value_counts().to_dict() if "kategoria_final" in out else {},
        "zgodnosc_miedzy_modelami": {"prosta": agree, "kappa": kappas},
        "uwaga": "Zgodność między modelami NIE jest miarą trafności – brak etykiet ludzkich ze złotego zbioru.",
        "n_materialow_ekstrakcja": n_ext,
        "koszt_usd_dotychczas": round(llm.spent(ctx), 4),
        "czas_s": round(t.s, 1),
        "wersja_promptu": ctx.cfg["llm"].get("wersja_promptu"),
    }
    ctx.save_metrics("llm_5", metrics)
    (ctx.data / "llm.done").write_text("ok\n", encoding="utf-8")
    log(f"s05: gotowe; zgodność={agree}, koszt=${metrics['koszt_usd_dotychczas']}")
