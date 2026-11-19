"""Build manifest.json and the "Files" table of README_pseudo.md from the files on disk.

Sizes and sha256 are computed here; every other value (URLs, commits, licences, statuses) is what was
verified on 2026-11-13 and is documented in README_pseudo.md. Re-run after adding or changing files:

    python build_manifest.py
"""
import hashlib
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATE = "2026-11-13"

VENV = "/Users/michalpalinski/kompetencje_jezykowe/.venv"
ACT = f". {VENV}/bin/activate"
BASE = "/Users/michalpalinski/kompetencje_jezykowe/resources/pseudo"

CC_BY = "https://creativecommons.org/licenses/by/4.0/"
CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/"
OL_LICENCE = "https://github.com/chrplr/openlexicon/blob/master/LICENSE.txt"
PLUGIN_COMMIT = "2968223983626c4a178cda7ea071c082dcaba3fb"
OL_MASTER = "9009f488f664536940965453c127f43cf18b84a4"
OL_DJANGO = "5d6f5188db995a0c8052b7438137c61e49b99538"
GIN = "https://gin.g-node.org/SocGramLab/pseudo-word-stimuli-with-arbitrary-constrains"
WUGGY_RUN = f"{ACT} && cd {BASE}/wuggy_plugins && PYTHONDONTWRITEBYTECODE=1 python smoke_test_polish.py"
UNI_R_RUN = f"cd {BASE}/unipseudo && Rscript run_unipseudo_local.R 20 6 1 out.csv"
UNI_PY_RUN = f"{ACT} && cd {BASE}/unipseudo && python run_unipseudo_python_port.py 20 6 1 none"
NO_LICENCE_PLUGIN = ("No licence stated: repository WuggyCode/wuggy_language_plugin_data has no licence file "
                     "(GitHub API license=null, /license -> 404) and the file has no licence header. FLAGGED.")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entry(resource, path, url, version, licence, licence_url, polish, runnable, how, notes, status,
          kind="downloaded", is_dir=False):
    full = os.path.join(HERE, path) if path else None
    e = {
        "resource": resource,
        "path": path,
        "kind": kind,
        "url": url,
        "download_date": DATE if kind in ("downloaded", "evidence") else None,
        "version_or_commit": version,
        "size_bytes": None,
        "sha256": None,
        "licence": licence,
        "licence_url": licence_url,
        "supports_polish": polish,
        "runnable_locally": runnable,
        "how_to_run": how,
        "notes": notes,
        "status": status,
    }
    if full and os.path.isfile(full):
        e["size_bytes"] = os.path.getsize(full)
        e["sha256"] = sha256(full)
    elif full and is_dir and os.path.isdir(full):
        out = subprocess.run(["du", "-sk", full], capture_output=True, text=True).stdout.split()[0]
        e["size_bytes"] = int(out) * 1024
        e["notes"] += " size_bytes is disk usage of the directory (du -sk); sha256 not applicable, see version_or_commit."
    return e


M = []

# ---------------------------------------------------------------- 1. Wuggy
M.append(entry(
    "Wuggy Python package (already installed in the venv; not downloaded in this task)",
    None, "https://pypi.org/project/Wuggy/1.1.2/", "1.1.2 (PyPI wheel uploaded 2024-02-20)",
    "MIT", "https://github.com/WuggyCode/wuggy/blob/master/LICENSE", True, True, WUGGY_RUN,
    f"Installed at {VENV}/lib/python3.12/site-packages/wuggy. Official plugin list includes orthographic_polish. "
    "PyPI lists wheel sha256 446c6841d4762e9ab8aa7f45ba58b2608f2fe235dcead79c7c96a1c3c073ba57 (not re-checked against "
    "the installed files). GitHub master 25de4ac1a608913bcdd633f312f3ac7dd2fead4a is version 1.2.0, not on PyPI. "
    "Built-in plugin download fails on this machine with an SSL certificate error unless SSL_CERT_FILE points to "
    "certifi's bundle. Output is random unless random.seed() is called before generating.",
    "ready", kind="preinstalled"))
