"""Krok 1. Zrzut korpusu z materiałów ZPE.

Wejście (tylko do odczytu): katalog ZPE z `catalog.jsonl`, `subjects.json`, `materials/*.html`, `texts/*.txt`.
Wyjście (data/<nazwa>/<przebieg>/):
  korpus.jsonl               – materiał = wiersz; segmenty treści z typem (tytul/tresc/definicja/cwiczenie/podpis/alt)
  srebrny_slowniczek.csv     – hasła słowniczków ZPE (bloki `Concept`) = srebrny standard terminów
  srebrny_pojecie_ref.csv    – pary forma odmieniona → forma podstawowa (odwołania `pojecie-ref`)
  szablony_usuniete.csv      – zdania usunięte jako szablon platformy / polecenie techniczne
oraz metryki `opis_danych`.
"""
from __future__ import annotations

import csv
import html as html_mod
import json
import multiprocessing as mp
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .common import Ctx, Timer, expand, is_dataless, log, read_jsonl, write_jsonl

BLOCK = {
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "section", "figure", "figcaption", "tr", "td",
    "th", "br", "table", "blockquote", "dt", "dd", "article", "header", "footer", "aside", "summary", "details", "hr",
}
DROP_TAGS = ["script", "style", "noscript", "svg", "button", "nav", "form", "select", "input", "iframe", "textarea"]
RES_ID = re.compile(r"\b[RPDM](?=[A-Za-z0-9]{8,15}\b)(?=[A-Za-z]*\d|[a-z0-9]*[A-Z][a-z0-9]*[A-Z])[A-Za-z0-9]{8,15}\b")
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"(\[])")
# Polecenia techniczne interfejsu (nie język poleceń dydaktycznych typu „porównaj”, „uzasadnij”).
UI_RE = re.compile(
    r"\b(kliknij\w*|klikn\w+|klikając\w*|przeciągn\w+|przeciągaj\w*|upuść\w*|naciśnij\w*|najedź\w*|najecha\w+|"
    r"kursor\w*|suwak\w*|przewiń\w*|rozwiń\w*|zwiń\w*|odtwórz\w*|wciśnij\w*|pobierz plik\w*|zaloguj\w*|"
    r"tryb\w* pełnoekranow\w+|pełny ekran|przycisk\w*|zakładk[aęi]\w*|strzałk\w+ (w lewo|w prawo|na klawiaturze)|"
    r"ekran\w* dotykow\w+|czytnik\w* ekranu|panel\w* bocz\w+)\b",
    re.IGNORECASE,
)
META_RE = re.compile(
    r"^(źródło:|licencja:|autor(zy)?:|opracowanie:|fot\.|il\.|film dostępny pod adresem|nagranie dostępne pod adresem|"
    r"nagranie dźwiękowe|aplikacja dostępna pod adresem|ilustracja interaktywna dostępna|możliwe odpowiedzi:?$|"
    r"poziom trudności|pokaż (odpowiedź|podpowiedź|więcej)|ukryj|głośność|transkrypcja)",
    re.IGNORECASE,
)
LICENCE_RE = re.compile(r"(licencja: ?CC|CC BY|domena publiczna|wikimedia commons|\(…\)\s*$|dostępny w internecie:)", re.I)
GRADE_RE = re.compile(r"\bklas\w{0,3}\s+(VIII|VII|VI|IV|V|[4-8])\b(?!\s*[–-]\s*(VIII|VII|VI|V|[5-8]))")
ROMAN = {"IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


# --------------------------------------------------------------------------------------
# Parsowanie pojedynczej jednostki HTML
# --------------------------------------------------------------------------------------
def _has_class(cls: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {cls} ")'


def _walk(e, out: list[str]) -> None:
    tag = e.tag
    blk = tag in BLOCK
    if blk:
        out.append("\n")
    if e.text:
        out.append(e.text)
    for ch in e:
        if isinstance(ch.tag, str):
            _walk(ch, out)
        if ch.tail:
            out.append(ch.tail)
    if blk:
        out.append("\n")


def clean_line(s: str) -> str:
    s = html_mod.unescape(html_mod.unescape(s))
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\u2011", "-").replace("\u00ad", "").replace("\u200b", "")
    s = re.sub(r"[\u00a0\u2007\u202f\u2009\u200a]", " ", s)
    s = RES_ID.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def lines_of(e) -> list[str]:
    out: list[str] = []
    _walk(e, out)
    res = []
    for ln in "".join(out).split("\n"):
        ln = clean_line(ln)
        if ln and any(ch.isalpha() for ch in ln):
            res.append(ln)
    return res


def _drop(e) -> None:
    try:
        e.drop_tree()
    except Exception:
        par = e.getparent()
        if par is not None:
            par.remove(e)


def parse_unit(html_text: str) -> dict[str, Any]:
    from lxml import html as LH

    doc = LH.fromstring(html_text)
    roots = doc.xpath(f"//*[{_has_class('page-container')}]") or doc.xpath('//*[@id="main-content"]')
    root = roots[0] if roots else (doc.find("body") if doc.find("body") is not None else doc)
    segs: list[tuple[str, str]] = []
    glossary: list[tuple[str, str]] = []
    refs: list[tuple[str, str]] = []

    for tag in DROP_TAGS:
        for e in root.xpath(f".//{tag}"):
            _drop(e)

    # odwołania do pojęć: forma w tekście + forma podstawowa
    for sp in root.xpath('.//span[@data-specifier-type="pojecie-ref"]'):
        form = clean_line(" ".join(sp.xpath("./span[@data-alternative]//text()")))
        lemma = clean_line(" ".join(sp.xpath(".//span[@data-cp-editor-value]//text()")))
        vis = clean_line(" ".join(sp.xpath('.//a[contains(@class,"cp-concept-link")]//text()'))) or form
        if vis and lemma:
            refs.append((vis, lemma))
        tail = sp.tail
        sp.clear()
        sp.tail = tail
        sp.text = vis

    # słowniczek: bloki Concept (pojęcie + definicja)
    for blk in root.xpath('.//*[@data-block-name="Concept"]'):
        term = clean_line(" ".join(blk.xpath('.//span[@data-specifier-type="pojecie"]/span[@data-value]//text()')))
        if not term:
            term = clean_line(" ".join(blk.xpath(f".//*[{_has_class('note__title')}]//text()")))
        body = blk.xpath(".//*[@data-editor-content]")
        definition = " ".join(lines_of(body[0])) if body else ""
        if term:
            glossary.append((term, definition))
            segs.append(("definicja", term))
            if definition:
                segs.append(("definicja", definition))
        _drop(blk)

    # opisy alternatywne (WCAG): osobny typ segmentu
    alts: list[str] = []
    for e in root.xpath(f".//*[{_has_class('cp-editor-alt')}]"):
        alts.extend(lines_of(e))
        _drop(e)
    for a in root.xpath(".//img/@alt"):
        a = clean_line(a)
        if a:
            alts.append(a)
    for e in root.xpath(f".//*[{_has_class('print-only')}]"):
        alts.extend(lines_of(e))
        _drop(e)
    for e in root.xpath(f".//*[{_has_class('sr-only')}]"):
        if not e.xpath(f"ancestor::figure[{_has_class('exercise')}]"):
            alts.extend(lines_of(e))
            _drop(e)

    for xp in [
        ".//*[@data-specifier-type]", ".//*[@data-editor-params]", f".//*[{_has_class('figure_caption_bibliography')}]",
        f".//*[{_has_class('wrapper_comments-container')}]", f".//*[{_has_class('parameters-container')}]",
        f".//*[{_has_class('dummy-node')}]", f".//*[{_has_class('womi-container-v2')}]",
        f".//*[{_has_class('elearning_exercise__title')}]", f".//*[{_has_class('difficulty-picker')}]",
    ]:
        for e in root.xpath(xp):
            _drop(e)

    # ćwiczenia
    for blk in root.xpath('.//*[@data-block-name="StaticExercise"]'):
        if blk.xpath('ancestor::*[@data-block-name="StaticExercise"]'):
            continue
        segs.extend(("cwiczenie", ln) for ln in lines_of(blk))
        _drop(blk)
    for blk in root.xpath(f".//figure[{_has_class('exercise')}]"):
        segs.extend(("cwiczenie", ln) for ln in lines_of(blk))
        _drop(blk)

    # podpisy pod ilustracjami
    for cap in root.xpath(".//figcaption"):
        segs.extend(("podpis", ln) for ln in lines_of(cap))
        _drop(cap)

    segs.extend(("tresc", ln) for ln in lines_of(root))
    seen = set()
    for a in alts:
        if a not in seen and any(ch.isalpha() for ch in a):
            seen.add(a)
            segs.append(("alt", a))
    blocks = Counter(root.xpath(".//@data-block-name"))
    return {"segs": segs, "glossary": glossary, "refs": refs, "blocks": dict(blocks)}


def _process_material(args: tuple[str, str]) -> dict[str, Any]:
    mid, zpe_dir = args
    zpe = Path(zpe_dir)
    res: dict[str, Any] = {"id": mid, "segs": [], "glossary": [], "refs": [], "n_units": 0, "n_html": 0,
                           "dataless": 0, "source": "html", "error": None}
    man_path = zpe / "materials" / f"{mid}.manifest.json"
    try:
        res["dataless"] += int(is_dataless(man_path))
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    except Exception as exc:  # brak manifestu → tekst zapasowy
        manifest = {}
        res["error"] = f"manifest: {type(exc).__name__}"
    toc = manifest.get("tableOfContents") or []
    res["n_units"] = len(toc)
    for item in toc:
        code = str(item.get("code") or "")
        uid = code[:-3] if code.endswith("_pl") else None
        if not uid:
            continue
        hp = zpe / "materials" / f"{mid}_{uid}.html"
        if not hp.exists():
            continue
        try:
            res["dataless"] += int(is_dataless(hp))
            parsed = parse_unit(hp.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            res["error"] = f"html {uid}: {type(exc).__name__}: {exc}"[:200]
            continue
        res["n_html"] += 1
        title = clean_line(re.sub(r"<[^>]+>", " ", str(item.get("title") or "")))
        if title:
            res["segs"].append(("tytul", title))
        res["segs"].extend(parsed["segs"])
        res["glossary"].extend(parsed["glossary"])
        res["refs"].extend(parsed["refs"])
    desc = manifest.get("description")
    if desc:
        d = clean_line(re.sub(r"<[^>]+>", " ", str(desc)))
        if d:
            res["segs"].append(("tresc", d))
    if res["n_html"] == 0:
        # brak HTML: tekst zapasowy ze scrapera (bez podziału na typy, z nawigacją) – oznaczony
        tp = zpe / "texts" / f"{mid}.txt"
        if tp.exists():
            res["source"] = "txt"
            res["dataless"] += int(is_dataless(tp))
            txt = tp.read_text(encoding="utf-8", errors="replace")
            for ln in txt.split("\n"):
                ln = clean_line(ln)
                if ln:
                    res["segs"].append(("tresc", ln))
        else:
            res["source"] = "brak"
    return res


# --------------------------------------------------------------------------------------
# Dobór materiałów
# --------------------------------------------------------------------------------------
def select_materials(ctx: Ctx) -> list[dict[str, Any]]:
    cfg = ctx.cfg
    zpe = expand(cfg["zrodlo"]["zpe_dir"])
    stage = cfg["cel"]["etap_kod"]
    subjects = json.loads((zpe / "subjects.json").read_text(encoding="utf-8"))
    subj_stage = {s["id"]: (s["educationalStage"] or {}).get("code") for s in subjects}
    subj_name = {s["id"]: s["name"] for s in subjects}
    target_name = cfg["cel"]["przedmiot"]
    excl_types = set(cfg["cel"].get("typy_wyklucz") or [])
    excl_subj = set(cfg["kontrast"].get("przedmioty_wyklucz") or [])
    out = []
    stats = Counter()
    for r in read_jsonl(zpe / "catalog.jsonl"):
        stages = (r.get("etap_kod") or "").split("; ")
        if stage not in stages:
            continue
        stats["etap"] += 1
        sids = (r.get("extra") or {}).get("subject_ids") or []
        names = []
        for sid in sids:
            if subj_stage.get(sid) == stage and subj_name.get(sid) and subj_name[sid] not in names:
                names.append(subj_name[sid])
        if not names:
            stats["bez_przedmiotu_etapu"] += 1
            continue
        if r.get("typ_materialu") in excl_types:
            stats["typ_wykluczony"] += 1
            continue
        is_target = target_name in names
        if not is_target:
            names_k = [n for n in names if n not in excl_subj]
            if not names_k:
                stats["tylko_jezyk_obcy"] += 1
                continue
            names = names_k
        out.append({
            "id": r["id"], "tytul": clean_line(re.sub(r"<[^>]+>", " ", r.get("title") or "")),
            "przedmioty": names, "cel": is_target, "tylko_cel": is_target and names == [target_name],
            "typ": r.get("typ_materialu"), "etap_kod": r.get("etap_kod"), "klasa_katalog": r.get("klasa"),
            "url": r.get("url"),
        })
    stats["wybrane"] = len(out)
    stats["cel"] = sum(m["cel"] for m in out)
    ctx.save_metrics("dobor_materialow", dict(stats))
    return out


def sample_materials(ctx: Ctx, mats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ctx.probka:
        return mats
    rng = ctx.rng("probka")
    target = sorted((m for m in mats if m["cel"]), key=lambda m: m["id"])
    contrast = sorted((m for m in mats if not m["cel"]), key=lambda m: m["id"])
    t = rng.sample(target, min(ctx.probka, len(target)))
    c = rng.sample(contrast, min(ctx.probka * 6, len(contrast)))
    return t + c


# --------------------------------------------------------------------------------------
# Szablony i statystyki
# --------------------------------------------------------------------------------------
def norm_sentence(s: str) -> str:
    s = re.sub(r"\d+", "0", s.lower())
    return re.sub(r"[^\w ]+", "", s).strip()


def split_sentences(line: str) -> list[str]:
    return [s for s in SENT_SPLIT.split(line) if s.strip()]


def n_words(s: str) -> int:
    return len(WORD.findall(s))


def estimate_grade(cfg: dict[str, Any], title: str, text: str) -> dict[str, Any]:
    """Szacunek klasy z działu tematycznego (reguły słów-kluczy). To NIE jest atrybut ze źródła."""
    blocks = cfg["klasa_szacowana"]["bloki"]
    n = max(n_words(text), 1)
    scores = {}
    for grade, pats in blocks.items():
        sc = 0.0
        for p in pats:
            rx = re.compile(p, re.IGNORECASE)
            sc += len(rx.findall(text)) + 8 * len(rx.findall(title))
        scores[int(grade)] = sc
    total = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    explicit = sorted({ROMAN.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else None)
                       for m in GRADE_RE.finditer(text)} - {None})
    if total < 5 or ranked[0][1] == 0:
        return {"klasa_szac_reguly": None, "klasa_szac_reguly_udzial": None, "klasa_szac_reguly_pewnosc": "brak",
                "klasa_w_tresci": explicit, "klasa_punkty": scores}
    share = ranked[0][1] / total
    conf = "wysoka" if share >= 0.6 else ("srednia" if share >= 0.45 else "niska")
    return {"klasa_szac_reguly": ranked[0][0], "klasa_szac_reguly_udzial": round(share, 3),
            "klasa_szac_reguly_pewnosc": conf, "klasa_w_tresci": explicit, "klasa_punkty": scores,
            "klasa_slow_kluczy_na_1000": round(1000 * total / n, 1)}


def run(ctx: Ctx) -> None:
    cfg = ctx.cfg
    zpe = expand(cfg["zrodlo"]["zpe_dir"])
    t = Timer()
    mats = sample_materials(ctx, select_materials(ctx))
    log(f"s01: {len(mats)} materiałów (cel: {sum(m['cel'] for m in mats)}); parsowanie HTML…")
    by_id = {m["id"]: m for m in mats}
    procs = int(cfg["narzedzia"].get("procesy", 4))
    results: dict[str, dict[str, Any]] = {}
    with mp.Pool(procs) as pool:
        for i, res in enumerate(pool.imap_unordered(_process_material, [(m["id"], str(zpe)) for m in mats], chunksize=4)):
            results[res["id"]] = res
            if (i + 1) % 500 == 0:
                log(f"  {i + 1}/{len(mats)} ({t.s:.0f}s)")
    log(f"s01: sparsowano w {t.s:.0f}s; wykrywanie szablonów…")

    # --- szablony: zdania powtarzające się w wielu materiałach etapu
    df = Counter()
    for res in results.values():
        seen = set()
        for typ, line in res["segs"]:
            for s in split_sentences(line):
                if n_words(s) <= cfg["czyszczenie"]["szablon_max_slow"]:
                    seen.add(norm_sentence(s))
        df.update(seen)
    min_df = cfg["czyszczenie"]["szablon_min_materialow"]
    if ctx.probka:
        min_df = max(4, round(min_df * len(mats) / 6000))
    templates = {s for s, c in df.items() if c >= min_df and s}
    removed = Counter()
    removed_reason: dict[str, str] = {}

    def filter_line(typ: str, line: str) -> str:
        if typ == "tytul":
            return line
        keep = []
        for s in split_sentences(line):
            ns = norm_sentence(s)
            reason = None
            if META_RE.search(s.strip()) or (LICENCE_RE.search(s) and n_words(s) <= 25):
                reason = "metadane/licencja"
            elif UI_RE.search(s):
                reason = "polecenie techniczne"
            elif ns in templates:
                reason = "szablon powtarzalny"
            if reason:
                removed[ns] += 1
                removed_reason[ns] = reason
            else:
                keep.append(s)
        return " ".join(keep)

    stat_types = set(cfg["czyszczenie"]["segmenty_do_statystyk"])
    tok_by_subject = Counter()
    mat_by_subject = Counter()
    tok_by_type = Counter()
    tok_target_by_type = Counter()
    tok_removed = 0
    rows = []
    gloss_rows, ref_rows = [], []
    src_counter = Counter()
    dataless = 0
    errors = []
    grade_counter = Counter()
    typ_counter = Counter()
    for mid, m in by_id.items():
        res = results[mid]
        segs = []
        for typ, line in res["segs"]:
            before = n_words(line)
            line2 = filter_line(typ, line)
            tok_removed += before - n_words(line2)
            if line2 and any(ch.isalpha() for ch in line2):
                segs.append({"typ": typ, "tekst": line2})
        # usuwamy powtórzenia tego samego wiersza w obrębie materiału (np. tytuł w każdej jednostce)
        dedup, seen = [], set()
        for sgm in segs:
            key = (sgm["typ"], sgm["tekst"])
            if sgm["typ"] in ("tytul",) and key in seen:
                continue
            seen.add(key)
            dedup.append(sgm)
        segs = dedup
        n_stat = sum(n_words(s["tekst"]) for s in segs if s["typ"] in stat_types)
        row = dict(m)
        row.update({"n_jednostek": res["n_units"], "n_html": res["n_html"], "zrodlo_tresci": res["source"],
                    "n_slow": n_stat, "segmenty": segs})
        if m["cel"]:
            text = " ".join(s["tekst"] for s in segs if s["typ"] in stat_types)
            row.update(estimate_grade(cfg, m["tytul"], text))
            grade_counter[str(row["klasa_szac_reguly"])] += 1
            typ_counter[m["typ"]] += 1
            for typ_, n_ in Counter({s["typ"]: 0 for s in segs}).items():
                pass
            for s in segs:
                tok_target_by_type[s["typ"]] += n_words(s["tekst"])
        for s in segs:
            tok_by_type[s["typ"]] += n_words(s["tekst"])
        for subj in m["przedmioty"]:
            tok_by_subject[subj] += n_stat
            mat_by_subject[subj] += 1
        src_counter[res["source"]] += 1
        dataless += res["dataless"]
        if res["error"]:
            errors.append({"id": mid, "blad": res["error"]})
        for term, definition in res["glossary"]:
            gloss_rows.append({"material_id": mid, "cel": int(m["cel"]), "przedmioty": "; ".join(m["przedmioty"]),
                               "termin": term, "definicja": definition})
        for form, lemma in res["refs"]:
            ref_rows.append({"material_id": mid, "cel": int(m["cel"]), "forma": form, "forma_podstawowa": lemma})
        rows.append(row)

    rows.sort(key=lambda r: (not r["cel"], r["id"]))
    write_jsonl(ctx.data / "korpus.jsonl", rows)
    for name, data in [("srebrny_slowniczek.csv", gloss_rows), ("srebrny_pojecie_ref.csv", ref_rows)]:
        with open(ctx.data / name, "w", encoding="utf-8", newline="") as fh:
            if data:
                w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
                w.writeheader()
                w.writerows(data)
    with open(ctx.data / "szablony_usuniete.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["zdanie_znormalizowane", "liczba_usuniec", "liczba_materialow", "powod"])
        for s, c in removed.most_common():
            w.writerow([s, c, df.get(s, ""), removed_reason[s]])

    target_rows = [r for r in rows if r["cel"]]
    tg = [g for g in gloss_rows if g["cel"]]
    desc = {
        "zrodlo": str(zpe),
        "pola_katalogu": ["source", "id", "title", "typ_materialu", "przedmiot", "etap", "etap_kod", "klasa", "url",
                          "authors", "extra{subject_ids, stage_ids, student_content, teacher_content, cover, "
                          "has_validable_exercises, searcher}"],
        "materialy_lacznie": len(rows),
        "materialy_cel": len(target_rows),
        "materialy_cel_tylko_ten_przedmiot": sum(r["tylko_cel"] for r in target_rows),
        "materialy_kontrast": len(rows) - len(target_rows),
        "jednostki_html_cel": sum(r["n_html"] for r in target_rows),
        "slowa_cel": sum(r["n_slow"] for r in target_rows),
        "slowa_kontrast": sum(r["n_slow"] for r in rows if not r["cel"]),
        "slowa_cel_wg_typu_segmentu": dict(tok_target_by_type),
        "slowa_wszystkie_wg_typu_segmentu": dict(tok_by_type),
        "segmenty_w_statystykach": sorted(stat_types),
        "materialy_wg_przedmiotu": dict(mat_by_subject.most_common()),
        "slowa_wg_przedmiotu": dict(tok_by_subject.most_common()),
        "materialy_cel_wg_typu": dict(typ_counter.most_common()),
        "klasa_katalog_cel": dict(Counter(str(r["klasa_katalog"]) for r in target_rows)),
        "klasa_szac_reguly_cel": dict(grade_counter),
        "klasa_szac_pewnosc_cel": dict(Counter(r.get("klasa_szac_reguly_pewnosc") for r in target_rows)),
        "klasa_jawnie_w_tresci_cel": sum(bool(r.get("klasa_w_tresci")) for r in target_rows),
        "zrodlo_tresci": dict(src_counter),
        "pliki_pobrane_z_icloud": dataless,
        "bledy_parsowania": errors[:50],
        "liczba_bledow": len(errors),
        "szablony": {"prog_materialow": min_df, "rozne_zdania_usuniete": len(removed),
                     "usuniecia_lacznie": sum(removed.values()), "slowa_usuniete": tok_removed,
                     "wg_powodu": dict(Counter(removed_reason[s] for s in removed))},
        "srebrny_standard": {
            "hasla_slowniczka_cel": len(tg), "rozne_hasla_cel": len({g["termin"].lower() for g in tg}),
            "materialy_cel_ze_slowniczkiem": len({g["material_id"] for g in tg}),
            "hasla_slowniczka_kontrast": len(gloss_rows) - len(tg),
            "pary_forma_lemat_cel": sum(r["cel"] for r in ref_rows),
            "rozne_pary_forma_lemat_cel": len({(r["forma"].lower(), r["forma_podstawowa"].lower()) for r in ref_rows if r["cel"]}),
        },
        "czas_s": round(t.s, 1),
    }
    ctx.save_metrics("opis_danych", desc)
    log(f"s01: gotowe w {t.s:.0f}s – cel {desc['materialy_cel']} mat./{desc['slowa_cel']} słów, "
        f"kontrast {desc['materialy_kontrast']} mat./{desc['slowa_kontrast']} słów, "
        f"słowniczek {desc['srebrny_standard']['rozne_hasla_cel']} haseł")
