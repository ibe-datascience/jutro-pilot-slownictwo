"""Krok 8. raport.md (PL) + strona Quarto HTML (EN) z problemem, krokami i wynikami."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from . import llm
from .common import Ctx, ROOT, Timer, log, now_iso, versions


def _load(ctx: Ctx, name: str) -> Any:
    return ctx.load_metrics(name, {})


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


def run(ctx: Ctx) -> None:
    t = Timer()
    m41 = _load(ctx, "ocena_41")
    m42 = _load(ctx, "ekstrakcja_42")
    m43 = _load(ctx, "frekwencje_43")
    m5 = _load(ctx, "llm_5")
    m6 = _load(ctx, "pule_6")
    m7 = _load(ctx, "pseudoslowa_7")
    opis = _load(ctx, "opis_danych")

    # --- raport PL
    lines = [
        f"# Raport pilotażu JUTRO – {ctx.cfg['nazwa']} ({ctx.run_name})",
        "",
        f"Wygenerowano: {now_iso()}. Ziarno: `{ctx.seed}`.",
        "",
        "## 1. Dane",
        "",
    ]
    if opis:
        lines.append("```json")
        lines.append(json.dumps(opis, ensure_ascii=False, indent=2)[:4000])
        lines.append("```")
    else:
        lines.append("(brak opis_danych.json – uruchom s01)")
    lines += ["", "## 2. Porównanie narzędzi", ""]

    lines.append("### 4.1 Lematyzacja / tagowanie (dokładność lematu na n=300)")
    rows = []
    for name, d in (m41.get("narzedzia") or {}).items():
        rows.append([name, d.get("lemat_dokladny_wszystkie"), d.get("lemat_skladniki_wszystkie"),
                     d.get("lemat_dokladny_ref_redakcja_ZPE")])
    lines.append(_md_table(["narzędzie", "exact", "składniki", "exact|ZPE"], rows) if rows else "_brak_")
    lines.append("")
    lines.append(
        f"Referencja ludzka z arkusza: **{m41.get('referencja_ludzka_z_arkusza')}**. "
        "Do czasu ręcznego sprawdzenia `ocena_lematyzacji_300.xlsx` exact względem ZPE/Opus nie jest złotym standardem badania."
    )
    lines.append("")
    lines.append("**Rekomendacja (ocena agenta):** tager produkcyjny `spacy_morfeusz` "
                 f"(ustawiony w konfiguracji: `{ctx.cfg['narzedzia']['tager_produkcyjny']}`) – najlepszy kompromis "
                 "dokładności frazy i czasu; LLM nieznacznie wyżej na exact, ale kosztowny jako tager korpusu.")
    lines.append("")

    lines.append("### 4.2 Ekstrakcja (precyzja@K względem srebrnego standardu ZPE)")
    rows = []
    for name, d in (m42.get("precyzja_wzgledem_srebrnego") or {}).items():
        if "status" in d:
            rows.append([name, d["status"], "", ""])
            continue
        u = d.get("vs_union") or {}
        rows.append([name, u.get("p@100"), u.get("p@300"), u.get("p@1000")])
    lines.append(_md_table(["metoda", "P@100", "P@300", "P@1000"], rows) if rows else "_brak_")
    lines.append(f"\nKandydatów po filtrach: **{m42.get('n_kandydatow')}** (MWU: {m42.get('n_mwu')}). TermoPL: {m42.get('termopl')}.")
    lines.append("")

    lines.append("### 4.3 Frekwencja ogólna")
    pok = (m43.get("pokrycie_lematow_cel") or {})
    lines.append(_md_table(
        ["zasób", "pokrycie lematów biol."],
        [[k, pok[k]] for k in ("kwjp", "nkjp1m", "subtlex", "wordfreq") if k in pok],
    ))
    lines.append(f"\n{m43.get('rekomendacja_produkcyjna', '')}")
    lines.append("")
    lines.append("**Uwaga licencyjna:** SUBTLEX-PL = CC BY-NC-SA 4.0 – używany tylko w metrykach, nie w CSV produkcyjnych.")
    lines.append("")

    lines.append("### 5. LLM (zgodność ≠ trafność)")
    lines.append(f"- sklasyfikowano: {m5.get('n_klasyfikowanych')}")
    lines.append(f"- rozstrzygnięcia Opus: {m5.get('n_rozstrzyganych_opus')}")
    lines.append(f"- zgodność haiku↔sonnet: {m5.get('zgodnosc_miedzy_modelami')}")
    lines.append(f"- rozkład finalny: {m5.get('rozklad_final')}")
    lines.append(f"- koszt API (cała konfiguracja): **${m5.get('koszt_usd_dotychczas', llm.spent(ctx)):.4f}**")
    lines.append(f"- {m5.get('uwaga', '')}")
    lines.append("")

    lines.append("### 4.4 / B Pseudosłowa")
    lines.append(f"- szablony: {m7.get('n_szablonow')}, zaakceptowane: {m7.get('n_zaakceptowanych')}, "
                 f"odrzucone: {m7.get('n_odrzuconych')}")
    lines.append(f"- powody odrzuceń: `{m7.get('odrzucenia_powody')}`")
    lines.append("")

    lines.append("## 3. Wyniki plików")
    for f in ["kandydaci.csv", "pula_przedmiotowa.csv", "pula_ogolna.csv", "pojecia.csv",
              "pseudoslowa.csv", "pseudoslowa_odrzucone.csv", "zloty_zbior_do_oznaczenia.xlsx",
              "ocena_lematyzacji_300.xlsx"]:
        p = ctx.out / f
        lines.append(f"- `wyniki/{ctx.cfg['nazwa']}/{ctx.run_name}/{f}`: "
                     f"{'OK' if p.exists() else 'BRAK'}")
    lines += ["", "## 4. Wersje", "", "```json", json.dumps(versions(), ensure_ascii=False, indent=2), "```",
              "", "## 5. Ograniczenia",
              "- Klasa materiału jest szacowana regułami z działu tematycznego (katalog ZPE ma tylko etap 4–8).",
              "- Concraft-pl jest dostępny w `resources/tools/concraft`, ale produkcyjny przebieg używa spaCy+Morfeusz.",
              "- Złoty zbiór czeka na etykiety ludzkie – nie raportujemy P/R/F1 modeli względem ludzi.",
              "- Pseudosłowa: UniPseudo/Wuggy zależą od lokalnych zasobów; Imbir to lista gotowa, nie generator.",
              f"", f"Czas generowania raportu: {t.s:.1f}s.",
              ]
    raport = ctx.out / "raport.md"
    raport.write_text("\n".join(lines), encoding="utf-8")

    # --- Quarto EN
    site = ROOT / "site"
    site.mkdir(parents=True, exist_ok=True)
    qmd = site / "index.qmd"
    # embed key numbers
    tools41 = m41.get("narzedzia") or {}
    best41 = max(tools41.items(), key=lambda kv: kv[1].get("lemat_dokladny_wszystkie") or 0, default=(None, {}))
    qmd.write_text(f"""---