M.append(entry(
    "Wuggy official Polish plugin: lexicon", "wuggy_plugins/orthographic_polish/orthographic_polish.txt",
    f"https://raw.githubusercontent.com/WuggyCode/wuggy_language_plugin_data/{PLUGIN_COMMIT}/orthographic_polish/orthographic_polish.txt",
    f"repo commit {PLUGIN_COMMIT} (file last changed in 43258ad8a900dc26dcdb18d16d371479b7fa1d0d, 2020-12-14)",
    None, None, True, True, WUGGY_RUN,
    NO_LICENCE_PLUGIN + " 834,141 entries; columns: word, hyphen-syllabified word, relative frequency (sums to 1.0). "
    "Source corpus not documented (NOT VERIFIED). Byte-identical to what WuggyGenerator.download_language_plugin fetches.",
    "licence_unclear"))
M.append(entry(
    "Wuggy official Polish plugin: plugin class", "wuggy_plugins/orthographic_polish/orthographic_polish.py",
    f"https://raw.githubusercontent.com/WuggyCode/wuggy_language_plugin_data/{PLUGIN_COMMIT}/orthographic_polish/orthographic_polish.py",
    f"repo commit {PLUGIN_COMMIT} (file last changed in 43258ad8a900dc26dcdb18d16d371479b7fa1d0d, 2020-12-14)",
    None, None, True, True, WUGGY_RUN,
    NO_LICENCE_PLUGIN + " Class OfficialLanguagePlugin(BaseLanguagePlugin); header names Paweł Mandera as author. "
    "The nucleus regex lacks 'ó' (36,607 lexicon entries have a syllable it cannot segment).",
    "licence_unclear"))
M.append(entry(
    "Wuggy: helper to load the plugin from this directory", "wuggy_plugins/load_local_plugin.py", None, None,
    None, None, True, True, "from load_local_plugin import load_generator; g = load_generator('orthographic_polish')",
    "Written for this task. Executes the unmodified official plugin file under its official module name and passes "
    "an instance to WuggyGenerator.load(name, local_language_plugin=...).", "ready", kind="local_script"))
M.append(entry(
    "Wuggy: smoke test script", "wuggy_plugins/smoke_test_polish.py", None, None, None, None, True, True, WUGGY_RUN,
    "Written for this task. 5 pseudowords each for komora, wynik, porównać; seeded with random.seed(20261113).",
    "ready", kind="local_script"))
for f in ("smoke_test_polish_output.log", "smoke_test_polish_output.json"):
    M.append(entry("Wuggy: smoke test output", f"wuggy_plugins/{f}", None, None, None, None, True, True, WUGGY_RUN,
                   "Output of smoke_test_polish.py on 2026-11-13.", "ready", kind="output"))

# ---------------------------------------------------------------- 2. Dołżycka et al. 2022
GIN_COMMIT = "0ad42127df1809beca3b0517a83b6bf7ec456ac2"
DOL_LICENCE_NOTE = (
    "No LICENSE/COPYING in the GIN tree (FLAGGED). Journal article doi:10.1007/s10936-022-09884-6 is CC BY 4.0; "
    "this does not automatically licence the SOM repository."
)
M.append(entry(
    "Dołżycka et al. (2022): GIN repository clone (Org notebooks + xlsx)",
    "dolzycka2022/repo", GIN + ".git", f"branch master, commit {GIN_COMMIT} (2022-10-17)",
    None, None, True, False,
    None,
    "Cloned 2026-11-13 after gin.g-node.org recovered from a morning HTTP 503 outage. Contains README.org, "
    "pwords_proc_pGenerate_001..004.org (IPython literate notebooks) and four xlsx stimulus/rating files. "
    "Generation pipeline is NOT runnable as published: private modules init.imports / init.load / aux_nlp.aux_nlp "
    "and input corpora are missing from the repo; Wuggy is driven as the classic desktop program (TSV export then "
    "import of columns WORD/MATCH/LEXICALITY/OLD20/NED1/MAXDEVIATION/...), not via Python package wuggy 1.1.2. "
    + DOL_LICENCE_NOTE + " Nested .git — avoid git-adding into the parent repo blindly.",
    "licence_unclear", kind="downloaded", is_dir=True))
