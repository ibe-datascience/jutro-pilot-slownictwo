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
    return ctx.load_metrics(name, {}) or {}


def _f(v: Any, nd: int = 3) -> str:
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "tak" if v else "nie"
    if isinstance(v, float):
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") if v == v else "–"
    return str(v)


def _pct(v: Any) -> str:
    return f"{100 * v:.1f}%" if isinstance(v, (int, float)) else "–"


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_brak danych_"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(_f(x) for x in r) + " |")
    return "\n".join(lines)


METHOD_PL = {
    "ll_kontrast": "log-likelihood względem kontrastu", "log_ratio_kontrast": "log ratio względem kontrastu",
    "tfidf_biol": "TF-IDF po przedmiotach", "simple_maths_kwjp": "Simple Maths względem KWJP100",
    "ll_kwjp": "log-likelihood względem KWJP100", "pmi_mwu": "PMI (frazy)", "logdice_mwu": "logDice (frazy)",
    "cvalue_termopl": "C-value (TermoPL)", "rrf": "łączenie rang (RRF)", "frekwencja_cel": "sama frekwencja w biologii",
}
REASON_PL = {
    "znaki_spoza_alfabetu": "znaki spoza alfabetu", "istniejace_slowo": "istniejące słowo",
    "ksztalt_niezgodny_ze_wzorcem": "długość, liczba sylab lub zakończenie inne niż we wzorcu",
    "za_blisko_wzorca": "różni się od wzorca jedną literą", "ortotaktyka": "nietypowy układ liter",
    "literowka_czestego_slowa": "jedna litera od częstego słowa", "homofon": "brzmi jak istniejące słowo",
    "przejrzysta_budowa": "istniejący rdzeń z przedrostkiem lub przyrostkiem, zrost",
    "skojarzenie_wulgarne": "skojarzenie wulgarne", "slowo_ukrainskie_lub_rosyjskie": "słowo ukraińskie lub rosyjskie",
}


