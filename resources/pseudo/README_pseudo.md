# Pseudoword resources for the Polish LexTALE-style pilot

Checked and downloaded on **2026-11-13** (machine: macOS arm64, Python 3.12.2 venv at `../../.venv`, R 4.4.1).
Everything below was verified by fetching or running it on that date; anything that could not be verified is
marked **NOT VERIFIED**. Machine-readable version: `manifest.json` (hashes, sizes, licences, status per file).

Total size of this directory: about 54 MB. No system packages and no R packages were installed
(`Rlib/` was not needed and was not created). Nothing was written into the venv.

| # | Resource | Status | Polish | Runs locally | Licence |
|---|----------|--------|--------|--------------|---------|
| 1 | Wuggy 1.1.2 + official `orthographic_polish` plugin | works (smoke test passed) | yes | yes | package MIT; **plugin data: no licence stated (flagged)** |
| 2 | Dołżycka, Nikadon & Formanowicz (2022) scripts + pseudoword lists | **obtained** (GIN clone after outage); lists usable; pipeline **not runnable** as published | yes | lists: yes; generation: no | paper CC BY 4.0; **repository: no LICENSE file (flagged)** |
| 3 | UniPseudo (R Shiny source + Python port) with WorldLex-Polish | works (smoke tests passed) | yes | yes (`Rscript`, also pure Python) | code CC BY-SA 4.0; **WorldLex-Polish data: no licence stated (flagged)** |
| 4 | Polish Pseudo-words List (Imbir, Spustek & Żygierewicz 2015) | downloaded, converted to CSV | yes | n/a (static list) | CC BY 4.0 |

---

## 1. Wuggy (Python package) and the official Polish plugin

### What exists