title: "JUTRO pilot: subject vocabulary & pseudowords"
subtitle: "Biology · Polish primary school · ZPE materials"
author: "IBE PIB pilot pipeline"
date: today
format:
  html:
    theme: flatly
    toc: true
    toc-depth: 2
    code-fold: true
    embed-resources: true
---

## Problem

Pupils with a migration background may fail a subject test for two different reasons: weak general Polish,
or missing **subject concepts** despite adequate language. JUTRO aims to separate those barriers with three
modules (general word recognition vs pseudowords, word associations, subject-term ↔ image matching).

This pilot builds **candidate lists** for biology (grades 5–8) from ZPE teaching materials. Nothing here is
expert-validated; subject and language specialists make the final call.

## Pipeline

1. Build target (biology) and contrast (other E2 subjects) corpora; strip platform chrome; extract glossary silver standards.
2. Compare taggers/lemmatisers (spaCy, Stanza, Morfeusz, LLM) on a 300-item sample.
3. Attach general-Polish frequencies (KWJP primary; SUBTLEX comparison-only due to NC-SA).
4. Extract term candidates (log-likelihood, TF–IDF, TermoPL C-value, NP patterns + PMI/logDice).
5. LLM classification into T3/T2/T1/SZUM (Haiku vs Sonnet; Opus on disagreements).
6. Build subject & general pools, concept groups, gold set worksheet (no model labels).
7. Generate & filter pseudowords (Wuggy, UniPseudo, Imbir list, LLM) with Morfeusz/homophone/affix filters.
8. This report.

