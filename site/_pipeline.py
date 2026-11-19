"""Schemat techniczny procesu: co każdy krok czyta, co robi i co zapisuje.

Opis jest utrzymywany ręcznie na podstawie modułów `jutro/s0*.py` (nazwy plików i progi z kodu i konfiguracji).
`diagram(cfg)` zwraca HTML; wygląd jest w `styles.css` (klasy `pl-*`).
"""
from __future__ import annotations

from html import escape
from typing import Any


def _chip(kind: str, name: str, note: str = "", src: int | None = None, href: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "name": name, "note": note, "src": src, "href": href}


def ext(name: str, note: str = "") -> dict[str, Any]:
    """Zasób lub narzędzie spoza repozytorium."""
    return _chip("ext", name, note)


def mid(name: str, note: str = "", src: int | None = None) -> dict[str, Any]:
    """Plik pośredni w data/<nazwa>/<przebieg>/ (src = numer kroku, który go zapisał)."""
    return _chip("mid", name, note, src)


def out(name: str, href: str, note: str = "", src: int | None = None) -> dict[str, Any]:
    """Plik wynikowy w wyniki/<nazwa>/<przebieg>/, pokazany na stronie `href`."""
    return _chip("out", name, note, src, href)


def met(name: str, anchor: str) -> dict[str, Any]:
    """Plik metryk kroku; odnośnik do sekcji strony Results."""
    return _chip("met", f"metryki/{name}.json", "", None, f"results.html#{anchor}")


