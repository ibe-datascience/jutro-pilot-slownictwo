# Requirements for reproducing the pipeline

What you need besides the code in this repository. The published run (`probka50`) was made on macOS 26.5 (Apple
Silicon, 18 GB RAM) with Python 3.12.2; nothing has been tested on Linux or Windows.

## 1. System software

| Software | Version used | Needed for | Without it |
|:---|:---|:---|:---|
| Python | 3.12.2 | everything | – |
| Java runtime | OpenJDK 11.0.22 | TermoPL (step 4) | step 4 runs without the C-value method |
| bash, awk | system | `resources/tools/termopl/run_termopl.sh` | as above |
| Quarto | 1.9.36 | the report site (step 8) | step 8 still writes `raport.md`; the site is not rebuilt |
| R | 4.4.1 | only to export UniPseudo word lists from `WorldLex-Polish.rds` | no UniPseudo candidates |

## 2. Python environment

```bash
python3.12 -m venv .venv            # must be called .venv and sit in the repository root
. .venv/bin/activate
pip install -r requirements.txt     # direct dependencies, pinned
# or, for the exact environment of the published run:
pip install -r requirements-lock.txt
```

The location matters: `run_termopl.sh` and step 7 start helper scripts with `<repository>/.venv/bin/python`.

`requirements.txt` installs the spaCy model `pl_core_news_lg` 3.8.0 (GPL-3.0, about 570 MB) and Morfeusz2 with the
SGJP dictionary. `wordfreq` brings its own Polish frequency data.

## 3. Files to download into `resources/`

These are not in the repository because of their size or licence. Paths are relative to the repository root. Full
notes on each (how it was obtained, format, licence evidence, SHA-256) are in `resources/*/README_*.md` and
`resources/*/manifest.json`.