for fname, note in (
    (".gitattributes", "DataLad/git-annex attributes from the upstream GIN dataset."),
    ("README.org", "Authors' README: Org files = generation/selection code; spreadsheets = pseudo-nouns/verbs + ratings."),
    ("pwords_proc_pGenerate_001_main.org", "Main generation/selection notebook (includes Wuggy TSV export/import stages)."),
    ("pwords_proc_pGenerate_002_syllabes_freq_1st.org", "Syllable-frequency follow-up notebook."),
    ("pwords_proc_pGenerate_003_word_vals.org", "Word-values / rating notebook (mentions savReaderWriter/SPSS)."),
    ("pwords_proc_pGenerate_004_generate_gforms.org", "Google Forms generation notebook."),
    ("SOM_study_1_dataset_JLSP_FINAL_001.xlsx", "Study 1 SOM: ALL_* pools + CHOSEN_NOUNS_VERBS (158) + 80_CHOSEN_*."),
    ("SOM_study_2_dataset_JLSP_FINAL_001.xlsx", "Study 2 SOM: NOUNS/VERBS data + CHOSEN_PAIRS (120) + 40_noun-verb_PAIRS."),
    ("supplementary_material_study_1.xlsx", "Study 1 supplementary (overlap with SOM_1 chosen lists)."),
    ("supplementary_material_study_2.xlsx", "Study 2 supplementary (overlap with SOM_2 chosen pairs)."),
):
    M.append(entry(
        f"Dołżycka et al. (2022): {fname}", f"dolzycka2022/repo/{fname}",
        f"{GIN}/raw/master/{fname}", GIN_COMMIT, None, None, True,
        False if fname.endswith(".org") else True,
        None if fname.endswith(".org") else f"open or convert; CSV extracts in dolzycka2022/lists/",
        note + " " + DOL_LICENCE_NOTE,
        "licence_unclear" if fname.endswith(".org") else "licence_unclear"))
for csv_name, note in (
    ("study1_chosen_nouns_verbs_158.csv", "Derived from SOM_study_1 CHOSEN_NOUNS_VERBS (158 rows)."),
    ("study1_80_chosen_nouns_verbs.csv", "Derived from SOM_study_1 80_CHOSEN_NOUNS_VERBS."),
    ("study1_all_nouns_320.csv", "Derived from SOM_study_1 ALL_NOUNS_data (320 rows)."),
    ("study1_all_verbs_320.csv", "Derived from SOM_study_1 ALL_VERBS_data (320 rows)."),
    ("study2_chosen_pairs_120.csv", "Derived from SOM_study_2 CHOSEN_PAIRS_data (120 rows)."),
    ("study2_40_noun_verb_pairs.csv", "Derived from SOM_study_2 40_noun-verb_PAIRS (39 non-empty rows)."),
):
    M.append(entry(
        f"Dołżycka et al. (2022): UTF-8 CSV extract {csv_name}", f"dolzycka2022/lists/{csv_name}",
        None, f"derived 2026-11-13 from repo @{GIN_COMMIT}", None, None, True, True, None,
        note + " Written for this task from the authors' xlsx; upstream licence still unclear (FLAGGED).",
        "licence_unclear", kind="derived"))
M.append(entry(
    "Dołżycka et al. (2022): preprint PDF (PsyArXiv 9xefc)", "dolzycka2022/DolzyckaEtAl2022a_preprint_psyarxiv_9xefc.pdf",
    "https://osf.io/download/bupqt/", "preprint 9xefc_v1, file dated 2022-05-25", "CC BY 4.0",
    "https://creativecommons.org/licenses/by/4.0/legalcode", True, False, None,
    "Document only (39 pages); contains no code and no stimulus lists. sha256 equals the hash reported by the OSF API. "
    "Licence as reported by the OSF API for the preprint ('CC-By Attribution 4.0 International').",
    "downloaded_not_run"))
