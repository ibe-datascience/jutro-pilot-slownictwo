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
    def short(m: str) -> str:
        parts = str(m).replace("claude-", "").split("-")  # claude-opus-5-5 → Opus 5.5
        return f"{parts[0].title()} {'.'.join(parts[1:])}".strip()

    m1, m2 = (short(m) for m in l["modele_porownywane"][:2])
    judge, extractor = short(l["model_rozstrzygajacy"]), short(l["model_ekstrakcji"])
    lem_models = " and ".join(short(m) for m in l.get("lematyzacja_modele") or l["modele_porownywane"])
    lem_ref = short(l.get("lematyzacja_referencja") or l["model_rozstrzygajacy"])
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
                f"alone and with Morfeusz2, Morfeusz2 first reading, {lem_models}.",
                f"Reference: the editors' base form where ZPE has one, otherwise a provisional answer from {lem_ref}; the "
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
            "n": 4, "name": "kandydaci", "title": "Extract and score candidates",
            "modules": "s04_kandydaci.py · frazy.py · morf.py",
            "reads": [mid("tagi.parquet", src=2), mid("frekwencje_lemat.parquet", src=3),
                      mid("korpus.jsonl", "texts for TermoPL, material metadata", src=1),
                      mid("srebrny_*.csv", "for precision@K", src=1),
                      ext("TermoPL 8.1.1 (Java)", "its input is tagged by Stanza and checked against Morfeusz2")],
            "does": [
                "Single-word candidates: lemmas of content words known to Morfeusz2; lemmas tagged mostly as proper names are dropped.",
                f"Multiword candidates: noun phrases of 2–{k['max_dlugosc']} words found within a sentence by syntactic patterns "
                "(agreeing adjectives, genitive modifiers), rebuilt in the nominative; phrases built on pronouns, determiners "
                "and instruction words are skipped.",
                f"Subject candidates: at least {k['min_frekw_cel']} occurrences in at least {k['min_materialow']} target materials, "
                f"or at least {k['min_frekw_jeden_material']} in a single one. General candidates: words spread over at least "
                f"{k['ogolne_min_przedmiotow']} other subjects.",
                "Score every candidate with every method, using the true corpus sizes: log-likelihood and log ratio against "
                "the contrast corpus; log-likelihood, log ratio and Simple Maths against KWJP100; TF-IDF across subjects; "
                "PMI and logDice of the weakest adjacent pair for phrases; TermoPL C-value; reciprocal-rank fusion of the rankings.",
                "Compare each ranking with the silver standards (precision and recall at K, against a random baseline) "
                "and count how many silver entries are reachable at all.",
                "Keep up to three real sentences per candidate, from different materials, for the models and the annotators.",
            ],
            "writes": [mid("kandydaci_stat.parquet", "one candidate per row; scores and ranks of all methods"),
                       mid("kandydaci_konteksty.parquet", "sentences"), mid("termopl_terms.tsv"), met("ekstrakcja_42", "extraction")],
        },
        {
            "n": 5, "name": "llm", "title": "Classify candidates with language models", "modules": "s05_llm.py · llm.py",
            "reads": [mid("kandydaci_stat.parquet", src=4), mid("kandydaci_konteksty.parquet", src=4),
                      mid("korpus.jsonl", "texts for direct extraction", src=1),
                      ext("Claude API", "Batch API, prompt caching, JSON-schema output")],
            "does": [
                f"Send all subject candidates (up to {k['top_do_llm']}) and a sample of {k['ogolne_do_llm']} general candidates "
                "stratified by general frequency and number of words.",
                "Prompt per candidate: the form, its counts in biology and in the other subjects, and up to three sentences. "
                "The rule-based pre-label is not shown.",
                f"{m1} and {m2} independently return a category (T3 biology term, T3_INNY term of another subject, T2 school "
                "vocabulary, T1 everyday word, SZUM not usable), the kind of noise, a corrected base form, imageability, "
                "confidence and a one-sentence reason.",
                f"Where the two labels differ or either confidence is low, {judge} labels the candidate too; the majority of "
                "the three decides, and cases without a majority are marked for review.",
                f"{short(l.get('model_pojec', l['model_rozstrzygajacy']))} groups all T3 terms into concepts in a single request.",
                f"Separately, {extractor} lists terms directly from {l['n_materialow_ekstrakcja']} materials, as a check on what step 4 missed.",
                f"The cost of each batch is estimated before it is sent; the run stops rather than pass the limit of "
                f"{l['limit_kosztu_usd']} USD. An interrupted batch is collected on the next run, not sent again.",
            ],
            "writes": [mid("llm_klasyfikacja.parquet", "labels of each model and the final label"),
                       mid("llm_pojecia.json", "concept groups"), mid("llm_ekstrakcja.jsonl"),
                       out("terminy_llm_spoza_kandydatow.csv", "pools.html"),
                       mid("llm/", "cached answers, cost ledger"), met("llm_5", "llm")],
        },
        {
            "n": 6, "name": "pule", "title": "Build the pools and the annotation worksheet", "modules": "s06_pule.py",
            "reads": [mid("kandydaci_stat.parquet", src=4), mid("llm_klasyfikacja.parquet", src=5),
                      mid("llm_pojecia.json", src=5), mid("kandydaci_konteksty.parquet", src=4)],
            "does": [
                "Join statistics with the final labels. Only labelled candidates enter the pools: T3 the subject pool, "
                "T1 and T2 the general pool.",
                "A corrected base form replaces the extracted one in <code>forma_podstawowa</code> if it keeps the number of "
                "words; if two rows then name the same item, the more frequent one is kept.",
                "Match each subject term to one general item of the same part of speech and number of words, closest in Zipf "
                "frequency and length in letters: optimal assignment without reuse, within calipers.",
                "Report balance of frequency and length before and after matching.",
                "Attach the concept of each subject term.",
                f"Draw {cfg['zloty_zbior']['n']} candidates stratified by final label and by whether the case was adjudicated "
                "into a worksheet for two human annotators, with sentences and without model labels; keep the key and the "
                "sampling weights aside. If a filled-in worksheet is present, score the labels against it.",
            ],
            "writes": [out("kandydaci.csv", "candidates.html"), out("pula_przedmiotowa.csv", "pools.html"),
                       out("pula_ogolna.csv", "pools.html"), out("pojecia.csv", "pools.html"),
                       out("zloty_zbior_do_oznaczenia.xlsx", "sheets.html"), mid("zloty_zbior_klucz.csv", "labels and weights"),
                       met("pule_6", "pools")],
        },
        {
            "n": 7, "name": "pseudoslowa", "title": "Generate, filter and rate pseudowords",
            "modules": "s07_pseudoslowa.py · pseudo.py · morf.py",
            "reads": [out("pula_ogolna.csv", "pools.html", "templates", src=6), out("pula_przedmiotowa.csv", "pools.html", "templates", src=6),
                      mid("frekwencje_forma.parquet", "forms of the corpus", src=3),
                      ext("KWJP100 lemma and form lists", "reference lexicon"), ext("Wuggy + Polish plugin"),
                      ext("UniPseudo + WorldLex-Polish"), ext("Imbir et al. (2015) list"),
                      ext("Claude API", f"{short(l.get('model_pseudoslow', ''))} generates, {short(l.get('model_oceny_pseudoslow', ''))} rates"),
                      ext("Morfeusz2, wordfreq", "existing words; Ukrainian and Russian word lists")],
            "does": [
                f"Templates: {p['n_szablonow']} real nouns and verbs in base form, {int(100 * p.get('udzial_przedmiotowych', 0))}% "
                "from the subject pool and the rest from the general pool.",
                f"Up to {p['kandydatow_na_szablon']} candidates per template from each generator: Wuggy keeping the template's "
                "ending, Wuggy with a free ending, UniPseudo, a language model, and the Imbir list.",
                "Reference lexicon: KWJP100 lemmas known to Morfeusz2, with counts of letter trigrams, onsets, codas and clusters.",
                "Hard filters, each rejection with its reason: existing word; length, syllables or ending unlike the template; "
                "rare letter pattern; one edit from a frequent word; homophone of a word; existing stem with an affix or a "
                "compound; vulgar association; Ukrainian or Russian word in Polish spelling.",
                "Measure what passes: OLD20 and neighbours over the whole lexicon, bigram probability, the same for the templates.",
                f"The model rates up to {p.get('ocenianych_na_szablon', 6)} per template for pronounceability, associations and "
                f"foreign or inappropriate readings; the best {p.get('wybrane_na_szablon', 2)} rated positively are recommended.",
                "Compare the distributions of templates and pseudowords (standardised differences).",
            ],
            "writes": [out("pseudoslowa.csv", "pseudowords.html"), out("pseudoslowa_odrzucone.csv", "pseudowords.html"),
                       out("pseudoslowa_szablony.csv", "pseudowords.html"), out("pseudoslowa_rozklady.csv", "pseudowords.html"),
                       met("pseudoslowa_7", "pseudowords")],
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
