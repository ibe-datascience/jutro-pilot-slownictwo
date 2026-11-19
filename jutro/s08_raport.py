"""Krok 8. raport.md (PL) + strona Quarto (EN): problem, schemat procesu, wszystkie metryki i pełne tabele wyników.

Źródła strony leżą w `site/` (pliki .qmd + `_lib.py`), wynik renderowania w `docs/` (GitHub Pages).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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

    site_ok = render_site(ctx)
    ctx.save_metrics("raport_8", {
        "raport_md": str(raport.relative_to(ROOT)),
        "site_html": str((DOCS / "index.html").relative_to(ROOT)) if site_ok else None,
        "czas_s": round(t.s, 1),
    })
    log(f"s08: {raport}")


SITE = ROOT / "site"
DOCS = ROOT / "docs"


def render_site(ctx: Ctx) -> bool:
    """Renderuje stronę Quarto (`site/` → `docs/`) dla bieżącego przebiegu.

    Strony w `site/*.qmd` są zwykłymi plikami źródłowymi: nie mają liczb wpisanych na stałe, tylko czytają
    `wyniki/<nazwa>/<przebieg>/` w trakcie renderowania. Ta funkcja zapisuje, który przebieg pokazać
    (`site/_przebieg.json`), uruchamia `quarto render` z interpreterem, który wykonuje proces, i kopiuje
    wynik (`site/_site/`) do `docs/`. Nie potrzebuje `data/`, modeli ani klucza API.
    """
    (SITE / "_przebieg.json").write_text(
        json.dumps({"nazwa": ctx.cfg["nazwa"], "przebieg": ctx.run_name}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["QUARTO_PYTHON"] = sys.executable
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")  # jądro Jupytera = to samo środowisko
    try:
        subprocess.run(["quarto", "render", str(SITE)], check=True, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        log("s08: brak `quarto` w PATH – strona nie została odświeżona")
        return False
    except subprocess.CalledProcessError as exc:
        log(f"s08: quarto render nieudany – strona nie została odświeżona:\n{(exc.stderr or str(exc))[-1500:]}")
        return False
    # docs/ jest w całości wynikiem renderowania: podmieniamy go dopiero po udanym renderze
    built = SITE / "_site"
    if DOCS.exists():
        shutil.rmtree(DOCS)
    shutil.copytree(built, DOCS)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    log(f"s08: Quarto → {DOCS / 'index.html'}")
    return True