M.append(entry(
    "Dołżycka et al. (2022): Internet Archive snapshot of the GIN repository page",
    "dolzycka2022/wayback_20250805170039_gin_repo_page.html",
    "https://web.archive.org/web/20250805170039id_/" + GIN, "snapshot 2025-08-05 17:00:39", None, None,
    "unknown", False, None,
    "Evidence recorded while GIN was down (file list, 4 commits, README text). The archive holds no file contents. "
    "Superseded for content by dolzycka2022/repo.", "downloaded_not_run", kind="evidence"))
M.append(entry(
    "Dołżycka et al. (2022): log of failed attempts to reach gin.g-node.org", "dolzycka2022/gin_http503_poll_log.txt",
    None, None, None, None, "unknown", False, None,
    "Written for this task: 40 polls between 11:39 and 12:08 UTC on 2026-11-13, all HTTP 503, plus a final probe. "
    "GIN recovered later the same day; clone succeeded.",
    "downloaded_not_run", kind="evidence"))
M.append(entry(
    "NOT the authors' code: illustration of last-syllable-preserving generation with Wuggy 1.1.2",
    "dolzycka2022/approach_demo_NOT_AUTHORS_CODE.py", None, None, None, None, True, True,
    f"{ACT} && cd {BASE}/dolzycka2022 && PYTHONDONTWRITEBYTECODE=1 python approach_demo_NOT_AUTHORS_CODE.py komora wynik porównać",
    "Written for this task. Uses WuggyGenerator.generate_advanced() plus a regex on the template's last syllable. "
    "Does not reproduce the paper's desktop-Wuggy pipeline. Worked for komora and wynik; 0 candidates for "
    "porównać in 30 s.", "ready", kind="local_script"))
M.append(entry(
    "NOT the authors' code: output of the illustration", "dolzycka2022/approach_demo_NOT_AUTHORS_CODE.log",
    None, None, None, None, True, True, None, "Output on 2026-11-13.", "ready", kind="output"))

# ---------------------------------------------------------------- 3. UniPseudo
M.append(entry(
    "UniPseudo: original R Shiny source (sparse clone of chrplr/openlexicon)", "unipseudo/openlexicon",
    "https://github.com/chrplr/openlexicon", f"branch master, commit {OL_MASTER}", "CC BY-SA 4.0", OL_LICENCE,
    True, True, UNI_R_RUN,
    "Sparse, depth-1, blob-filtered clone: apps/unipseudo, datasets-info/_json, datasets-info/links, "
    "datasets-info/WorldLex, packages/openlexicon.fetcher (GPL >= 3 per its DESCRIPTION), "
    "scripts/pseudoword-generation-by-markov-on-trigrams, plus top-level files. Repository README: CC BY-SA 4.0 unless "
    "a directory says otherwise; apps/unipseudo has no own licence file. Share-alike licence applied to code. "
    "Run through unipseudo/run_unipseudo_local.R (no web UI).", "ready", is_dir=True))
M.append(entry(
    "UniPseudo: WorldLex-Polish frequency table (lexicon UniPseudo uses for Polish)", "unipseudo/data/WorldLex-Polish.rds",
    "http://www.lexique.org/databases/WorldLex/WorldLex-Polish.rds", "md5 dd9ee3a0268dcd61776b1e1694a1d78f (matches datasets-info/_json/WorldLex-Polish.json)",
    None, None, True, True, UNI_R_RUN,
    "No licence stated on http://worldlex.lexique.org (citation request only: Gimenes & New 2016, "
    "doi:10.3758/s13428-015-0621-0) nor in datasets-info/WorldLex/README-Worldlex.md, which says the source corpora are "
    "from HC Corpora and quotes a 'Fair Use' belief. File is hosted outside the repository. FLAGGED. "
    "545,699 rows, 14 columns (Word, nbcar, Blog/Twitter/News Freq, FreqPm, CD, CDPc).", "licence_unclear"))
