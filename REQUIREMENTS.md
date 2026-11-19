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
| R | 4.4.1 | only to export the WorldLex-Polish word list from `WorldLex-Polish.rds` (`Rscript export_worldlex.R`, once) | no UniPseudo candidates; step 7 checks candidates against one word list fewer |

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
| `resources/freq/kwjp100-slowa-lemma-all.csv.gz` | KWJP100 lemma frequencies (general Polish; the list used in published results) | [ipipan/kwjp100-varia @ 26d82bd](https://raw.githubusercontent.com/ipipan/kwjp100-varia/26d82bd8b906dfed1cfcf8f903b1650b56daeabf/freqlists/kwjp100-slowa-lemma-all.csv.gz) | CC BY 4.0 | 3.1 MB | steps 3 and 7 (required) |
| `resources/freq/kwjp100-slowa-orth_lc-all.csv.gz` | KWJP100 form frequencies | [ipipan/kwjp100-varia @ 26d82bd](https://raw.githubusercontent.com/ipipan/kwjp100-varia/26d82bd8b906dfed1cfcf8f903b1650b56daeabf/freqlists/kwjp100-slowa-orth_lc-all.csv.gz) | CC BY 4.0 | 5.9 MB | steps 3 and 7 (required) |
| `resources/freq/nkjp_1grams.gz` | NKJP 1-grams | [zil.ipipan.waw.pl/NKJPNGrams](https://zil.ipipan.waw.pl/NKJPNGrams?action=AttachFile&do=get&target=1grams.gz) | CC BY, version not stated | 22.7 MB | step 3 (required) |
| `resources/freq/nkjp1m-1.2_lemma_freq.tsv` | lemma frequencies of the NKJP 1M subcorpus; derive with `python resources/freq/derive_nkjp1m_freq.py` from `NKJP-PodkorpusMilionowy-1.2.tar.gz` placed in the same folder | [clip.ipipan.waw.pl/NationalCorpusOfPolish](https://clip.ipipan.waw.pl/NationalCorpusOfPolish?action=AttachFile&do=get&target=NKJP-PodkorpusMilionowy-1.2.tar.gz) | CC BY, version stated inconsistently | 171 MB archive | step 3 (required) |
| `resources/freq/subtlex-pl-lemmas-master.csv` | SUBTLEX-PL lemma frequencies, comparison metrics only | [osf.io/download/ab9ym](https://osf.io/download/ab9ym/) | **CC BY-NC-SA 4.0** | 59 MB | step 3 (required by the code as written) |
| `resources/tools/stanza_resources/` | Stanza Polish models, default package | `python -c "import stanza; stanza.download('pl', model_dir='resources/tools/stanza_resources')"` | Apache-2.0 on the model card; training treebank CC BY-NC-SA 4.0 | 436 MB | step 2 comparison and step 4 TermoPL input (optional) |
| `resources/tools/termopl/TermoPL_Mac_OS_X/` | TermoPL 8.1.1, unpacked macOS arm64 package | [zil.ipipan.waw.pl/TermoPL](https://zil.ipipan.waw.pl/TermoPL?action=AttachFile&do=get&target=TermoPL_Mac_OS_X.zip) | BSD 2-clause | 21 MB | step 4 (optional) |
| `resources/pseudo/wuggy_plugins/orthographic_polish/orthographic_polish.py` and `.txt` | official Wuggy Polish plugin and its lexicon | [WuggyCode/wuggy_language_plugin_data @ 2968223](https://github.com/WuggyCode/wuggy_language_plugin_data/tree/2968223983626c4a178cda7ea071c082dcaba3fb/orthographic_polish) | none stated | 40 MB | step 7 (optional) |
| `resources/pseudo/imbir2015/Polish_pseudo-words_List_dataset.csv` | Imbir (2015) pseudoword list; download the xlsx, then `python convert_to_csv.py` in that folder | [figshare file 2099389](https://ndownloader.figshare.com/files/2099389?private_link=1089daa40de311e589a806ec4b8d1f61) | CC BY 4.0 | 0.1 MB | step 7 (optional) |
| `resources/pseudo/unipseudo/openlexicon_django_dev_5d6f5188/unipseudo/generator.py`, `filters.py` | UniPseudo generator (Python port) | [chrplr/openlexicon @ 5d6f518](https://github.com/chrplr/openlexicon/tree/5d6f5188db995a0c8052b7438137c61e49b99538/openlexicon.org/unipseudo) | CC BY-SA 4.0 | under 0.1 MB | step 7 (optional) |
| `resources/pseudo/unipseudo/data/worldlex_polish_words.tsv` | WorldLex-Polish word list (word, length, blog frequency); download `WorldLex-Polish.rds` into `data/`, then run `Rscript export_worldlex.R` in `resources/pseudo/unipseudo/` | [WorldLex-Polish.rds](http://www.lexique.org/databases/WorldLex/WorldLex-Polish.rds) | none stated | 6.5 MB download, 10.3 MB exported | step 7 (optional): source words of the UniPseudo chains and one of the lists used to reject existing words |

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
plus its estimated cost would pass the limit. The requests of the published sample run cost about 32 USD: 26 USD for
labelling 5,344 candidates with two models and adjudicating their disagreements, 5 USD for generating and rating
pseudowords, and the rest for the lemmatisation benchmark, direct term extraction and concept grouping. Which model
does which task is set in the `llm` section of the configuration. With `--bez-llm` no API call is made: step 5 is
skipped and the other steps use only answers already in the local cache.

## 5. Running

```bash
. .venv/bin/activate
python -m jutro run --config config/biologia_sp.yaml --probka 50      # sample: 50 target + 300 contrast materials
python -m jutro run --config config/biologia_sp.yaml                  # full corpus
python -m jutro run --config config/biologia_sp.yaml --probka 50 --kroki raport   # one step only
```

Steps whose result already exists in `data/<name>/<run>/` are skipped; `--od-nowa` forces them to run again.
In the sample run the local computation took about 6 minutes for steps 1–4 and 2 minutes for step 7. The rest of the
time is waiting for the API: about 10 minutes for the direct requests of the lemmatisation benchmark in step 2, and
between 1 and 10 minutes for each batch job (five in step 5, two in step 7). The run left about 50 MB in `data/`.

Batch identifiers are written to `data/<name>/<run>/llm/*.oczekujace.json` as soon as a batch is sent. If the run is
interrupted while a batch is being processed, the next run collects the results of that batch instead of sending
(and paying for) the requests again.

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
- Wuggy stops searching after `pseudoslowa.wuggy_czas_s` seconds per template, so on a slower or busier machine it
  can return fewer candidates.
- The versions of all libraries used by a run are saved in `wyniki/<name>/<run>/przebieg.json`.