- Installed package: `wuggy` 1.1.2 (PyPI project `Wuggy`, wheel uploaded 2024-02-20, the newest release on PyPI;
  <https://pypi.org/project/Wuggy/>). Source: <https://github.com/WuggyCode/wuggy>. Licence **MIT**
  (`wuggy-1.1.2.dist-info/LICENSE`, "Copyright (c) 2020 Emmanuel Keuleers"; GitHub API reports `MIT`;
  <https://github.com/WuggyCode/wuggy/blob/master/LICENSE>).
  GitHub `master` (commit `25de4ac1a608913bcdd633f312f3ac7dd2fead4a`, 2026-04-17) is at version 1.2.0 in `setup.py`
  and is not on PyPI; it adds `orthographic_lithuanian` and a GUI-related plugin path.
- **An official Polish plugin exists: `orthographic_polish`.** The official names hard-coded in 1.1.2
  (`WuggyGenerator().supported_official_language_plugin_names`) are:
  `orthographic_basque, orthographic_dutch, orthographic_english, orthographic_french, orthographic_german,
  orthographic_italian, orthographic_polish, orthographic_serbian_cyrillic, orthographic_serbian_latin,
  orthographic_spanish, orthographic_vietnamese, orthographic_estonian, phonetic_english_celex,
  phonetic_english_cmu, phonetic_french, phonetic_italian`.
- Plugin data repository: <https://github.com/WuggyCode/wuggy_language_plugin_data> (branch `master`, commit
  `2968223983626c4a178cda7ea071c082dcaba3fb`, 2026-04-16). The `orthographic_polish/` folder was last changed
  in the initial commit `43258ad8a900dc26dcdb18d16d371479b7fa1d0d` (2020-12-14).

### How plugins are downloaded and stored (read from `wuggy/generators/wuggygenerator.py`, 1.1.2)

- `WuggyGenerator.load(name)` looks for `<site-packages>/wuggy/plugins/language_data/<name>/`; if the folder is
  missing it calls `download_language_plugin(name)`, which asks for `y/n` on stdin unless called with
  `auto_download=True`.
- The download fetches exactly two files with `urllib.request.urlopen` from
  `https://raw.githubusercontent.com/WuggyCode/wuggy_language_plugin_data/master/<name>/<name>.py` and
  `.../<name>/<name>.txt` and writes them into that `language_data/<name>/` folder inside site-packages.
- `WuggyGenerator.remove_downloaded_language_plugins()` deletes the whole `language_data` folder.
- **Problem on this machine:** the venv's Python has no CA bundle configured, so the built-in download fails with
  `ssl.SSLCertVerificationError: certificate verify failed: unable to get local issuer certificate`. It works
  when `SSL_CERT_FILE` points at certifi's bundle (tested, see below). A failed download leaves an empty
  `language_data/orthographic_polish/` folder behind, and because `load()` only checks that the folder exists,
  it must be deleted before retrying.

### Plugin file format and API

A plugin is a folder with two files:

1. `<name>.py` defining a subclass of `wuggy.plugins.baselanguageplugin.BaseLanguagePlugin`
   (official plugins must name the class `OfficialLanguagePlugin`). Required members:
   `default_data`, `default_neighbor_lexicon`, `default_word_lexicon`, `default_lookup_lexicon` (file names,
   resolved relative to the folder of the `.py` file) and `transform(self, input_sequence, frequency=1)`.
   The Polish plugin implements `transform` as `self.pre_transform(input_sequence, frequency=frequency, language=self)`
   and supplies `oncpattern`, a regex with three groups (onset, nucleus, coda) applied to each syllable.
   Inherited from the base class: output modes `plain`, `syllabic`, `segmental`, `pass`; statistics
   `lexicality`, `ned1`, `old20`, `overlap`, `overlap_ratio`, `plain_length`, `transition_frequencies`.
2. `<name>.txt`, UTF-8, one entry per line, three tab-separated columns:
   `word <TAB> word-syl-la-bi-fied (hyphens between syllables) <TAB> frequency`.
   The same file serves as bigram-chain training data, lookup lexicon (word to syllabification), word lexicon
   (lexicality check) and neighbour lexicon (OLD20, ned1). For the lexicons Wuggy reads the last column as a
   float and keeps entries with frequency >= 0. For the bigram chain, `BigramChain.load` in 1.1.2 sets
   `frequency = 1` for every line, so each entry counts once (type counts); the frequency column does not
   weight the transition frequencies.
   The Wuggy documentation calls the third column "occurrence per million words"; in the Polish file the
   values are proportions that sum to 1.000000.

To use a custom or modified plugin: `g.load("any_name", local_language_plugin=MyPlugin())`. The data folder is
the folder containing the class's `.py` file. The official docs
(`documentation/baselanguageplugin/baselanguageplugin.md` in the Wuggy repo) say to copy the official `.py`/`.txt`
and replace `from ...baselanguageplugin import BaseLanguagePlugin` with `from wuggy import BaseLanguagePlugin`.
`wuggy_plugins/load_local_plugin.py` here achieves the same without editing the official file.

### The Polish plugin (`wuggy_plugins/orthographic_polish/`)

- `orthographic_polish.py` (1,017 bytes): header comment "Subsyllabic Polish, by Paweł Mandera,
  pawel.mandera@ugent.be". Nucleus pattern: `ia|ie|io|iu|ą|ę|a|e|i|o|u|y`.
- `orthographic_polish.txt` (39,841,583 bytes): **834,141 entries**, all lower-case, no duplicate words, every
  line has 3 columns. Frequencies range from 9.828e-09 to 0.0283 (`nie`) and sum to 1.000000.
- **Source corpus: NOT documented** in the plugin, the plugin repository (no README) or the Wuggy docs, so it
  is NOT VERIFIED. Observations only: the author is the first author of SUBTLEX-PL (Mandera et al. 2015,
  doi:10.3758/s13428-014-0489-4); the lexicon has more types than the 449,300 reported for SUBTLEX-PL, and its
  frequency values are not integer multiples of the smallest value, so it is not a plain count list from one
  corpus. Ask the maintainers before citing a source.
- **Licence of the plugin data: none stated.** The repository has no licence file (GitHub API `license: null`,
  `/license` endpoint returns 404) and the files carry no licence header. The MIT licence of the `wuggy`
  package is in a different repository and does not mention the language data. **Flagged as unclear.**
- **Quirk:** `ó` is missing from the nucleus pattern. For 36,607 of 834,141 entries (4.4%) at least one
  syllable does not match the onset-nucleus-coda regex, and Wuggy then treats the whole syllable as an "onset"
  segment (e.g. `po-ró-wnać` becomes segments `p|o||ró|||wn|a|ć`). Templates containing `ó` therefore get a much
  narrower and odder candidate set (see `porównać` below).
- The lexicon is large and contains rare forms; `lexicality == "N"` only means "not in this file". Candidates
  should still be screened against a dictionary before use as LexTALE nonwords.

### Exact calls that worked

Loading the plugin from this directory (nothing written to the venv), from `wuggy_plugins/`:

```python
from load_local_plugin import load_generator      # helper in this folder
import random
g = load_generator("orthographic_polish")         # about 10.5 s
random.seed(20261113)                             # see "Reproducibility"
matches = g.generate_classic(["komora"], ncandidates_per_sequence=5, max_search_time_per_sequence=30)
# each match: {"word", "segments", "pseudoword", "statistics": {...}, "difference_statistics": {...}}
```

`load_generator` is equivalent to:

```python
import importlib.util, sys
from wuggy import WuggyGenerator
name = "orthographic_polish"
mod_name = f"wuggy.plugins.language_data.{name}.{name}"
spec = importlib.util.spec_from_file_location(mod_name, f"wuggy_plugins/{name}/{name}.py")
mod = importlib.util.module_from_spec(spec); sys.modules[mod_name] = mod; spec.loader.exec_module(mod)
g = WuggyGenerator(); g.load(name, local_language_plugin=mod.OfficialLanguagePlugin())
```

Smoke test command (about 20 s in total):

```bash
. /Users/michalpalinski/kompetencje_jezykowe/.venv/bin/activate
cd /Users/michalpalinski/kompetencje_jezykowe/resources/pseudo/wuggy_plugins
PYTHONDONTWRITEBYTECODE=1 python smoke_test_polish.py
```

Output (`smoke_test_polish_output.log`, `.json`); all three template words are in the lexicon:

| template (syllabification in lexicon) | 5 pseudowords (OLD20) |
|---|---|
| `komora` (`ko-mo-ra`) | kanory (1.80), kasory (1.75), karory (1.80), kabory (1.80), kawory (1.70) |
| `wynik` (`wy-nik`) | wynył (1.80), wynyć (1.80), wyneł (1.95), wyneć (1.95), wynać (1.75) |
| `porównać` (`po-ró-wnać`) | połódnał (2.90), połóścał (3.00), połówcał (2.80), pomódnał (2.90), pomówcał (2.75) |

The official download path was also tested, on a copy of the package in `/tmp` so that the venv stayed
untouched; it produced byte-identical plugin files (same sha256):

```bash
SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())") python -c '
from wuggy import WuggyGenerator
g = WuggyGenerator()
g.download_language_plugin("orthographic_polish", auto_download=True)
g.load("orthographic_polish")
print([m["pseudoword"] for m in g.generate_classic(["komora"], ncandidates_per_sequence=5)])'
```

Without `SSL_CERT_FILE` this fails on this machine with the certificate error quoted above. Run against the
real venv it would write the 40 MB plugin into `.venv/lib/python3.12/site-packages/wuggy/plugins/language_data/`.

### Reproducibility

Wuggy shuffles its start keys with Python's global `random` module (`wuggy/utilities/bigramchain.py`). Without
a seed, repeated runs gave different pseudowords for the same template; `PYTHONHASHSEED=0` did not fix it.
Calling `random.seed(<int>)` right before `generate_classic` gave identical output within a process and across
two separate processes. `generate_classic` also stops at `max_search_time_per_sequence` (default 10 s), so a
slower machine can return fewer candidates.

---

## 2. Dołżycka, Nikadon & Formanowicz (2022)

Paper: Dołżycka, J. D., Nikadon, J., & Formanowicz, M. (2022). Constructing Pseudowords with Constraints on
Morphological Features - Application for Polish Pseudonouns and Pseudoverbs. *Journal of Psycholinguistic
Research, 51*(6), 1247-1265. <https://doi.org/10.1007/s10936-022-09884-6>. Licence of the article: CC BY 4.0
(Crossref licence field: <https://creativecommons.org/licenses/by/4.0>).
Preprint: PsyArXiv <https://doi.org/10.31234/osf.io/9xefc>, licence "CC-By Attribution 4.0 International"
(OSF API).

### Where the code and data are

- The article states: "The scripts used to generate the two initial sets of pseudowords for this paper are
  available as supplemental online material (SOM) at
  https://gin.g-node.org/SocGramLab/pseudo-word-stimuli-with-arbitrary-constrains.git".
- The OSF project linked to the preprint (<https://osf.io/53ps8/>, "Supplemental materials for preprint: ...")
  contains **no files**; its wiki page consists only of the GIN repository URL. No licence is set on that project.
- No GitHub copy was found (GitHub repository search for the repository name and for "pseudonouns pseudoverbs"
  returned 0 results). The Software Heritage API has no origin for the GIN URL. No supplementary-material
  section was found in the text of the Springer article page.

### Status: downloaded (after GIN outage)

Earlier the same day (11:25–12:09 UTC) `gin.g-node.org` answered **HTTP 503** on every probe
(`dolzycka2022/gin_http503_poll_log.txt`). Around 13:57 UTC the host was reachable again and the repository
was cloned:

```bash
cd /Users/michalpalinski/kompetencje_jezykowe/resources/pseudo/dolzycka2022
git clone https://gin.g-node.org/SocGramLab/pseudo-word-stimuli-with-arbitrary-constrains.git repo
# commit 0ad42127df1809beca3b0517a83b6bf7ec456ac2 (2022-10-17), branch master; DataLad metadata present
```

Cloned contents match the 2025-08-05 Wayback listing: `README.org`, four `pwords_proc_pGenerate_00*.org`
literate notebooks, and four xlsx spreadsheets (real Excel files, not git-annex stubs). **No LICENSE /
COPYING file** anywhere in the tree: **repository licence unclear (flagged)**. The journal article itself
remains CC BY 4.0.

### Ready-made pseudoword lists (usable)

UTF-8 CSV extracts are under `dolzycka2022/lists/` (source sheets left intact in `repo/*.xlsx`):

| File | Rows | Content |
|------|------|---------|
| `study1_chosen_nouns_verbs_158.csv` | 158 | Study 1 chosen stimuli (paper cites 159; sheet has 158 data rows) |
| `study1_80_chosen_nouns_verbs.csv` | 80 | Study 1 subset |
| `study1_all_nouns_320.csv` / `study1_all_verbs_320.csv` | 320 each | Full generated pools with ratings |
| `study2_chosen_pairs_120.csv` | 120 | Study 2 chosen verb–noun pairs |
| `study2_40_noun_verb_pairs.csv` | 39 | Study 2 subset sheet (39 non-empty rows) |

Example Study 1 items: `ciltrum`, `celbrum`, `chósło`, `krudert`, `fobunek`. Example Study 2 pairs:
`bakdawić_bakdakła`, `chobucać_chobunek`.

### Dependencies and Wuggy version (from Org + paper)

- Pipeline language: **IPython / Emacs Org** (`#+BEGIN_SRC ipython`), not a standalone CLI. Stages prepare
  template word lists, export TSV for Wuggy, then **read Wuggy’s output TSV back** and filter/merge.
- Private Python packages imported in the Org sources are **not in the GIN repo**: `from init.imports import *`,
  `from init.load import *`, `from aux_nlp.aux_nlp import *`. Input corpora (plTenTen / Sketch Engine dumps,
  SGJP tables, `data_out/` intermediates) are also absent. **Smoke-running the authors’ generation pipeline
  is therefore not feasible** from this clone alone.
- Other imports that *are* ordinary packages: pandas, numpy, scipy (`linear_sum_assignment`, distances),
  matplotlib, seaborn; one later stage mentions `savReaderWriter` (SPSS). Paper also cites Pyphen 0.9.5 and
  Morfeusz 2 / Grammatical Dictionary of Polish.
- **Wuggy version used: the classic desktop Wuggy (Keuleers & Brysbaert, 2010), not the Python package.**
  Evidence: (1) zero `import wuggy` / `WuggyGenerator` in the Org sources; (2) stage “Export for Wuggy”
  writes headerless TSV columns `WORD`, `SYLL`, `SUFF`, then stage “Verify Wuggy output” loads
  `./data_out/s0005_exp_00_pairs_all_DONE.tsv` with desktop-style columns
  `WORD, MATCH, LEXICALITY, OLD20, OLD20_DIFF, NED1, NED1_DIFF, OVERLAP_RATIO, MAXDEVIATION,
  SUMMED_DEVIATION, MAXDEVIATION_TRANSITION`; (3) the paper describes the Wuggy *program* with the Polish
  module and its Matching Expression feature. Installed **Wuggy 1.1.2 does not plug into this workflow**
  as published (different API; `generate_classic` has no matching-expression parameter). The independent
  demo below only illustrates the last-syllable constraint with 1.1.2.

### What is in `dolzycka2022/`

- `repo/`: GIN clone at commit `0ad42127df…` (Org notebooks + xlsx). Nested `.git` — do not `git add` the
  whole tree into the parent repo without care.
- `lists/`: UTF-8 CSV extracts of the published stimulus sheets (derived here on 2026-11-13).
- `DolzyckaEtAl2022a_preprint_psyarxiv_9xefc.pdf`: the preprint (39 pages), from <https://osf.io/download/bupqt/>;
  sha256 equals the hash reported by the OSF API.
- `wayback_20250805170039_gin_repo_page.html`: earlier evidence of the repository listing.
- `gin_http503_poll_log.txt`: log of the failed morning connection attempts.
- `approach_demo_NOT_AUTHORS_CODE.py` and `.log`: **not the authors' code.** A short independent illustration
  of the single step the paper describes (keep the template's last syllable via a regex), done with
  `WuggyGenerator.generate_advanced()` from Wuggy 1.1.2 and the classic settings. It only shows that this step
  is feasible with the installed Wuggy; it does not reproduce the paper's pipeline. Result of
  `python approach_demo_NOT_AUTHORS_CODE.py komora wynik porównać`:
  - `komora`, regex `.+ra$`: matora, mawora, mabora, masora, malora (1.9 s)
  - `wynik`, regex `.+nik$`: minik, renik, rinik, menik, binik (1.7 s)
  - `porównać`, regex `.+wnać$`: **0 candidates** in 30 s (about 50,000 inspected), a consequence of the `ó`
    quirk described in section 1.

---

## 3. UniPseudo

Paper: New, B., Bourgin, J., Barra, J., & Pallier, C. (2024, online 2023). UniPseudo: A universal pseudoword
generator. *Quarterly Journal of Experimental Psychology, 77*(2), 278-286.
<https://doi.org/10.1177/17470218231164373>.

### Polish support

- Yes. Polish is one of the languages in the R Shiny source (`latin_languages` and dataset id `WorldLex-Polish`
  in `apps/unipseudo/www/data/loadingDatasets.R`; 64 datasets are listed there, Lexique383 for French and
  WorldLex for the rest), and "Polish" is in the language menu of the live web app.
- Lexicon for Polish: **WorldLex-Polish** (Gimenes & New 2016, <https://doi.org/10.3758/s13428-015-0621-0>),
  blog/Twitter/news frequencies. File: <http://www.lexique.org/databases/WorldLex/WorldLex-Polish.rds>
  (6,549,777 bytes, md5 `dd9ee3a0268dcd61776b1e1694a1d78f`, matching the md5 in
  `datasets-info/_json/WorldLex-Polish.json`). 545,699 rows, 14 columns: `Word, nbcar, BlogFreq, BlogFreqPm,
  BlogCD, BlogCDPc, TwitterFreq, TwitterFreqPm, TwitterCD, TwitterCDPc, NewsFreq, NewsFreqPm, NewsCD, NewsCDPc.`
- The live web app (<http://www.lexique.org/shiny/unipseudo/>, which now redirects to
  <https://www.lexique.org/django/unipseudo/>) confirmed this on 2026-11-13: its endpoint
  `api/language/?language=Polish` returned database `WorldLex-Polish` and `"presets": {}`.

### Source code and licence

- Original R Shiny app: <https://github.com/chrplr/openlexicon>, folder `apps/unipseudo/` (branch `master`,
  commit `9009f488f664536940965453c127f43cf18b84a4`). Repository licence **CC BY-SA 4.0** (`LICENSE.txt`; README:
  "Unless otherwise explained by a individual readme or license file in a directory, it distributed under a
  CC BY-SA 4.0 LICENSE", <https://creativecommons.org/licenses/by-sa/4.0/>). `apps/unipseudo/` has no licence
  file of its own. Note that this is a share-alike licence applied to code.
- The live site is no longer the Shiny app. Branch `django_dev` of the same repository (commit
  `5d6f5188db995a0c8052b7438137c61e49b99538`, 2026-10-20) contains `openlexicon.org/unipseudo/`, a Django app
  whose `generator.py` describes itself as a "Pure-Python port of generate_pseudowords from the original Shiny
  app ... No Django dependency". Same repository licence file. That the live site runs exactly this commit is
  NOT VERIFIED (the live JavaScript and API routes match the branch's `urls.py`).
- Also seen, not downloaded: <https://github.com/chrplr/unipseudo-go> (GPL-3.0), a Go port of the original
  single-file script `scripts/pseudoword-generation-by-markov-on-trigrams/pseudoword-generation-by-markov-on-trigrams.R`
  (that R script is included in the sparse clone here).
- **Licence of the WorldLex-Polish data: none stated** on the WorldLex page
  (<http://worldlex.lexique.org>, which only asks for citation) or in `datasets-info/WorldLex/README-Worldlex.md`,
  which says the underlying web corpora come from HC Corpora and quotes their collector as believing the use
  "would fall under Fair Use". The `.rds` is hosted on lexique.org, outside the repository. **Flagged as unclear.**

### Algorithm (as implemented in `generatePseudo.R`)

All source words have the same length L. For trigrams: pick a random source word and keep its first 3 letters;
then, for each following position, take the last 2 letters built so far, find all source words with those 2
letters at that same position, and draw the next letter in proportion to how often it follows there. Bigram
variant: same with 1 letter of context. A candidate is kept if it is not a source word, not in the exclusion
list, not a duplicate, and passes the constraints. For a named language the app uses, from the WorldLex table,
source words with `BlogFreqPm > 0.5` and the exclusion list of all entries of that length. Default algorithm:
bigram up to length 5, trigram from 6. Constraint presets in the R app for Polish: at most 3 consecutive
consonants and at most 2 identical consecutive letters (the live Django site reported no presets for Polish).

### Running it locally (both tested)

**R, original code** (`unipseudo/run_unipseudo_local.R`). It sources the unmodified repository files; only the
Shiny UI calls (`shinyjs::html`, `shinyalert`) are neutralised in memory. Needs only the already installed
`shiny` package (for `tags`). Arguments: `n len seed out.csv [own_word_list.txt]`.

```bash
cd /Users/michalpalinski/kompetencje_jezykowe/resources/pseudo/unipseudo
Rscript run_unipseudo_local.R 20 6 1 smoke_test_polish_len6.csv
# constraints off, as on the live site:  UNIPSEUDO_CONSTRAINTS=none Rscript run_unipseudo_local.R 20 6 1 out.csv
```

Result (1.5 s; 9,770 source words, 31,157 excluded words, trigram, seed 1), saved in
`smoke_test_polish_len6.csv` together with the source words of each item:
taliży, węgląc, sensja, chcisy, janich, myleby, ohydło, nosmem, obrótu, obcasz, leczyn, utarch, flesex, wasada,
meniży, jabiją, kolotę, zdejki, żarpie, jecząć.

Not replicated from the app: it passes the table through `fix.encoding()` (needs `rjson`, `varhandle`), here
the `.rds` is read directly (its `Word` column is UTF-8 and `nbcar` counts characters). The consonant
constraint relies on `iconv(..., "ASCII//TRANSLIT")`, whose output differs between platforms.

**Python port** (`unipseudo/run_unipseudo_python_port.py`, uses `generator.py` and `filters.py` from the
`django_dev` snapshot; no Django needed). The 6-letter word lists were exported once with:

```bash
Rscript -e 'wl <- as.data.frame(readRDS("data/WorldLex-Polish.rds")); m <- unique(tolower(wl$Word[wl$BlogFreqPm > 0.5 & wl$nbcar == 6])); e <- unique(wl$Word[wl$nbcar == 6]); writeLines(enc2utf8(m), "data/worldlex_polish_len6_models_BlogFreqPm_gt0.5.txt", useBytes=TRUE); writeLines(enc2utf8(e), "data/worldlex_polish_len6_all.txt", useBytes=TRUE)'
. /Users/michalpalinski/kompetencje_jezykowe/.venv/bin/activate
python run_unipseudo_python_port.py 20 6 1 none
```

Result (`smoke_test_python_port_len6.log`): błakaz, klizną, miemni, wystej, osobyś, losaby, takiel, bledzę,
żytami, podbat, duszyć, obytku, zmętym, barnej, słytań, jeciem, pląski, bywnej, perefa, logone.

Both generators only guarantee that an item is absent from WorldLex-Polish entries of the same length. Several
outputs look like inflected or derivable Polish forms, so dictionary screening is needed before use.

---

## 4. Polish Pseudo-words List (PPwL)

Paper: Imbir, K. K., Spustek, T., & Żygierewicz, J. (2015). Polish pseudo-words list: dataset of 3023 stimuli
with competent judges' ratings. *Frontiers in Psychology, 6*, 1395. <https://doi.org/10.3389/fpsyg.2015.01395>
(PMCID PMC4569746). Article licence: "Creative Commons Attribution License (CC BY)" (article page; Europe PMC
lists `cc by`).

- The article has no supplementary file (Europe PMC `hasSuppl: N`). It says the dataset "is deposited at
  http://figshare.com/s/1089daa40de311e589a806ec4b8d1f61 and consists of a single xlsx spreadsheet".
- That figshare page ("Polish Pseudo Words List Dataset", "This item is shared privately", modified
  2015-12-03) shows **Licence: CC BY 4.0** (<https://creativecommons.org/licenses/by/4.0/>). The item was not
  found through the figshare search API. `curl` on the page gets an AWS WAF JavaScript challenge (HTTP 202, empty body), so
  the page was opened once in the Cursor browser to read the licence and the file link; the file itself
  downloads with plain `curl`:

```bash
curl -L -o Polish_pseudo-words_List_dataset.xlsx \
  "https://ndownloader.figshare.com/files/2099389?private_link=1089daa40de311e589a806ec4b8d1f61"
python convert_to_csv.py     # openpyxl, writes UTF-8 CSV with unchanged values
```

- `imbir2015/Polish_pseudo-words_List_dataset.xlsx`: 101,174 bytes, one sheet `PPwL`, 3,024 rows x 4 columns.
- `imbir2015/Polish_pseudo-words_List_dataset.csv`: UTF-8, header + **3,023 rows**, 4 columns:
  1. `pseudo-word`
  2. `Judge competent congruency index ` (trailing space in the original header): 0.2 to 1.0, equal to column 3 / 5
  3. `No. of judges indicating that this is good example of pseudo-word`: 1 to 5
  4. `Length: Number of letters`: 4 to 13
- Checks run on the CSV: 3,023 unique pseudo-words, no empty cells, all lower-case, column 4 equals the
  character count for every row. Judges: 5/5 for 870 items, 4 for 988, 3 for 537, 2 for 341, 1 for 287
  (no item with 0 judges; the paper reports 3,240 generated items of which 217 were rejected by all five).
  Length counts: 4: 365, 5: 525, 6: 649, 7: 385, 8: 406, 9: 410, 10: 173, 11: 26, 12: 62, 13: 22.
  Six-letter items accepted by all five judges: 124.
- Generation method per the paper: random letter substitution in 540 nouns from a 4,905-word Polish norming
  list (1 letter for 4-6 letter words, 2 for 7-9, 3 for 10-13), then rating by five judges. Not Wuggy-based.

---

## Files

<!--FILES_TABLE_START-->
Download date for all downloaded files: 2026-11-13. Source URLs, run commands and notes per file are in `manifest.json` (regenerate both with `python build_manifest.py`).

| Path | Kind | Size (bytes) | sha256 or commit | Licence | Status |
|---|---|---|---|---|---|
| (Wuggy Python package (already installed in the venv; not downloaded in this task)) | preinstalled |  | `1.1.2 (PyPI wheel uploaded 2024-02-20)` | MIT | ready |
| `wuggy_plugins/orthographic_polish/orthographic_polish.txt` | downloaded | 39841583 | `1cc6a5391a29452150ccd9d3ab74f3055b0f03beab6e0efd8902b27c7b152216` | none stated (flagged) | licence_unclear |
| `wuggy_plugins/orthographic_polish/orthographic_polish.py` | downloaded | 1017 | `f3172e0c2531784bc8de5672f20a4362da4e1eacde5d6740ffc7c9ef6f2a98e3` | none stated (flagged) | licence_unclear |
| `wuggy_plugins/load_local_plugin.py` | local_script | 1705 | `420c9ffe8408c7d2f4db47db5d2790a3e41600b222463c22ef4d2e7c8c0337d1` | n/a (written here) | ready |
| `wuggy_plugins/smoke_test_polish.py` | local_script | 1936 | `17d6a77314ccdafd1fd3c9a1c8c9dd2117b07fa0e95184083bc2d5ab9ec94fde` | n/a (written here) | ready |
| `wuggy_plugins/smoke_test_polish_output.log` | output | 1753 | `7e56052fc19af99a33c5a6f7ff36fdca52df074faae9846ce05d92745353a1bc` | n/a (written here) | ready |
| `wuggy_plugins/smoke_test_polish_output.json` | output | 2366 | `8ff47a506d346f842f2b3e2758abca350cba319899679b9e21a77de8993d941e` | n/a (written here) | ready |
| `dolzycka2022/repo` | downloaded | 2879488 | `branch master, commit 0ad42127df1809beca3b0517a83b6bf7ec456ac2 (2022-10-17)` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/.gitattributes` | downloaded | 533 | `7304616f71d982a58a69d791096f488d7eb8f743289c3b4fe56eb11e47102bfd` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/README.org` | downloaded | 703 | `03da920c0ab0eca46789f2236e89ae3daa2771f7d6514d694ff5c94d3096383c` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/pwords_proc_pGenerate_001_main.org` | downloaded | 744239 | `f97c6eb06a695e8e44a14bca018ad6a8b207577d5a919d5cf9b98cf47fb2eed6` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/pwords_proc_pGenerate_002_syllabes_freq_1st.org` | downloaded | 174665 | `432fed3a47001c75e245884b148551003cb19fb600b90339769a199e9ed46405` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/pwords_proc_pGenerate_003_word_vals.org` | downloaded | 264712 | `4aa8c02a559af0bb3a07145b756e2a072d539af75594b5cae48a0e5e583581bf` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/pwords_proc_pGenerate_004_generate_gforms.org` | downloaded | 229777 | `7c94564f6d8f0fd76278c41c09479bc4897dd2b593ce7fea288ea607de09e387` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/SOM_study_1_dataset_JLSP_FINAL_001.xlsx` | downloaded | 115820 | `f27a92426d53695022333683f5505c031ab244a4b0532fd6367c23312a4afc97` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/SOM_study_2_dataset_JLSP_FINAL_001.xlsx` | downloaded | 179843 | `8dc796b772fe73ebd789bc8d0cce759f9bc98a16f02639cb7f0da4df6fd41850` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/supplementary_material_study_1.xlsx` | downloaded | 94110 | `ef40ebe97d8fc15fce80eaa4a446d7633459720d8918bfb7ef50e9d524e5a627` | none stated (flagged) | licence_unclear |
| `dolzycka2022/repo/supplementary_material_study_2.xlsx` | downloaded | 127332 | `38808fe98e74f3a1e8ba868ee0517d8e9cbc97c2f415526a8a582278d4cb2a8a` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study1_chosen_nouns_verbs_158.csv` | derived | 23273 | `30952e4c8db14a94bcc4f1d4f39307f1e5348eb47330b4c19aae4a7c4371b136` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study1_80_chosen_nouns_verbs.csv` | derived | 12008 | `fe13c8048b8fc0fa3505ef9ce1a7fa2b9fcd9a695157d53ff83aca68545a9c79` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study1_all_nouns_320.csv` | derived | 47238 | `ba5c39713fdee9934477671520ea897b1d02fc853e15d5ff6b96d6b9cedb5984` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study1_all_verbs_320.csv` | derived | 47051 | `a9d60d35b2edd551bc8c78bd2eb27a4ee12b2533a58a419ef88ed0b5d4a15e01` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study2_chosen_pairs_120.csv` | derived | 79097 | `aec309e3da10ff295e97718430654440a28b8e42a2b014418fc8dc11def712b3` | none stated (flagged) | licence_unclear |
| `dolzycka2022/lists/study2_40_noun_verb_pairs.csv` | derived | 31771 | `4b2052653ab5f9dadd98c66a435c343673529f3710369c453ab17eb3201e384c` | none stated (flagged) | licence_unclear |
| `dolzycka2022/DolzyckaEtAl2022a_preprint_psyarxiv_9xefc.pdf` | downloaded | 583923 | `4f0fbcc2b752a2ab482155cc6074bac3bfd35265feefbfdf86cbe2cbd1309ee0` | CC BY 4.0 | downloaded_not_run |
| `dolzycka2022/wayback_20250805170039_gin_repo_page.html` | evidence | 28016 | `a140d3c429376ded67aa80228b7e50076532b203bc0a484588e9c2c1ed5ef696` | not recorded | downloaded_not_run |
| `dolzycka2022/gin_http503_poll_log.txt` | evidence | 1996 | `b49dfdde50bf43ce6489b676720c1dc92e5f2a66e5cb6bbd474cb4ca69074c69` | not recorded | downloaded_not_run |
| `dolzycka2022/approach_demo_NOT_AUTHORS_CODE.py` | local_script | 3333 | `b536e7da6415ce1b79f7fe6cb04871d026d2d5eb00cac8a21b2d382982229ec6` | n/a (written here) | ready |
| `dolzycka2022/approach_demo_NOT_AUTHORS_CODE.log` | output | 444 | `738e95c191c7437c7425153de17a6f7af73547b7709de400fe23cdd660423645` | n/a (written here) | ready |
| `unipseudo/openlexicon` | downloaded | 6860800 | `branch master, commit 9009f488f664536940965453c127f43cf18b84a4` | CC BY-SA 4.0 | ready |
| `unipseudo/data/WorldLex-Polish.rds` | downloaded | 6549777 | `e82fc08b1af799749e35a8ee75904669eefc99dd529a8340576d6cf4e4c7be8b` | none stated (flagged) | licence_unclear |
| `unipseudo/data/worldlex_polish_len6_models_BlogFreqPm_gt0.5.txt` | derived | 74067 | `4ead24f7eb3275a8ccffd002303aa8b8d2dbc3b8af562dc1f8dfdb641c892826` | none stated (flagged) | licence_unclear |
| `unipseudo/data/worldlex_polish_len6_all.txt` | derived | 235741 | `5dd79fbe2533ff5c17af820dd5ee528726a0c96997b5f501e7466c474aa30b76` | none stated (flagged) | licence_unclear |
| `unipseudo/run_unipseudo_local.R` | local_script | 5836 | `f230b8c5f12fa488b6ff81602cfa111cc8ccafe83f114fb5ecf59a78ceb33fc5` | n/a (written here) | ready |
| `unipseudo/smoke_test_polish_len6.csv` | output | 994 | `74d9008a69bf9f3116c86294f48dad6bbc4c25023644bf0096a08db1d48b7ecc` | n/a (written here) | ready |
| `unipseudo/smoke_test_polish_len6.log` | output | 1142 | `0dc38ce7a836f1a7aa969ad72e423029379c060c90805fc93efcb7b9d5deac1d` | n/a (written here) | ready |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/generator.py` | downloaded | 5672 | `0e7214bb3afcb47fc645e028d7ed9699b1fc47bea181b75510f69f7209e1fcdb` | CC BY-SA 4.0 | ready |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/filters.py` | downloaded | 4471 | `1c5b02a58a7dbe5ce4738ad4a9e7b10f9a634f60f8a88fc8afc4bbffcf855f64` | CC BY-SA 4.0 | ready |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/conf.py` | downloaded | 2485 | `f1f3aa0010b2029ef4ff300877c03cdf1ede2609023ac318071d3825d8f04eed` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/services.py` | downloaded | 6432 | `a3e2f2c87bdc54d260a6a998793fe0a5e77b09e8ec7af7a06e7785aef523261e` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/views.py` | downloaded | 9964 | `bccc8ecf67c4022e291ae700dda351489ba4ba24840d048dac03eed206621508` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/urls.py` | downloaded | 372 | `74b36a5b8c69dde85fcecf0c3cad350f39120a122128a845813e4b95cd2e8502` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/apps.py` | downloaded | 124 | `c7412fe7a4c5051536a07d36ee4e21bcb747637252ea814d5faabaab56f38828` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/tests.py` | downloaded | 12986 | `7748bee923e57873ae80be89f85988012a16e223300ce29fd78df09040a8dd45` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/__init__.py` | downloaded | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | CC BY-SA 4.0 | downloaded_not_run |
| `unipseudo/run_unipseudo_python_port.py` | local_script | 2813 | `487e49e83dd2a6018f39b4364578b3baf1ccdee8be1ef56867225b37ff5e62e0` | n/a (written here) | ready |
| `unipseudo/smoke_test_python_port_len6.log` | output | 938 | `de3169021a0448a30ea2c726470d031f89d7dc4d3c44953c6b18da06f36810c2` | n/a (written here) | ready |
| `imbir2015/Polish_pseudo-words_List_dataset.xlsx` | downloaded | 101174 | `c543022ba6e310ae295cd35cb67d4476e7b7665a436397846b3fc680d9a8f33c` | CC BY 4.0 | ready |
| `imbir2015/Polish_pseudo-words_List_dataset.csv` | derived | 51065 | `15b4b552d79f00528f49d3d7e72d3a781a3b827cb7f13fdc0be5070b66bf197c` | CC BY 4.0 | ready |
| `imbir2015/convert_to_csv.py` | local_script | 936 | `383dfdf9e897c85f05edb37d0d818c025fbf12777bc0608fad0d8e8d9110b713` | n/a (written here) | ready |
<!--FILES_TABLE_END-->

## Leftovers and caveats

- A figshare tab opened in the Cursor browser for item 4 could not be closed by the tool and may still be open.
- `unipseudo/openlexicon/` is a git checkout with its own `.git` (partial, sparse clone). If the project
  folder is put under git, add it as ignored or it will be picked up as an embedded repository.
- Python was run with `PYTHONDONTWRITEBYTECODE=1` so that no `__pycache__` folders were created here.
- Scratch files were kept in `/tmp` only.
- `resources/freq/` (present in the parent folder) was not touched.