for f, n in (("worldlex_polish_len6_models_BlogFreqPm_gt0.5.txt", "9,770 six-letter words with BlogFreqPm > 0.5, lower-cased (source words)"),
             ("worldlex_polish_len6_all.txt", "31,157 six-letter entries (exclusion list)")):
    M.append(entry("UniPseudo: word list exported from WorldLex-Polish.rds", f"unipseudo/data/{f}", None,
                   "derived from unipseudo/data/WorldLex-Polish.rds", None, None, True, True, UNI_PY_RUN,
                   f"Derived file: {n}. Same unclear licence as WorldLex-Polish.rds. FLAGGED.", "licence_unclear", kind="derived"))
M.append(entry(
    "UniPseudo: headless R runner", "unipseudo/run_unipseudo_local.R", None, None, None, None, True, True, UNI_R_RUN,
    "Written for this task. Sources the unmodified repository R files, neutralises shinyjs::html/shinyalert in memory, "
    "replicates the app's Polish settings (WorldLex-Polish, BlogFreqPm > 0.5, trigram for length >= 6, presets max 3 "
    "consonants / max 2 same letters; UNIPSEUDO_CONSTRAINTS=none switches presets off). Needs only the installed shiny "
    "package. Derived from CC BY-SA 4.0 code.", "ready", kind="local_script"))
for f in ("smoke_test_polish_len6.csv", "smoke_test_polish_len6.log"):
    M.append(entry("UniPseudo: R smoke test output (20 Polish pseudowords, length 6, seed 1)", f"unipseudo/{f}", None, None,
                   None, None, True, True, f"cd {BASE}/unipseudo && Rscript run_unipseudo_local.R 20 6 1 smoke_test_polish_len6.csv",
                   "Output on 2026-11-13.", "ready", kind="output"))
for f in ("generator.py", "filters.py", "conf.py", "services.py", "views.py", "urls.py", "apps.py", "tests.py", "__init__.py"):
    used = f in ("generator.py", "filters.py")
    M.append(entry(
        "UniPseudo: Python (Django) port from branch django_dev", f"unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/{f}",
        f"https://raw.githubusercontent.com/chrplr/openlexicon/{OL_DJANGO}/openlexicon.org/unipseudo/{f}",
        f"branch django_dev, commit {OL_DJANGO} (2026-10-20)", "CC BY-SA 4.0", OL_LICENCE, True,
        True if used else False, UNI_PY_RUN if used else None,
        ("Django-free module, used by run_unipseudo_python_port.py." if used else
         "Kept for reference; needs the Django project, not run.") +
        " Licence: repository-level LICENSE.txt (also present on this branch). That the live site "
        "https://www.lexique.org/django/unipseudo/ runs this commit is NOT VERIFIED.",
        "ready" if used else "downloaded_not_run"))
M.append(entry(
    "UniPseudo: runner for the Python port", "unipseudo/run_unipseudo_python_port.py", None, None, None, None, True, True,
    UNI_PY_RUN, "Written for this task. Loads generator.py/filters.py by path; no Django required.", "ready", kind="local_script"))
M.append(entry(
    "UniPseudo: Python port smoke test output (20 Polish pseudowords, length 6, seed 1)", "unipseudo/smoke_test_python_port_len6.log",
    None, None, None, None, True, True, UNI_PY_RUN, "Output on 2026-11-13.", "ready", kind="output"))

# ---------------------------------------------------------------- 4. Imbir et al. 2015
M.append(entry(
    "Polish Pseudo-words List (Imbir, Spustek & Żygierewicz 2015): original xlsx",
    "imbir2015/Polish_pseudo-words_List_dataset.xlsx",
    "https://ndownloader.figshare.com/files/2099389?private_link=1089daa40de311e589a806ec4b8d1f61",
    "figshare file 2099389; item page https://figshare.com/s/1089daa40de311e589a806ec4b8d1f61 (modified 2015-12-03)",
    "CC BY 4.0", CC_BY, True, True, "static dataset: read imbir2015/Polish_pseudo-words_List_dataset.csv",
    "Link given in the article (doi:10.3389/fpsyg.2015.01395, itself CC BY). Licence 'CC BY 4.0' read from the figshare "
    "item page, which is behind a JavaScript challenge for curl and was opened once in a browser. Sheet PPwL, 3,024 rows "
    "x 4 columns.", "ready"))