| Path | What | Source | Licence | Size | Used by |
|:---|:---|:---|:---|---:|:---|
| `resources/freq/kwjp100-slowa-lemma-all.csv.gz` | KWJP100 lemma frequencies (general Polish; the list used in published results) | [ipipan/kwjp100-varia @ 26d82bd](https://raw.githubusercontent.com/ipipan/kwjp100-varia/26d82bd8b906dfed1cfcf8f903b1650b56daeabf/freqlists/kwjp100-slowa-lemma-all.csv.gz) | CC BY 4.0 | 3.1 MB | step 3 (required) |
| `resources/freq/kwjp100-slowa-orth_lc-all.csv.gz` | KWJP100 form frequencies | [ipipan/kwjp100-varia @ 26d82bd](https://raw.githubusercontent.com/ipipan/kwjp100-varia/26d82bd8b906dfed1cfcf8f903b1650b56daeabf/freqlists/kwjp100-slowa-orth_lc-all.csv.gz) | CC BY 4.0 | 5.9 MB | step 3 (required) |
| `resources/freq/nkjp_1grams.gz` | NKJP 1-grams | [zil.ipipan.waw.pl/NKJPNGrams](https://zil.ipipan.waw.pl/NKJPNGrams?action=AttachFile&do=get&target=1grams.gz) | CC BY, version not stated | 22.7 MB | step 3 (required) |
| `resources/freq/nkjp1m-1.2_lemma_freq.tsv` | lemma frequencies of the NKJP 1M subcorpus; derive with `python resources/freq/derive_nkjp1m_freq.py` from `NKJP-PodkorpusMilionowy-1.2.tar.gz` placed in the same folder | [clip.ipipan.waw.pl/NationalCorpusOfPolish](https://clip.ipipan.waw.pl/NationalCorpusOfPolish?action=AttachFile&do=get&target=NKJP-PodkorpusMilionowy-1.2.tar.gz) | CC BY, version stated inconsistently | 171 MB archive | step 3 (required) |
| `resources/freq/subtlex-pl-lemmas-master.csv` | SUBTLEX-PL lemma frequencies, comparison metrics only | [osf.io/download/ab9ym](https://osf.io/download/ab9ym/) | **CC BY-NC-SA 4.0** | 59 MB | step 3 (required by the code as written) |
| `resources/tools/stanza_resources/` | Stanza Polish models, default package | `python -c "import stanza; stanza.download('pl', model_dir='resources/tools/stanza_resources')"` | Apache-2.0 on the model card; training treebank CC BY-NC-SA 4.0 | 436 MB | step 2 comparison and step 4 TermoPL input (optional) |
| `resources/tools/termopl/TermoPL_Mac_OS_X/` | TermoPL 8.1.1, unpacked macOS arm64 package | [zil.ipipan.waw.pl/TermoPL](https://zil.ipipan.waw.pl/TermoPL?action=AttachFile&do=get&target=TermoPL_Mac_OS_X.zip) | BSD 2-clause | 21 MB | step 4 (optional) |
| `resources/pseudo/wuggy_plugins/orthographic_polish/orthographic_polish.py` and `.txt` | official Wuggy Polish plugin and its lexicon | [WuggyCode/wuggy_language_plugin_data @ 2968223](https://github.com/WuggyCode/wuggy_language_plugin_data/tree/2968223983626c4a178cda7ea071c082dcaba3fb/orthographic_polish) | none stated | 40 MB | step 7 (optional) |
| `resources/pseudo/imbir2015/Polish_pseudo-words_List_dataset.csv` | Imbir (2015) pseudoword list; download the xlsx, then `python convert_to_csv.py` in that folder | [figshare file 2099389](https://ndownloader.figshare.com/files/2099389?private_link=1089daa40de311e589a806ec4b8d1f61) | CC BY 4.0 | 0.1 MB | step 7 (optional) |
| `resources/pseudo/unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/generator.py`, `filters.py` and `resources/pseudo/unipseudo/data/` | UniPseudo generator (Python port) and WorldLex-Polish word lists | [chrplr/openlexicon @ 5d6f518](https://github.com/chrplr/openlexicon/tree/5d6f5188db995a0c8052b7438137c61e49b99538/openlexicon.org/unipseudo), [WorldLex-Polish.rds](http://www.lexique.org/databases/WorldLex/WorldLex-Polish.rds) | code CC BY-SA 4.0; data: none stated | 6.6 MB | step 7 (optional, see section 7) |

"Optional" means the step logs the failure and continues without that method. "Required" means the step stops if the
file is missing. On another operating system TermoPL needs the matching package from the same page and the `APP`
path in `run_termopl.sh` changed accordingly.

## 4. Input data and credentials

Set these in the `zrodlo` section of `config/biologia_sp.yaml`; the committed file holds the paths of the machine that
made the published run.

| Setting | What it must point to |
|:---|:---|
| `zrodlo.zpe_dir` | A local dump of the ZPE platform with `catalog.jsonl`, `subjects.json`, `materials/<id>.manifest.json`, `materials/<id>_<unit>.html` and `texts/<id>.txt`. Read-only for the pipeline. The dump is not distributed with this repository. |
| `zrodlo.env_file` | A `.env` file with `ANTHROPIC_API_KEY=...` (the environment variable of the same name also works). |
| `zrodlo.podstawa_pdf` | Present in the configuration, but no step reads it at the moment. |

API use is bounded by `llm.limit_kosztu_usd` in the configuration: a request batch is refused when the spend so far
plus its estimated cost would pass the limit. The sample run cost about 2.4 USD. With `--bez-llm` no API call is
made: step 5 is skipped and the other steps use only answers already in the local cache.

## 5. Running

```bash
. .venv/bin/activate
python -m jutro run --config config/biologia_sp.yaml --probka 50      # sample: 50 target + 300 contrast materials
python -m jutro run --config config/biologia_sp.yaml                  # full corpus
python -m jutro run --config config/biologia_sp.yaml --probka 50 --kroki raport   # one step only
```

Steps whose result already exists in `data/<name>/<run>/` are skipped; `--od-nowa` forces them to run again.
The sample run needed about 40 minutes of processing, most of it waiting for batch jobs in step 5, and about 40 MB
in `data/`.

To rebuild only the site from the committed results in `wyniki/` (no ZPE dump, models or API key needed):

```bash
. .venv/bin/activate
python -m jutro site --config config/biologia_sp.yaml --probka 50
```

This renders `site/*.qmd` with Quarto and replaces `docs/`, the folder GitHub Pages serves, with the result. Step 8
of a normal run does the same. The pages contain no hard-coded numbers; they read `wyniki/<name>/<run>/` while
rendering.

## 6. What is and is not repeatable

- Sampling of materials, the benchmark sample, the gold-set worksheet and template choice use the seed `ziarno` from
  the configuration.
- Language-model answers are not deterministic. They are cached under `data/<name>/<run>/llm/`, which is not
  published, so a fresh run asks the models again and labels can differ.
- The versions of all libraries used by a run are saved in `wyniki/<name>/<run>/przebieg.json`.

## 7. Known problem that affects reproduction

Step 7 does not read the output of the UniPseudo generator. It takes the first rows of whichever CSV file is in
`resources/pseudo/unipseudo/`. In the published run that was a six-letter smoke-test file, so the `unipseudo` rows in
`pseudoslowa.csv` repeat three strings. On a clean checkout there is no such file and the method returns nothing. The
other three generators are not affected.