def steps(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    k, l, p = cfg["kandydaci"], cfg["llm"], cfg["pseudoslowa"]
    short = lambda m: m.replace("claude-", "").replace("-", " ").title().replace(" 5 5", " 5.5")
    m1, m2 = (short(m) for m in l["modele_porownywane"][:2])
    judge, extractor = short(l["model_rozstrzygajacy"]), short(l["model_ekstrakcji"])
    stage = cfg["cel"]["etap_kod"]
    return [
        {
            "n": 1, "name": "korpus", "title": "Build the corpus", "modules": "s01_korpus.py",
            "reads": [ext("ZPE dump", "catalog.jsonl · subjects.json · materials/*.html · texts/*.txt")],
            "does": [
                f"Select catalogue entries of school stage {stage}: materials of the target subject "
                f"({cfg['cel']['przedmiot']}) and, as contrast, of all other subjects. Teacher-facing material types and "
                "foreign-language subjects are dropped.",
                "With <code>--probka N</code>: draw N target and 6·N contrast materials (seeded).",
                "Parse the HTML into typed segments: title, body, definition, exercise, caption, image description.",
                "Remove sentences repeated across many materials (platform templates), interface instructions and "
                "licence or metadata lines.",
                "Estimate the grade of each target material from topic keywords.",
                "Collect glossary entries and the editors' pairs <i>inflected form → base form</i> as silver standards.",
            ],
            "writes": [mid("korpus.jsonl", "one material per row, typed segments"),
                       mid("srebrny_slowniczek.csv", "glossary entries"),
                       mid("srebrny_pojecie_ref.csv", "form → base form pairs"),
                       mid("szablony_usuniete.csv", "removed sentences, with reason"),
                       met("opis_danych", "corpus"), met("dobor_materialow", "corpus")],
        },
        {
            "n": 2, "name": "tagowanie", "title": "Tag and lemmatise; compare tools",
            "modules": "s02_tagowanie.py · s02b_ocena_lematyzacji.py · morf.py",
            "reads": [mid("korpus.jsonl", src=1), mid("srebrny_pojecie_ref.csv", "reference lemmas", src=1),
                      ext(f"spaCy {cfg['narzedzia']['spacy_model']}"), ext("Morfeusz2 + SGJP dictionary"),
                      ext("Stanza, Polish models"), ext("Claude API", "LLM lemmatisers, provisional reference")],
            "does": [
                "Whole corpus: spaCy tokenises and tags; for each token the Morfeusz2 reading that agrees with spaCy's "
                "part of speech, case, number and gender gives the lemma and inflectional class.",
                "Target corpus again with Stanza, for comparison; speed test of the three tools on the same text.",
                "Benchmark on 300 forms (150 rare terms, 100 multiword expressions, 50 others): spaCy and Stanza, each "
                f"alone and with Morfeusz2, Morfeusz2 first reading, {m1} and {m2}.",
                f"Reference: the editors' base form where ZPE has one, otherwise a provisional answer from {judge}; the "
                "sheet has columns for a human checker.",
            ],
            "writes": [mid("tagi.parquet", "token, lemma, class, case, number, gender; whole corpus"),
                       mid("tagi_stanza.parquet", "target corpus, comparison only"),
                       out("ocena_lematyzacji_300.xlsx", "sheets.html"),
                       met("tagowanie_czasy", "tagging"), met("ocena_41", "tagging")],
        },
        {
            "n": 3, "name": "frekwencje", "title": "Count and attach general-Polish frequencies", "modules": "s03_frekwencje.py",
            "reads": [mid("tagi.parquet", src=2), mid("korpus.jsonl", "subject and grade of each material", src=1),
                      ext("KWJP100 frequency lists", "lemmas and forms; used in published lists"),
                      ext("NKJP 1-grams, NKJP 1M lemmas"), ext("wordfreq", "Zipf frequency"),
                      ext("SUBTLEX-PL", "CC BY-NC-SA: comparison metrics only")],
            "does": [
                "For every lemma and every form: occurrences in target and in contrast, number of materials, of contrast "
                "subjects, of estimated grades.",
                "Attach the frequency of the lemma or form in each general-Polish resource.",
                "Measure coverage of the biology vocabulary by each resource, rank correlations between resources, and "
                "how much the choice of resource changes a top-300 keyness list.",
            ],
            "writes": [mid("frekwencje_lemat.parquet"), mid("frekwencje_forma.parquet"), met("frekwencje_43", "frequency")],
        },
        {
            "n": 4, "name": "kandydaci", "title": "Extract and score term candidates",
            "modules": "s04_kandydaci.py · frazy.py · morf.py",
            "reads": [mid("tagi.parquet", src=2), mid("frekwencje_lemat.parquet", src=3),
                      mid("korpus.jsonl", "texts for TermoPL, material metadata", src=1),
                      mid("srebrny_*.csv", "for precision@K", src=1),
                      ext("TermoPL 8.1.1 (Java)", "its input is tagged by Stanza and checked against Morfeusz2")],
            "does": [
                "Single-word candidates: lemmas of content words known to Morfeusz2.",
                f"Multiword candidates: noun phrases of 2–{k['max_dlugosc']} words found by syntactic patterns (agreeing "
                "adjectives, genitive modifiers), rebuilt in the nominative.",
                f"Keep candidates with at least {k['min_frekw_cel']} occurrences in at least {k['min_materialow']} target materials.",
                "Score every candidate with every method: log-likelihood and log ratio against the contrast corpus; "
                "log-likelihood, log ratio and Simple Maths against KWJP100; TF-IDF across subjects; PMI and logDice for "
                "multiword candidates; TermoPL C-value.",
                "Add a rule-based pre-label (T3?, T2?, T1? or undecided) from dispersion and frequency thresholds.",
                "Compare each ranking with the silver standards (precision and recall at K).",
            ],
            "writes": [mid("kandydaci_stat.parquet", "one candidate per row; scores and ranks of all methods"),
                       mid("termopl_terms.tsv"), met("ekstrakcja_42", "extraction")],
        },
        {
            "n": 5, "name": "llm", "title": "Classify candidates with language models", "modules": "s05_llm.py · llm.py",
            "reads": [mid("kandydaci_stat.parquet", src=4), mid("korpus.jsonl", "context sentences; texts for extraction", src=1),
                      ext("Claude API", "Batch API, prompt caching, JSON-schema output")],
            "does": [
                f"Select the top {k['top_do_llm']} candidates of each of six rankings plus the most frequent widely "
                "dispersed words (250 each on a sample run).",
                "Prompt per candidate: the form, its statistics and up to two sentences from the corpus.",
                f"{m1} and {m2} each return a category (T3 subject term, T2 school vocabulary, T1 everyday word, SZUM "
                "noise), a corrected base form, a concept label, imageability, confidence and a one-sentence reason.",
                f"Where the two labels differ or either confidence is low, {judge} decides.",
                f"Separately, {extractor} lists terms directly from a sample of materials (saved; not used by later steps).",
                f"The cost of each batch of requests is estimated before it is sent; the run stops rather than pass the limit of {l['limit_kosztu_usd']} USD.",
            ],
            "writes": [mid("llm_klasyfikacja.parquet", "labels of each model and the final label"),
                       mid("llm_ekstrakcja.jsonl"), mid("llm/", "cached answers, cost ledger"), met("llm_5", "llm")],
        },
        {
            "n": 6, "name": "pule", "title": "Build the pools and the annotation worksheet", "modules": "s06_pule.py",
            "reads": [mid("kandydaci_stat.parquet", src=4), mid("llm_klasyfikacja.parquet", src=5)],
            "does": [
                "Join statistics with labels. The label used is the language-model label; candidates the models did not "
                "see keep the rule-based pre-label.",
                "Where a model returned a different base form, it replaces the extracted one in <code>forma_podstawowa</code>; "
                "the extracted string stays in <code>forma_kandydata</code>.",
                "T3 goes to the subject pool, T1 and T2 to the general pool.",
                "For each subject term pick one unused general item with the same number of words and the closest Zipf frequency.",
                "Group subject terms that share a concept label.",
                f"Draw {cfg['zloty_zbior']['n']} candidates (200 on a sample run) stratified by method, frequency and "
                "length into a worksheet for two human annotators; model labels are left out on purpose.",
            ],
            "writes": [out("kandydaci.csv", "candidates.html"), out("pula_przedmiotowa.csv", "pools.html"),
                       out("pula_ogolna.csv", "pools.html"), out("pojecia.csv", "pools.html"),
                       out("zloty_zbior_do_oznaczenia.xlsx", "sheets.html"), met("pule_6", "pools")],
        },
        {
            "n": 7, "name": "pseudoslowa", "title": "Generate and filter pseudowords", "modules": "s07_pseudoslowa.py · morf.py",
            "reads": [out("pula_ogolna.csv", "pools.html", "templates", src=6), mid("frekwencje_forma.parquet", "corpus lexicon", src=3),
                      ext("Wuggy + Polish plugin"), ext("UniPseudo + WorldLex-Polish"), ext("Imbir (2015) list"),
                      ext("Claude API", f"{m1} as a generator"), ext("Morfeusz2, wordfreq", "for the filters")],
            "does": [
                f"Templates: {p['n_szablonow']} single words from the general pool (80 on a sample run), spread over lengths "
                "and syllable counts.",
                f"Up to {p['kandydatow_na_szablon']} pseudowords per template from each generator (4 on a sample run): Wuggy, "
                "UniPseudo, the language model (keeps the template's ending) and a random draw from the Imbir list.",
                "Reject a pseudoword if it is known to Morfeusz2, occurs in the corpus or in wordfreq, sounds like a real "
                "word, is a productive prefix or suffix on an existing stem, or is one edit away from a real word.",
                "Describe what is kept: length, syllables, consonant runs, diacritics, approximate OLD20, a coarse "
                "Ukrainian/Russian similarity flag.",
                "Compare the distributions of templates and pseudowords.",
            ],
            "writes": [out("pseudoslowa.csv", "pseudowords.html"), out("pseudoslowa_odrzucone.csv", "pseudowords.html"),
                       out("pseudoslowa_rozklady.csv", "pseudowords.html"), met("pseudoslowa_7", "pseudowords")],
        },
        {
            "n": 8, "name": "raport", "title": "Report", "modules": "s08_raport.py · site/*.qmd",
            "reads": [_chip("met", "metryki/*.json", "of steps 1–7", None, "reproduce.html#raw-metrics-files"),
                      _chip("out", "all files in wyniki/", "", None, None), ext("Quarto")],
            "does": [
                "Write the detailed report in Polish from the saved metrics.",
                "Render this site: the pages read the metrics and result files directly, so no number is typed by hand.",
            ],
            "writes": [out("raport.md", "raport-pl.html"), _chip("out", "docs/", "this site", None, "index.html")],
        },
    ]


def _chip_html(c: dict[str, Any]) -> str:
    src = f'<span class="pl-src" title="written by step {c["src"]}">{c["src"]}</span>' if c["src"] else ""
    note = f'<span class="pl-note">{escape(c["note"])}</span>' if c["note"] else ""
    name = f'<span class="pl-name">{escape(c["name"])}</span>'
    if c["href"]:
        name = f'<a href="{c["href"]}">{name}</a>'
    return f'<li class="pl-chip pl-{c["kind"]}">{src}{name}{note}</li>'


def diagram(cfg: dict[str, Any]) -> str:
    rows = []
    for s in steps(cfg):
        does = "".join(f"<li>{d}</li>" for d in s["does"])
        rows.append(f"""
<div class="pl-row">
  <ul class="pl-io pl-reads" aria-label="Step {s['n']} reads">{''.join(_chip_html(c) for c in s['reads'])}</ul>
  <div class="pl-step">
    <div class="pl-step-head"><span class="pl-num">{s['n']}</span><span class="pl-step-name">{s['name']}</span>
      <span class="pl-step-title">{escape(s['title'])}</span></div>
    <ul class="pl-does">{does}</ul>
    <div class="pl-mod">jutro/ {escape(s['modules'])}</div>
  </div>
  <ul class="pl-io pl-writes" aria-label="Step {s['n']} writes">{''.join(_chip_html(c) for c in s['writes'])}</ul>
</div>""")
    legend = """
<ul class="pl-legend" aria-label="Legend">
  <li class="pl-chip pl-ext"><span class="pl-name">external data or tool</span><span class="pl-note">not in the repository</span></li>
  <li class="pl-chip pl-mid"><span class="pl-src">n</span><span class="pl-name">intermediate file</span><span class="pl-note">data/&lt;name&gt;/&lt;run&gt;/, written by step n</span></li>
  <li class="pl-chip pl-out"><span class="pl-name">result file</span><span class="pl-note">wyniki/&lt;name&gt;/&lt;run&gt;/, shown on this site</span></li>
  <li class="pl-chip pl-met"><span class="pl-name">metrics file</span><span class="pl-note">source of the numbers on Results</span></li>
</ul>"""
    head = ('<div class="pl-row pl-colhead" aria-hidden="true"><div>reads</div><div>step: what happens</div>'
            '<div>writes</div></div>')
    return f'<div class="pl">{legend}{head}{"".join(rows)}</div>'