M.append(entry(
    "Polish Pseudo-words List: UTF-8 CSV conversion", "imbir2015/Polish_pseudo-words_List_dataset.csv", None,
    "derived from the xlsx with imbir2015/convert_to_csv.py", "CC BY 4.0", CC_BY, True, True,
    "static dataset: pandas.read_csv('imbir2015/Polish_pseudo-words_List_dataset.csv')",
    "3,023 rows + header; columns: 'pseudo-word', 'Judge competent congruency index ' (trailing space), "
    "'No. of judges indicating that this is good example of pseudo-word', 'Length: Number of letters'. Values unchanged.",
    "ready", kind="derived"))
M.append(entry(
    "Polish Pseudo-words List: conversion script", "imbir2015/convert_to_csv.py", None, None, None, None, True, True,
    f"{ACT} && cd {BASE}/imbir2015 && python convert_to_csv.py", "Written for this task (openpyxl).", "ready", kind="local_script"))

# ---------------------------------------------------------------- completeness check
listed = {e["path"] for e in M if e["path"]}
missing = []
for root, dirs, files in os.walk(HERE):
    rel_root = os.path.relpath(root, HERE)
    # Skip nested clones' internals (already covered as directory entries / listed files).
    skip_prefixes = (
        os.path.join("unipseudo", "openlexicon"),
        os.path.join("dolzycka2022", "repo", ".git"),
        os.path.join("dolzycka2022", "repo", ".datalad"),
    )
    if any(rel_root == p or rel_root.startswith(p + os.sep) for p in skip_prefixes):
        dirs[:] = []
        continue
    if rel_root == os.path.join("dolzycka2022", "repo"):
        # Individual tracked files are listed explicitly; ignore any unexpected cruft.
        dirs[:] = [d for d in dirs if d not in (".git", ".datalad")]
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".datalad")]
    for f in files:
        rel = os.path.normpath(os.path.join(rel_root, f))
        if rel in ("README_pseudo.md", "manifest.json", "build_manifest.py", ".DS_Store"):
            continue
        if rel.startswith(os.path.join("dolzycka2022", "repo") + os.sep) and rel in listed:
            continue
        if rel not in listed:
            missing.append(rel)
not_on_disk = [p for p in listed if not os.path.exists(os.path.join(HERE, p))]
print("files on disk but not in manifest:", missing)
print("manifest paths not on disk:", not_on_disk)

with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(M, fh, ensure_ascii=False, indent=2)
print("manifest entries:", len(M))

# ---------------------------------------------------------------- README table
rows = ["| Path | Kind | Size (bytes) | sha256 or commit | Licence | Status |", "|---|---|---|---|---|---|"]
for e in M:
    ident = e["sha256"] or (e["version_or_commit"] or "")
    lic = e["licence"] or ("none stated (flagged)" if e["status"] == "licence_unclear" else
                           ("unclear (flagged)" if e["status"] == "unavailable" else "n/a (written here)" if e["kind"] in ("local_script", "output") else "not recorded"))
    path = f"`{e['path']}`" if e["path"] else f"({e['resource']})"
    rows.append(f"| {path} | {e['kind']} | {e['size_bytes'] if e['size_bytes'] is not None else ''} | `{ident}` | {lic} | {e['status']} |")
table = ("Download date for all downloaded files: 2026-11-13. Source URLs, run commands and notes per file are in "
         "`manifest.json` (regenerate both with `python build_manifest.py`).\n\n" + "\n".join(rows))
readme = os.path.join(HERE, "README_pseudo.md")
s = open(readme, encoding="utf-8").read()
start, end = "<!--FILES_TABLE_START-->", "<!--FILES_TABLE_END-->"
if "<!--FILES_TABLE-->" in s:
    s = s.replace("<!--FILES_TABLE-->", f"{start}\n{table}\n{end}")
else:
    a, b = s.index(start), s.index(end)
    s = s[:a] + f"{start}\n{table}\n" + s[b:]
open(readme, "w", encoding="utf-8").write(s)
print("README table rows:", len(rows) - 2)