def run(ctx: Ctx) -> None:
    t = Timer()
    m41, m42, m43 = _load(ctx, "ocena_41"), _load(ctx, "ekstrakcja_42"), _load(ctx, "frekwencje_43")
    m5, m6, m7, opis = _load(ctx, "llm_5"), _load(ctx, "pule_6"), _load(ctx, "pseudoslowa_7"), _load(ctx, "opis_danych")
    przedmiot = str(ctx.cfg["cel"]["przedmiot"]).lower()

    # Koszty API w chwili pisania raportu: metryki kroku 5 nie obejmują żądań wysłanych później (pseudosłowa).
    # Księga leży w data/ (niepublikowana), więc stan zapisujemy do metryk, z których czyta też strona.
    ledger = llm.cost_summary(ctx)
    if ledger:
        by_task: dict[str, float] = {}
        for r in ledger:
            k = f"{r['zadanie']} / {r['model']}"
            by_task[k] = by_task.get(k, 0.0) + r.get("koszt_usd", 0.0)
        m8k = {"wg_zadania": {k: round(v, 4) for k, v in sorted(by_task.items())},
               "przebieg": round(sum(by_task.values()), 4), "dotychczas": round(llm.spent(ctx), 4)}
        ctx.save_metrics("koszty_8", m8k)
    else:
        m8k = _load(ctx, "koszty_8") or {"wg_zadania": m5.get("koszty_usd_wg_zadania") or {},
                                         "przebieg": m5.get("koszt_usd_przebieg"), "dotychczas": m5.get("koszt_usd_dotychczas")}

    L: list[str] = [
        f"# Raport pilotażu JUTRO – {ctx.cfg['nazwa']} ({ctx.run_name})",
        "",
        f"Wygenerowano: {now_iso()}. Ziarno: `{ctx.seed}`.",
        "",
        "Wszystkie listy są listami kandydatów z procesu automatycznego. Żadna nie została sprawdzona przez "
        "specjalistów, a etykiety modeli nie zostały jeszcze porównane z oceną ludzi.",
        "",
        "## 1. Dane",
        "",
        _md_table(["miara", "wartość"], [
            [f"materiały docelowe ({przedmiot})", opis.get("materialy_cel")],
            ["materiały kontrastowe (inne przedmioty etapu)", opis.get("materialy_kontrast")],
            ["słowa w korpusie docelowym", opis.get("slowa_cel")],
            ["słowa w korpusie kontrastowym", opis.get("slowa_kontrast")],
            ["hasła słowniczków ZPE w materiałach docelowych (różne)", (opis.get("srebrny_standard") or {}).get("rozne_hasla_cel")],
        ]),
        "",
        "## 2. Lematyzacja i tagowanie (4.1)",
        "",
    ]
    rows = [[f"`{name}`", d.get("lemat_dokladny_wszystkie"), d.get("lemat_skladniki_wszystkie"), d.get("lemat_dokladny_ref_redakcja_ZPE")]
            for name, d in (m41.get("narzedzia") or {}).items()]
    rows.sort(key=lambda r: -(r[1] or 0))
    L += [_md_table(["narzędzie", "cała forma zgodna", "składniki zgodne", "zgodna z formą redakcji ZPE"], rows), "",
          f"Próba: {_f(m41.get('n'))} form. Arkusz sprawdzony przez człowieka: **{_f(bool(m41.get('referencja_ludzka_z_arkusza')))}**. "
          "Dopóki nie jest sprawdzony, odniesieniem jest forma podstawowa zapisana przez redakcję ZPE, a gdzie jej brak – "
          "tymczasowa odpowiedź modelu językowego; wyniki nie są więc pomiarem względem złotego standardu.",
          "", f"Tager używany dla całego korpusu: `{ctx.cfg['narzedzia']['tager_produkcyjny']}`.", "",
          "## 3. Frekwencja ogólna (4.3)", ""]
    pok = m43.get("pokrycie_lematow_cel") or {}
    L += [_md_table(["zasób", "udział lematów biologii obecnych w zasobie"],
                    [[k, pok[k]] for k in ("kwjp", "nkjp1m", "subtlex", "wordfreq") if k in pok]), "",
          f"Zasób używany w publikowanych listach: {m43.get('rekomendacja_produkcyjna', '–')}. "
          "SUBTLEX-PL (CC BY-NC-SA 4.0) służy tylko do porównań.", "",
          "## 4. Kandydaci na terminy (4.2)", ""]

    mian = m42.get("mianowniki") or {}
    L += [_md_table(["miara", "wartość"], [
        ["kandydaci przedmiotowi po progach", m42.get("n_kandydatow")],
        ["… jednowyrazowi", m42.get("n_jednowyrazowych")],
        ["… wielowyrazowi", m42.get("n_mwu")],
        ["… obecni tylko w jednym materiale (frekwencja ≥ próg)", m42.get("n_kandydatow_z_jednego_materialu")],
        ["kandydaci ogólni (do puli T1/T2)", m42.get("n_kandydatow_ogolnych")],
        ["odrzuceni jako nazwy własne", m42.get("n_odrzuconych_nazw_wlasnych")],
        ["słowa: korpus docelowy / kontrast / lista KWJP100", f"{_f(mian.get('slowa_cel'))} / {_f(mian.get('slowa_kontrast'))} / {_f(int(mian.get('kwjp_suma_listy') or 0))}"],
        ["terminy zwrócone przez TermoPL", m42.get("termopl_terminow")],
    ]), ""]
    cov = m42.get("srebrny_pokrycie") or {}
    if cov:
        L += ["Ile haseł ze słowniczków ZPE proces w ogóle znajduje (górna granica pełności):", "",
              _md_table(["srebrny standard", "hasła", "wydobyte z korpusu", "wśród kandydatów po progach", "udział"],
                        [[k, d.get("hasla"), d.get("wydobyte_z_korpusu_docelowego"), d.get("wsrod_kandydatow_po_progach"),
                          _pct(d.get("udzial_wsrod_kandydatow"))] for k, d in cov.items()]), ""]
    base = (m42.get("precyzja_poziom_odniesienia") or {}).get("wszystkie", {}).get("vs_union")
    rows = []
    for name, d in (m42.get("precyzja_wzgledem_srebrnego") or {}).items():
        u = (d.get("wszystkie") or {}).get("vs_union") or {}
        if u:
            rows.append([METHOD_PL.get(name, name), u.get("n_ranking"), u.get("p@100"), u.get("p@300"), u.get("r@300"), u.get("r@1000")])
    L += [f"Precyzja i pełność rankingów względem haseł ZPE (oba srebrne standardy łącznie). Udział haseł wśród wszystkich "
          f"kandydatów, czyli precyzja losowego rankingu: **{_f(base)}**.", "",
          _md_table(["metoda", "kandydatów w rankingu", "P@100", "P@300", "R@300", "R@1000"], rows), "",
          "Słowniczki zawierają tylko to, co redakcja ZPE zdecydowała się objaśnić, więc niska precyzja nie oznacza, że "
          "czołówka rankingu jest błędna. Miara służy wyłącznie do porównania metod między sobą.", ""]
    rows = []
    mv = m5.get("metody_wzgledem_etykiet_llm") or {}
    for name, d in mv.items():
        if name == "poziom_odniesienia":
            continue
        a, s, w = d.get("wszystkie") or {}, d.get("jednowyrazowe") or {}, d.get("wielowyrazowe") or {}
        rows.append([METHOD_PL.get(name, name), a.get("p@100"), a.get("p@300"), a.get("p@1000"), s.get("p@300"), w.get("p@300")])
    if rows:
        L += [f"Te same rankingi względem etykiety końcowej T3 z kroku 5 (udział T3 wśród kandydatów przedmiotowych: "
              f"**{_f((mv.get('poziom_odniesienia') or {}).get('wszystkie'))}**). Etykiety pochodzą od modeli, nie od ludzi.", "",
              _md_table(["metoda", "P@100", "P@300", "P@1000", "P@300 słowa", "P@300 frazy"], rows), ""]

    # --- LLM
    mod = m5.get("modele") or {}
    ag = m5.get("zgodnosc_miedzy_modelami") or {}
    L += ["## 5. Klasyfikacja modelami językowymi", "",
          f"Modele klasyfikujące niezależnie: {', '.join(f'`{x}`' for x in mod.get('porownywane', []))}; rozbieżności i przypadki "
          f"o niskiej pewności rozstrzyga `{mod.get('rozstrzygajacy')}`. Wersja promptu: `{m5.get('wersja_promptu')}`. "
          "Model nie widzi etykiet regułowych ani wyników innych modeli.", "",
          _md_table(["miara", "wartość"], [
              ["sklasyfikowani kandydaci", m5.get("n_klasyfikowanych")],
              ["… przedmiotowi", m5.get("n_klasyfikowanych_przedmiotowych")],
              ["… tylko ogólni", m5.get("n_klasyfikowanych_ogolnych")],
              [f"zgodność prosta ({ag.get('para', '')})", ag.get("prosta")],
              ["kappa Cohena", ag.get("kappa")],
              ["rozstrzygane przez trzeci model", m5.get("n_rozstrzyganych")],
              ["pozostawione do przeglądu (brak większości lub niska pewność sędziego)", m5.get("n_do_przegladu")],
              ["formy podstawowe poprawione przez model", m5.get("n_form_poprawionych")],
          ]), ""]
    seg = ag.get("wg_segmentu") or {}
    if seg:
        L += [_md_table(["grupa kandydatów", "n", "zgodność prosta", "kappa"],
                        [[k, d.get("n"), d.get("prosta"), d.get("kappa")] for k, d in seg.items()]), ""]
    fin, fs, fg = m5.get("rozklad_final") or {}, m5.get("rozklad_final_przedmiotowe") or {}, m5.get("rozklad_final_tylko_ogolne") or {}
    L += [_md_table(["etykieta końcowa", "wszyscy", "kandydaci przedmiotowi", "kandydaci tylko ogólni"],
                    [[k, fin.get(k, 0), fs.get(k, 0), fg.get(k, 0)] for k in ("T3", "T3_INNY", "T2", "T1", "SZUM") if k in fin]), ""]
    if m5.get("typy_szumu"):
        L += ["Rodzaje szumu: " + ", ".join(f"{k} – {v}" for k, v in m5["typy_szumu"].items()) + ".", ""]
    js = m5.get("rozstrzygniecia") or {}
    if js:
        L += [f"Rozstrzygnięcia ({_f(js.get('n'))}): z powodu różnych etykiet {_f(js.get('powod_rozbieznosc_etykiet'))}, z powodu niskiej "
              f"pewności przy zgodnych etykietach {_f(js.get('powod_niska_pewnosc_przy_zgodzie'))}. Sędzia zgodził się z: "
              + ", ".join(f"{k} – {v}" for k, v in (js.get("zgodny_z") or {}).items())
              + f"; wybrał etykietę inną niż oba modele {_f(js.get('inny_niz_oba'))} razy.", ""]
    rl = m5.get("regula_wzgledem_llm") or {}
    if rl:
        L += [f"Etykieta regułowa z kroku 4 (progi rozproszenia i frekwencji) rozstrzygała {_f(rl.get('regula_rozstrzygnela'))} z "
              f"{_f(rl.get('n_kandydatow_przedmiotowych'))} kandydatów przedmiotowych i zgadzała się z etykietą końcową w "
              f"{_pct(rl.get('zgodnosc_z_etykieta_koncowa'))} przypadków (precyzja T3: {_pct(rl.get('precyzja_T3_reguly'))}, "
              f"pełność T3: {_pct(rl.get('pelnosc_T3_reguly'))}). Etykiety regułowe nie są używane do budowy pul.", ""]
    ex = m5.get("ekstrakcja_llm") or {}
    if ex.get("n_terminow"):
        L += [f"Metoda porównawcza: `{ex.get('model')}` wypisał terminy wprost z {_f(ex.get('n_materialow'))} materiałów "
              f"({_f(ex.get('n_terminow_T3'))} różnych terminów biologicznych, w tym {_f(ex.get('n_terminow_T3_wielowyrazowych'))} "
              f"wielowyrazowych). Wśród kandydatów z kroku 4 jest {_pct(ex.get('T3_wsrod_kandydatow'))} z nich "
              f"(jednowyrazowe {_pct(ex.get('T3_jednowyrazowe_wsrod_kandydatow'))}, wielowyrazowe "
              f"{_pct(ex.get('T3_wielowyrazowe_wsrod_kandydatow'))}); pozostałe są w pliku `terminy_llm_spoza_kandydatow.csv`.", ""]
    pj = m5.get("pojecia") or {}
    if pj:
        L += [f"Grupowanie w pojęcia (`{pj.get('model', '–')}`, jedno żądanie na całą listę): {_f(pj.get('n_terminow'))} terminów, "
              f"{_f(pj.get('n_grup'))} grup wieloterminowych obejmujących {_f(pj.get('n_terminow_w_grupach'))} terminów.", ""]
    costs = m8k.get("wg_zadania") or {}
    if costs:
        L += ["Koszt API wszystkich kroków (także oceny lematyzacji i pseudosłów), razem z zadaniami wcześniejszych wersji promptów:", "",
              _md_table(["zadanie / model", "koszt USD"], [[k, round(v, 2)] for k, v in costs.items()]), ""]
    L += [f"Koszt API tej konfiguracji łącznie: **{float(m8k.get('dotychczas') or 0):.2f} USD**.", "",
          "Zgodność między modelami nie jest miarą trafności. Precyzję, pełność i F1 względem ludzi można podać dopiero po "
          "wypełnieniu arkusza `zloty_zbior_do_oznaczenia.xlsx` (zapisanego jako `zloty_zbior_oznaczony.xlsx`).", ""]

    # --- pule
    dp = m6.get("dopasowanie") or {}
    L += ["## 6. Pule", "",
          _md_table(["miara", "wartość"], [
              ["pula przedmiotowa (T3)", m6.get("n_pula_przedmiotowa")],
              ["… terminy wielowyrazowe", m6.get("n_pula_przedmiotowa_wielowyrazowe")],
              ["pula ogólna", m6.get("n_pula_ogolna")],
              ["… T1 / T2", f"{_f(m6.get('n_pula_ogolna_T1'))} / {_f(m6.get('n_pula_ogolna_T2'))}"],
              ["pojęcia (grupy terminów)", m6.get("n_pojec")],
              ["… obejmujące więcej niż jeden termin", m6.get("n_pojec_wieloterminowych")],
              ["pozycje w pulach oznaczone do przeglądu", m6.get("n_do_przegladu_w_pulach")],
              ["wiersze złotego zbioru do oznaczenia", m6.get("n_zloty")],
          ]), "",
          f"Dopasowanie: każdemu terminowi przypisano najwyżej jedną pozycję puli ogólnej o tej samej części mowy i liczbie "
          f"wyrazów (przypisanie optymalne, bez powtórzeń; dopuszczalna różnica: {_f((dp.get('progi') or {}).get('max_roznica_zipf'))} "
          f"na skali Zipfa i {_f((dp.get('progi') or {}).get('max_roznica_liter'))} litery). Dopasowano "
          f"{_f(dp.get('n_dopasowanych'))} z {_f(dp.get('n_terminow'))} terminów ({_pct(dp.get('udzial_dopasowanych'))}).", "",
          _md_table(["cecha", "różnica standaryzowana przed", "po dopasowaniu"], [
              ["frekwencja (Zipf)", dp.get("smd_zipf_przed"), dp.get("smd_zipf_po")],
              ["długość w literach", dp.get("smd_liter_przed"), dp.get("smd_liter_po")],
          ]), "",
          _md_table(["warstwa", "terminy", "pozycje puli ogólnej", "dopasowane", "udział"],
                    [[k, d.get("terminy"), d.get("pula_ogolna"), d.get("dopasowane"), _pct(d.get("udzial"))]
                     for k, d in (dp.get("wg_warstwy") or {}).items()]), ""]
    if m6.get("zloty_ocena"):
        L += ["Ocena względem wypełnionego złotego zbioru:", "", "```json",
              json.dumps(m6["zloty_ocena"], ensure_ascii=False, indent=2), "```", ""]

    # --- pseudosłowa
    L += ["## 7. Pseudosłowa (4.4)", "",
          _md_table(["miara", "wartość"], [
              ["szablony (prawdziwe rzeczowniki i czasowniki)", m7.get("n_szablonow")],
              ["kandydaci wygenerowani", m7.get("n_wygenerowanych")],
              ["odrzuceni przez filtry", m7.get("n_odrzuconych")],
              ["po filtrach (różne ciągi)", m7.get("n_zaakceptowanych")],
              ["ocenieni przez model", m7.get("n_ocenianych")],
              ["… ocenieni pozytywnie", m7.get("n_ocena_pozytywna")],
              ["lista rekomendowana (`wybrane`)", m7.get("n_wybranych")],
              ["szablony z co najmniej jednym rekomendowanym pseudosłowem", m7.get("n_szablonow_z_wybranym")],
          ]), ""]
    rows = [[f"`{k}`", d.get("wygenerowane"), _pct(d.get("udzial_przyjetych")), d.get("oceniane"), _pct(d.get("udzial_pozytywnych")),
             d.get("srednia_wymawialnosc"), d.get("srednie_podobienstwo"), d.get("wybrane")]
            for k, d in (m7.get("wg_metody") or {}).items()]
    L += [_md_table(["generator", "wygenerowane", "przeszło filtry", "ocenione", "ocena pozytywna", "wymawialność (1–5)",
                     "podobieństwo do słowa (0–3)", "na liście rekomendowanej"], rows), "",
          _md_table(["powód odrzucenia", "kandydaci"],
                    [[REASON_PL.get(k, k), v] for k, v in (m7.get("odrzucenia_powody") or {}).items()]), ""]
    dist = [d for d in (m7.get("rozklady") or []) if isinstance(d, dict) and d.get("grupa") == "pseudoslowa_wybrane"]
    if dist:
        L += ["Lista rekomendowana względem szablonów (różnica standaryzowana średnich; wartości bliskie 0 oznaczają, że "
              "pseudosłów nie da się odróżnić od słów po samej cesze):", "",
              _md_table(["cecha", "średnia", "odch. std.", "różnica względem szablonów"],
                        [[d.get("cecha"), d.get("srednia"), d.get("odch_std"), d.get("smd_wzgledem_szablonow")] for d in dist]), ""]
    L += [f"Ocena „wymawialności” i skojarzeń pochodzi od modelu `{m7.get('model_oceniajacy')}` i zastępuje ocenę sędziów "
          "tylko na etapie selekcji; lista wymaga oceny przez osoby dwujęzyczne i pilotażu z uczniami.", ""]

    L += ["## 8. Pliki wynikowe", ""]
    for f in ["kandydaci.csv", "pula_przedmiotowa.csv", "pula_ogolna.csv", "pojecia.csv", "terminy_llm_spoza_kandydatow.csv",
              "pseudoslowa.csv", "pseudoslowa_odrzucone.csv", "pseudoslowa_szablony.csv", "pseudoslowa_rozklady.csv",
              "zloty_zbior_do_oznaczenia.xlsx", "ocena_lematyzacji_300.xlsx"]:
        p = ctx.out / f
        L.append(f"- `wyniki/{ctx.cfg['nazwa']}/{ctx.run_name}/{f}`: {'jest' if p.exists() else 'BRAK'}")
    L += ["", "## 9. Wersje", "", "```json", json.dumps(versions(), ensure_ascii=False, indent=2), "```",
          "", "## 10. Ograniczenia", "",
          "- Przebieg na próbce: liczebności i rankingi zmienią się na pełnym korpusie." if ctx.run_name != "pelny" else
          "- Przebieg na pełnym korpusie etapu.",
          "- Klasa materiału jest szacowana regułami z działu tematycznego (katalog ZPE zna tylko etap 4–8).",
          "- Etykiety T1/T2/T3 pochodzą od modeli językowych; złoty zbiór czeka na etykiety ludzi.",
          "- Frekwencja ogólna fraz nie jest dostępna w KWJP100, więc frazy dopasowuje się po frekwencji w korpusie ZPE.",
          "- Kandydat wielowyrazowy musi pasować do wzorca składniowego (przymiotnik + rzeczownik, rzeczownik + dopełniacz); "
          "terminy o innej budowie są widoczne tylko w ekstrakcji modelem.",
          "- Filtr słów ukraińskich i rosyjskich opiera się na transliteracji najczęstszych słów z list wordfreq i nie "
          "zastąpi oceny przez osoby znające te języki.",
          "", f"Czas generowania raportu: {t.s:.1f} s."]
    raport = ctx.out / "raport.md"
    raport.write_text("\n".join(L), encoding="utf-8")

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