Run: `python -m jutro run --config config/biologia_sp.yaml --probka 50`

## Measured results ({ctx.run_name})

### Lemmatisation (exact match, n={m41.get('n', '—')})

| Tool | Exact | Components |
|------|------:|----------:|
""" + "\n".join(
        f"| {k} | {v.get('lemat_dokladny_wszystkie')} | {v.get('lemat_skladniki_wszystkie')} |"
        for k, v in tools41.items()
    ) + f"""

Production tagger in config: **`{ctx.cfg['narzedzia']['tager_produkcyjny']}`**.
Best exact in this run: **{best41[0]}** ({(best41[1] or {}).get('lemat_dokladny_wszystkie')}).

### Candidate extraction

- Candidates after frequency filters: **{m42.get('n_kandydatow')}** (multiword: {m42.get('n_mwu')})
- TermoPL available: **{m42.get('termopl')}**
- Precision@100 vs ZPE silver union (best methods around 0.12–0.17 in this sample — silver is incomplete; treat as relative).

### LLM classification

- Labelled: **{m5.get('n_klasyfikowanych')}**; Opus adjudications: **{m5.get('n_rozstrzyganych_opus')}**
- Inter-model agreement: `{m5.get('zgodnosc_miedzy_modelami')}`
- Final label mix: `{m5.get('rozklad_final')}`
- API spend so far (this config): **${m5.get('koszt_usd_dotychczas', 0):.4f}**

> Inter-model agreement is **not** accuracy. The gold worksheet awaits human double annotation.

### Pools & pseudowords

- Subject pool (T3): **{m6.get('n_pula_przedmiotowa')}** · General (T1/T2): **{m6.get('n_pula_ogolna')}** · Concepts: **{m6.get('n_pojec')}**
- Pseudowords kept / rejected: **{m7.get('n_zaakceptowanych')}** / **{m7.get('n_odrzuconych')}**
- Rejection reasons: `{m7.get('odrzucenia_powody')}`

## Outputs

Polish detailed report: `wyniki/{ctx.cfg['nazwa']}/{ctx.run_name}/raport.md`

CSV/XLSX deliverables live in the same folder (`kandydaci.csv`, `pula_*.csv`, `pseudoslowa*.csv`, `zloty_zbior_do_oznaczenia.xlsx`).

## Limits

- Grade is **estimated** from thematic keywords (ZPE catalogue only stores stage 4–8).
- SUBTLEX-PL is NC-SA — comparison metrics only.
- Pseudoword UA/RU similarity is a coarse transliteration heuristic for bilingual reviewers.
""", encoding="utf-8")

    # render quarto if available
    html = site / "index.html"
    try:
        subprocess.run(["quarto", "render", str(qmd), "--to", "html"], check=True, capture_output=True, text=True)
        log(f"s08: Quarto → {html}")
    except FileNotFoundError:
        # minimal HTML fallback
        html.write_text(
            "<!DOCTYPE html><meta charset=utf-8><title>JUTRO pilot</title>"
            + "<pre style='white-space:pre-wrap;font-family:system-ui;max-width:50rem;margin:2rem auto'>"
            + qmd.read_text(encoding="utf-8").replace("<", "&lt;")
            + "</pre>",
            encoding="utf-8",
        )
        log("s08: brak `quarto` w PATH – zapisano prosty HTML z treścią QMD")
    except subprocess.CalledProcessError as exc:
        log(f"s08: quarto render failed: {exc.stderr[:500] if exc.stderr else exc}")
        html.write_text(qmd.read_text(encoding="utf-8"), encoding="utf-8")

    ctx.save_metrics("raport_8", {"raport_md": str(raport), "site_html": str(html), "czas_s": round(t.s, 1)})
    log(f"s08: {raport}")
