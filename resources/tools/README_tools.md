# Polish NLP tools for the terminology pilot: availability, licence, install status

Checked on 2026-11-13, macOS (Darwin 25.5.0, arm64), Python 3.12.2, OpenJDK 11.0.22 (Corretto) at `/usr/bin/java`.
Everything below was fetched or run on this machine on that day; where something was not run it says so.
Machine-readable version: `manifest.json` (same directory).

## 1. Summary

| Tool | Version | Works here? | Licence (as declared) | Open question |
|---|---|---|---|---|
| TermoPL | 8.1.1 | yes, headless batch mode | BSD 2-clause | none |
| Morfeusz2 (already in venv; also bundled in TermoPL) | 1.99.15, SGJP 2026-06-01 | yes | BSD 2-clause | none |
| spaCy `pl_core_news_lg` | 3.8.0 | yes | GNU GPL 3.0 | training treebank says CC BY-NC-SA 4.0 (section 7) |
| Stanza `pl` default package (PDB) | models for Stanza 1.15.0 | yes | Apache-2.0 on the model card | training treebank says CC BY-NC-SA 4.0 (section 7) |
| Concraft-pl | 2.5.0 binary, model SGJP-20220221 | yes, prebuilt x86_64 binary under Rosetta 2 | code BSD 2-clause | no licence stated for the model |
| COMBO (`combo-nlp`) | 4.0.14 | yes, in its own venv; model cache deleted again (3.4 GB) | code GPL-3.0, Polish models CC BY-NC-SA 4.0 | non-commercial licence; 3.4 GB of models |
| IPI PAN spaCy models `pl_spacy_model`, `pl_spacy_model_morfeusz` | 0.1.0 / 0.1.3 | no | GNU GPL 3.0 | need spaCy 2.2–2.3 |
| `pl_nask` | 0.0.7 | no (not in the main venv) | none in package metadata | needs spaCy 3.5.x, no Python 3.12 wheels |
| KRNNT | 1.0.0 | no | LGPL-3.0 | needs TensorFlow 1.14 / Keras 2.2.5 |
| COMBO legacy (`combo` 1.0.7) | 1.0.7 | no | GPL-3.0 | pins torch 1.7.1, allennlp 1.3.0, spacy 2.3.2 |
| IPI PAN Multiservice (web service) | – | no, public instance does not answer | CC BY 3.0 (software) | – |
| CLARIN-PL web services (Postagger) | – | not tried | – | needs a CLARIN-PL account and API token; texts leave the machine |

### Three things that did not go as instructed

1. **Download budget exceeded.** Total downloads were about 5 GB against the ~4 GB limit. The overshoot comes from COMBO: 205 MB of wheels plus 3.36 GB of models (I had expected about 1.1 GB; the segmenter model and the base encoder are a further 1.1 GB each). The 3.36 GB model cache has been deleted again; the 1.0 GB venv is kept. `rm -rf resources/tools/combo` removes the rest.
2. **Two archive copies were written outside `resources/tools/` by the mandated download commands** (library defaults, noticed afterwards, left untouched because they sit in your personal caches):
   - `~/.cache/huggingface/hub/blobs/16/162b914981fee565eeda4a379678d7e24fd1a01e3ed48cf956349363eb9105c4` (416,036,108 bytes, Stanza `default.zip`), plus the small `~/.cache/huggingface/hub/models--stanfordnlp--stanza-pl/` entry that points to it. Stanza 1.15.0 downloads through `huggingface_hub`, which caches there regardless of `model_dir`.
   - `~/Library/Caches/pip/http-v2/6/b/f/7/a/6bf7a2b408c3b3cb9e4a423e0c004cb23aa2b9b143d351354224e7c1.body` (573,718,074 bytes, the `pl_core_news_lg` wheel in pip's HTTP cache).
   Both are safe to delete; together they hold about 1 GB.
3. **`pyarrow==26.0.1` appeared in the main venv at 12:32:37.** It was not installed by this work (the only pip action here was `python -m spacy download pl_core_news_lg` at 12:26). spacy, stanza, torch, numpy and pandas are unchanged (`pip freeze` diff before/after shows only `pl_core_news_lg` and `pyarrow`).

### Disk use under `resources/tools/` (after clean-up)

| Path | Size |
|---|---|
| `termopl/` (program 21 MB + scripts + test data) | 22 MB |
| `stanza_resources/` | 436 MB |
| `concraft/` (binary 16 MB, model 80 MB) | 98 MB |
| `combo/venv/` | 1.0 GB |
| spaCy model inside `.venv/lib/python3.12/site-packages/pl_core_news_lg` | 611 MB |

All downloaded archives inside `resources/tools/` were deleted after unpacking (`TermoPL_Mac_OS_X.zip`, Stanza `pl/default.zip`, `Concraft-MacOSX.zip`, `format-examples.zip`).

---

## 2. TermoPL 8.1.1

- Page: <https://zil.ipipan.waw.pl/TermoPL> ("Downloads (current version: 8.1.1)", page last edited 2025-10-30). The jar's About class contains the string `Version 8.1.1`.
- Downloaded: `https://zil.ipipan.waw.pl/TermoPL?action=AttachFile&do=get&target=TermoPL_Mac_OS_X.zip` (9,429,888 bytes, "Mac OS X (arm_64)" package), unpacked to `termopl/TermoPL_Mac_OS_X/`. SHA-256 of `TermoPL.jar`: `b46c5aab9a9dfa70ffc1ba51e180c4473201100edb8ccddd59ae562f768c6fb2`.
- Package contents: `TermoPL.jar`, `libjmorfeusz.dylib` and `libmorfeusz2.dylib` (both arm64), `parse.py`, `TermoPL-user-manual.pdf` (manual "TermoPL 8.1", dated 22.09.2025), `termopl_sw.txt` / `termopl_cp.txt` / `termopl_ct.txt` (default stop words, compound prepositions, common terms), `languages/`.
- Licence: BSD 2-clause, "Copyright (c) 2016, Institute of Computer Science, Polish Academy of Sciences". Text: `termopl/LICENSE.txt`, from `https://zil.ipipan.waw.pl/TermoPL?action=AttachFile&do=get&target=LICENSE.txt`. The bundled Morfeusz 2 library is also BSD 2-clause (<https://morfeusz.sgjp.pl/doc/license/>).
- Sources (`src.zip` from the same page) were read to confirm the behaviour described below; they are not kept on disk.

### 2.1 Input formats (manual section 2.1 and `CorpusReader.java`)

TermoPL needs **morphologically tagged, disambiguated, lemmatised** UTF-8 input. The format is chosen per file:

| Format | Recognised by | What is read |
|---|---|---|
| CoNLL-U | extension `.conllu` | col 2 FORM, col 3 LEMMA, col 4 UPOS, col 5 XPOS (used as the NKJP-style tag), col 6 FEATS, col 7 HEAD, col 8 DEPREL, col 10 MISC (`SpaceAfter=No`, or `start_char=..\|end_char=..`, optional `ner=`). Multi-word-token lines `1-2` are handled. A comment line containing `newdoc` starts a new document. All 10 columns must be present. |
| Flat text | any other name whose lines have two tabs | `form<TAB>lemma<TAB>tag`, or `form<TAB>#lemma<TAB>#tag#`. Empty line (or `&<TAB>&<TAB>interp`) ends a sentence. A line starting with `%%` starts a new document. |
| Legacy flat | extension `.tgt` | `form<TAB>lemma<TAB>tag[<TAB>nps]`, sentences end with a line `eos`. |
| XCES / CCL | extension `.ccl` or `<?xml … <cesAna` | `<tok><orth>`, `<lex disamb="1"><base>`, `<ctag>` |
| NKJP TEI | `<?xml … <teiCorpus` | `ann_morphosyntax`-style `fs type="morph"` with `disamb` |
| Plain text | anything else | handed to `parse.py` (Stanza) to produce a `.conllu` next to the file. **Does not work in batch mode in 8.1.1**, see 2.4. |

The tag is the NKJP/SGJP positional tag with `:` separators, e.g. `subst:sg:gen:m3`, `adj:pl:nom:f:pos`. The built-in grammar only looks at the class (`subst`, `ger`, `adj`, `adja`, `ppas`), at `case = gen`, at agreement in number/case/gender, and at the form `-`. The default tagset is defined "by values", so the order of categories inside the tag does not matter.

What can produce this input here:

| Source | Result |
|---|---|
| **Stanza `pl` (PDB)** | Directly usable. Stanza's XPOS column is already the NKJP-style tag, so `CoNLL.write_doc2conll` output is read as is. Stanza's lemmatiser makes errors on domain words (below). |
| **Morfeusz2 alone** | Not usable: it lists all readings, it does not disambiguate. Usable as a lemma check on top of a tagger (`txt2conllu.py --morfeusz-lemmas`) or as input to Concraft (section 5). |
| **Morfeusz2 + Concraft-pl** | Usable via the flat format (`concraft/concraft_tag.py`). |
| **spaCy `pl_core_news_lg`** | Usable after conversion: `token.tag_` holds only the class (`SUBST`, `ADJ` …), so the tag has to be rebuilt from `token.morph` (`termopl/spacy2flat.py`). |

Scripts written for this (all in `termopl/`, run with the main venv python):

- `txt2conllu.py IN_DIR OUT_DIR [--no-depparse] [--morfeusz-lemmas]`: Stanza, models from `resources/tools/stanza_resources`, no network access. `--morfeusz-lemmas` replaces a Stanza lemma by the Morfeusz2 lemma when exactly one Morfeusz lemma is compatible with the tag Stanza chose (gerunds are left alone).
- `conllu2flat.py IN_DIR OUT_DIR`: CoNLL-U to flat `form<TAB>lemma<TAB>tag`.
- `spacy2flat.py IN_DIR OUT_DIR`: spaCy to flat format.
- `run_termopl.sh TXT_DIR WORK_DIR OUT_TSV [MAX_LEN=4] [CONTRAST]`: the whole chain, see 2.5.

Why the Morfeusz lemma check matters. On the 402-token test corpus Stanza produced these lemmas (log of `txt2conllu.py --morfeusz-lemmas`):

```
lemma chloroplastach: chloroplasta -> chloroplast
lemma fotosyntezy: fotosyntez -> fotosynteza
lemma dwutlenek: dwutlenka -> dwutlenek
lemma glukoza: glukoze -> glukoza
lemma błonę: błońa -> błona
lemma błonie: błoń -> błona
lemma cytoplazmy: cytoplazm -> cytoplazma
lemma utleniana: utlenieć -> utleniać
```

18 of 402 lemmas were replaced. Without the check TermoPL splits one term into several rows (`test/out/stanza_lemmas_gt.txt`):

```
1	1	dwutlenka węgiel	[dwutlenek węgla]	4.0	2	4	0	0
8	3	dwutlenek węgiel	[dwutlenek węgla]	2.0	2	3	1	1
6	3	błona komórkowy	[błona komórkowa]	2.0	2	3	1	1
12	3	błońa komórkowy	[błonę komórkowa]	2.0	2	2	0	0
```

With the check (`test/out/morf_lemmas_gt.txt`) these are single rows: `dwutlenek węgiel` 6.0 (freq 7), `błona komórkowy` 5.0 (freq 6).

### 2.2 Batch mode and options (manual section 7, `BatchParameters.java`, tested)

```
java [JVM options] -jar TermoPL.jar [program options] file...
```

Any argument switches the program to batch mode (no GUI). Everything after the first non-option argument is treated as an input file or directory. Options can also be put in a file given with `-conf FILE` (one option per line, input paths as `-in PATH`); command-line options win.

| Purpose | Option | Notes (tested unless marked) |
|---|---|---|
| Output: text table | `-exp FILE` | UTF-8, tab-separated, **no header line** |
| Output: binary term set | `-out FILE.trm` | can be reused as input or as contrastive set |
| Output: all forms / sentences / groups | `-expf FILE`, `-exps FILE`, `-expg FILE.xml` | `-expg` not tested |
| Columns of `-exp` | `-save "# rank sf bf cvalue comp length freq_s freq_in context"` | one quoted argument; columns are always written in this fixed order whatever order you list |
| Simplified forms only | `-sf` | no base (nominative) forms |
| Multi-word terms only | `-mw` | keeps length >= 2 |
| Top-ranked only | `-tr N` | keeps terms with **rank <= N**, not N rows (`-tr 10` gave 58 rows on the test corpus because of ties) |
| Sorting | `-sort COL` (ascending), `-SORT COL` (descending) | `rank`, `term`, `cvalue`, `comp`, `length`, `freq_s`, `freq_in`, `context`; not tested |
| Extraction method | `-method gt` (grammar templates, default) or `-method ud` (UD trees) | `ud` needs HEAD/DEPREL, i.e. Stanza depparse |
| Nested-phrase search (C-value variant) | `-srch npmi1\|npmi2\|npmi3\|nonpmi1\|nonpmi2` | default `npmi3`; `nonpmi1` = all sub-phrases, `nonpmi2` = trim left to right |
| NPMI preference factor | `-pf N` | default 120; not tested |
| Context counting for C-value | `-cntx 1\|2\|3` | default 1 (max of distinct left and right contexts) |
| Stop words | `-SW` (bundled `termopl_sw.txt`) or `-sw FILE` | without either, no stop-word filtering |
| Compound prepositions | `-CP` or `-cp FILE` | |
| Common (general) terms | `-CT` or `-ct FILE` | |
| Custom grammar / tagset | `-grammar FILE`, `-tagset FILE` | examples in `languages/pl/`; not tested |
| Contrastive corpus | `-comp FILE` + `-cc ll\|tfitf\|csmw\|tw\|no` | FILE is a `.trm` or a text export of another run (3, 8, 9 or 10 columns); adds the `comp` column. The manual prints `csmv`, the program only accepts `csmw` (`Bad option: -cc csmv`). |
| Contrastive thresholds | `-frq` (frequencies instead of C-values), `-freq N`, `-cval X` | not tested |
| Determiners (UD method) | `-det include\|exclude\|article`, `-detr N` | not tested |
| Case | `-ignc yes\|no` | default yes |
| WordNet grouping | `-wdn plwordnet.xml`, `-group` | not tested; needs the plWordNet XML |
| Workspace for relative paths | `-wrk DIR` | not tested |
| Language | `-lang pl` | default `pl` |
| Python for plain text | `-python PATH` | accepted but ignored in 8.1.1 (2.4) |

**There is no option for maximum term length.** `Bad option: -maxlen` is what an invented option returns. A min/max length filter exists only in the GUI's Terms window (`Preferences.minLength = 2`, `maxLength = -1`, applied only together with "multi-word terms only"). The cap therefore has to be applied to the exported table using the `length` column. Longer phrases are still found and still count as contexts for their nested sub-phrases, which is how C-value is meant to work.

C-value as implemented (manual 3.1): `C(p) = l(p) * (f(p) - (1/|LP|) * sum f(lp))` if p is nested in other phrases, else `l(p) * f(p)`; `l(p) = log2(length)` for multi-word terms and `0.1` for one-word terms.

Output columns of `-exp` (from `TermoPLDocument.exportResults`):

| # | Column | `-save` key |
|---|---|---|
| 1 | row number | `#` |
| 2 | rank (ties share a rank) | `rank` |
| 3 | simplified form (lemmas), e.g. `dwutlenek węgiel` | `sf` |
| 4 | base form in square brackets, e.g. `[dwutlenek węgla]` (no brackets if `sf` is not exported) | `bf` |
| 5 | C-value | `cvalue` |
| (6) | contrastive coefficient, only with `-comp` | `comp` |
| 6 | length in words | `length` |
| 7 | frequency | `freq_s` |
| 8 | frequency as nested phrase | `freq_in` |
| 9 | number of contexts | `context` |

### 2.3 Working command and result

Test corpus: `termopl/test/txt/biologia_01.txt`, `biologia_02.txt` (5 paragraphs, 402 tokens, written for this test: fotosynteza, błona komórkowa, układ krwionośny, wymiana gazowa, oddychanie komórkowe).

Tagging (Stanza on CPU: model load 1.4 s, then 0.3–0.4 s per file):

```
cd resources/tools/termopl
. ../../../.venv/bin/activate
python txt2conllu.py --no-depparse --morfeusz-lemmas test/txt test/work/conllu
```

TermoPL (must be started from its own directory):

```
cd resources/tools/termopl/TermoPL_Mac_OS_X
java -Djava.awt.headless=true -Xmx1500M -jar TermoPL.jar \
  -SW -CP -CT -method gt -srch npmi3 -cntx 1 \
  -save "# rank sf bf cvalue length freq_s freq_in context" \
  -exp /Users/michalpalinski/kompetencje_jezykowe/resources/tools/termopl/test/work/terms_all.tsv \
  /Users/michalpalinski/kompetencje_jezykowe/resources/tools/termopl/test/work/conllu
```

Runtime: 0.32 s wall (0.87 s user) for 2 files / 402 tokens; exit status 0; nothing printed. 127 rows. First 20 lines of the output:

```
1	1	dwutlenek węgiel	[dwutlenek węgla]	6.0	2	7	1	1
2	2	błona komórkowy	[błona komórkowa]	5.0	2	6	1	1
3	3	wymiana gazowy	[wymiana gazowa]	4.0	2	4	0	0
4	4	układ krwionośny	[układ krwionośny]	3.0	2	4	1	1
5	4	oddychanie komórkowy	[oddychanie komórkowe]	3.0	2	3	0	0
6	4	pęcherzyk płucny	[pęcherzyk płucny]	3.0	2	4	1	1
7	5	układ oddechowy	[układ oddechowy]	2.0	2	2	0	0
8	5	komórka zwierzęcy	[komórka zwierzęca]	2.0	2	2	0	0
9	5	związek organiczny	[związek organiczny]	2.0	2	2	0	0
10	5	naczynie krwionośny	[naczynie krwionośne]	2.0	2	2	0	0
11	5	komórka roślinny	[komórka roślinna]	2.0	2	2	0	0
12	5	białko błonowy	[białko błonowe]	2.0	2	2	0	0
13	6	lewy komora serce	[lewa komora serca]	1.584962500721156	3	1	0	0
14	6	udział energia świetlny	[udział energii świetlnej]	1.584962500721156	3	1	0	0
15	6	mały obieg krew	[mały obieg krwi]	1.584962500721156	3	1	0	0
16	6	ściana pęcherzyk płucny	[ściana pęcherzyków płucnych]	1.584962500721156	3	1	0	0
17	6	prawy komora serce	[prawa komora serca]	1.584962500721156	3	1	0	0
18	6	faza ciemny fotosynteza	[faza ciemnej fotosyntezy]	1.584962500721156	3	1	0	0
19	6	stężenie dwutlenek węgiel	[stężenie dwutlenku węgla]	1.584962500721156	3	1	0	0
20	6	błona komórkowy zbudować	[błona komórkowa zbudowana]	1.584962500721156	3	1	0	0
```

Length distribution of the 127 rows: 63 one-word, 48 two-word, 15 three-word, 1 four-word. The test corpus contains no term longer than 4 words, so the cap of 4 removes nothing here; with a cap of 2 the filter keeps 111 rows, which confirms that it works.

Other runs kept in `termopl/test/out/`:

| File | Command difference | Rows |
|---|---|---|
| `stanza_lemmas_gt.txt` | input `test/conllu` (Stanza lemmas unchanged) | 134 |
| `morf_lemmas_gt.txt` | input `test/conllu_morf` | 127 |
| `morf_lemmas_gt_mw.txt` | `-mw` | 64 |
| `morf_lemmas_ud.txt` | `-method ud` | 129 |
| `flat_stanza_gt.txt` | flat-format input from `conllu2flat.py` | 127, same rows as CoNLL-U input |
| `flat_spacy_gt.txt` | flat-format input from `spacy2flat.py` | 132 |
| `contrast.trm`, `contrast_terms.txt` | `-out`/`-exp` on `test/contrast_conllu` (one general-language text) | 58 |
| `domain_vs_contrast_ll.txt` | `-comp test/out/contrast.trm -cc ll` | 127, extra column 6 |
| `terms_max4.tsv` | output of `run_termopl.sh` (header added, brackets removed) | 127 |

On the contrastive run: the two tiny corpora share no terms, so every log-likelihood value is `-Infinity` (and `Infinity` for `csmw`); `tfitf` and `tw` give finite numbers. The option works mechanically; the numbers only become meaningful with a real contrastive corpus. Passing the `.trm` or the text export as `-comp` gives byte-identical output.

### 2.4 Pitfalls found while testing

1. **Start it from `TermoPL_Mac_OS_X/`.** `libjmorfeusz.dylib` loads `libmorfeusz2.dylib` by bare name, which macOS resolves against the current directory. From any other directory (with or without `-Djava.library.path=<app dir>`) you get `java.lang.UnsatisfiedLinkError: no jmorfeusz in java.library.path`, **exit status 0**, and an output file with wrong content (rank 0, unsorted, different C-values). `-sf` (simplified forms only) fails the same way from another directory. Always check stderr.
2. **Plain-text input does not work in batch mode.** `-python PATH` is parsed but never passed on (`BatchParameters.python` is not referenced by any other class in the 8.1.1 jar; checked with `javap`). Result: `Python interpreted not selected.`, exit status 0, empty output. Workaround: tag first, pass `.conllu`. This is also preferable because the bundled `parse.py` calls `stanza.download()` on every run.
3. **A directory argument is read recursively and every file in it is used**, including `.DS_Store` or leftover `.txt` files. An unrecognised file triggers pitfall 2 and the whole run yields an empty output. Keep the input directory clean (only `.conllu`).
4. **Wildcards are not expanded by the program** (`File does not exist -- …/*.conllu` followed by a `NullPointerException`). Give a directory, or let the shell expand the pattern (do not quote it).
5. **Row order among ties is not stable** between a directory argument and a shell-expanded file list (same rows, same values, different order inside a rank). Repeated runs with the same argument are byte-identical. Sort downstream by C-value and term if a stable order is needed.
6. **`~/.TermoPL-8`**: if the GUI is ever started it saves its preferences there, and batch mode loads that file first. It does not exist on this machine. Settings that batch mode does not override (for example the min/max length used with `-mw`) would then come from the GUI.
7. Stanza lemmatises gerunds as nouns (`oddychanie`), Morfeusz/Concraft/spaCy as infinitives (`oddychać`). TermoPL prints the right base form in both cases, but mixing the conventions in one corpus splits terms. `txt2conllu.py --morfeusz-lemmas` therefore never touches gerunds.

### 2.5 Batch run on a directory of text files with a 4-word cap

```
cd resources/tools/termopl
./run_termopl.sh /path/to/txt_dir /path/to/work_dir /path/to/terms_max4.tsv 4
# optional 5th argument: contrastive term set (.trm or text export), adds comp_ll
```

Verified on the test corpus: 3.8 s wall in total, output `all terms: 127  kept (length <= 4): 127`. The script tags with Stanza (`--no-depparse --morfeusz-lemmas`), runs the command from 2.3 from inside `TermoPL_Mac_OS_X/`, fails loudly if stderr contains an exception or the output is empty, then keeps rows with `length <= 4`, strips the brackets from the base form and adds a header (`nr rank simplified_form base_form cvalue length freq_s freq_in contexts`). It also writes `work_dir/terms.trm` (reusable as a contrastive set for another run) and `work_dir/terms_all.tsv` (unfiltered).

The filter itself, if you run TermoPL by hand with the `-save` list above (length is column 6, or column 7 when `-comp` is used):

```
awk -F'\t' '$6 <= 4' terms_all.tsv > terms_max4.tsv
```

Memory: the manual states about 1 GB of RAM per 500,000 tokens and suggests `-Xmx5G -Xms4G` for much larger corpora. Not measured here.

---

## 3. spaCy

### 3.1 `pl_core_news_lg` 3.8.0 (installed)

```
. .venv/bin/activate
python -m spacy download pl_core_news_lg
```

```
Collecting pl-core-news-lg==3.8.0
  Downloading pl_core_news_lg-3.8.0-py3-none-any.whl (573.7 MB)
Successfully installed pl-core-news-lg-3.8.0
✔ Download and installation successful
```

1 min 21 s. Source: `https://github.com/explosion/spacy-models/releases/download/pl_core_news_lg-3.8.0/pl_core_news_lg-3.8.0-py3-none-any.whl`. On disk 611 MB. `python -m spacy validate` reports it compatible (`>=3.8.0,<3.9.0`, spaCy 3.8.18).

From the installed `meta.json`:

```
version = 3.8.0
spacy_version = >=3.8.0,<3.9.0
license = GNU GPL 3.0
author = Explosion
pipeline = ['tok2vec', 'morphologizer', 'parser', 'lemmatizer', 'tagger', 'attribute_ruler', 'ner']
vectors = {'width': 300, 'vectors': 500000, 'keys': 500000, 'name': 'pl_vectors', 'mode': 'default'}
sources:
  UD Polish PDB v2.8 – license 'GNU GPL 3.0'
  National Corpus of Polish – license 'GNU GPL 3.0'
  Explosion fastText Vectors (cbow, OSCAR Common Crawl + Wikipedia) – license 'CC0'
```

Smoke test (load 1.5 s):

```
Błona	błona	NOUN	SUBST	Case=Nom|Gender=Fem|Number=Sing	nsubj
komórkowa	komórkowy	ADJ	ADJ	Case=Nom|Degree=Pos|Gender=Fem|Number=Sing	amod
oddziela	oddzielać	VERB	FIN	Aspect=Imp|Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act	ROOT
wnętrze	wnętrze	NOUN	SUBST	Case=Acc|Gender=Neut|Number=Sing	obj
komórki	komórka	NOUN	SUBST	Case=Gen|Gender=Fem|Number=Sing	nmod
od	od	ADP	PREP	AdpType=Prep|Variant=Short	case
środowiska	środowisko	NOUN	SUBST	Case=Gen|Gender=Neut|Number=Sing	nmod
zewnętrznego	zewnętrzny	ADJ	ADJ	Case=Gen|Degree=Pos|Gender=Neut|Number=Sing	amod
.	.	PUNCT	SUBST	PunctType=Peri	punct
```

Note the final full stop: `tag_` is `SUBST` (the model's output; `pos_` is correct). `spacy2flat.py` forces `interp` for punctuation.

### 3.2 IPI PAN models: not compatible, not installed

Evidence was read from the packages' own metadata (archives streamed, nothing stored).

| Package | Source | Requirement found | Why it cannot go into the main venv |
|---|---|---|---|
| `pl_spacy_model` 0.1.0 | <https://zil.ipipan.waw.pl/SpacyPL> | `meta.json`: `spacy_version '>=2.2.2'`, pipeline `tagger, parser, ner`; repository README: "Spacy in a version `== 2.2.4`" | spaCy 2.x model format; spaCy 2.2.4 has wheels only for cp36–cp38, none for macOS arm64 |
| `pl_spacy_model_morfeusz` 0.1.3 | same page | `setup.py`: `install_requires=['spacy==2.3.2', 'distance', 'keras==2.4.3', 'numpy', 'tensorflow==2.3.1']` | spaCy 2.3.2 has wheels only for cp36–cp38, none for macOS arm64 |
| `pl_nask` 0.0.7 (453 MB) | <https://mozart.ipipan.waw.pl/~rtuora/spacy/> | `meta.json`: `spacy_version '>=3.5.0,<3.6.0'`, `requirements ['spacy-transformers>=1.1.5,<1.2.0']`, pipeline `transformer, tagger, morphologizer, parser, ner, morfeusz` | conflicts with spaCy 3.8.18; spaCy 3.5.4 has no cp312 wheel (cp36–cp311 only) |

Licence: `pl_spacy_model*` are GNU GPL 3.0 (`meta.json` and the README of <https://github.com/ipipan/spacy-pl>, last push 2022-08-22). `pl_nask` has an empty `license` field in `meta.json` ("License: n/a" in its README); a GPL v3 text `LICENSE.txt` lies in the same download directory. That is not an explicit licence statement for the model.

Not attempted: spaCy 3.5.4 does have macOS arm64 wheels for Python 3.10 and 3.11, so `pl_nask` might install in a separate conda environment. That would be a second spaCy installation and a 453 MB download.

---

## 4. Stanza Polish models

```
. .venv/bin/activate
export STANZA_RESOURCES_DIR=$PWD/resources/tools/stanza_resources
python -c "import stanza, os; stanza.download('pl', model_dir=os.environ['STANZA_RESOURCES_DIR'])"
```

```
Downloaded file to …/resources/tools/stanza_resources/resources.json   (resources_1.15.0.json)
Downloading default packages for language: pl (Polish) ...
Downloaded file to …/resources/tools/stanza_resources/pl/default.zip
Finished downloading models and saved to …/resources/tools/stanza_resources
```

25 s. `pl/default.zip` (416,036,108 bytes) was deleted after unpacking; a second copy stayed in `~/.cache/huggingface` (section 1). Models come from `https://huggingface.co/stanfordnlp/stanza-pl` (resources version 1.15.0).

Default package for `pl` according to `resources.json`: treebank **PDB** (UD_Polish-PDB), NER from NKJP.

| Processor | Model | File | Size |
|---|---|---|---|
| tokenize | `pdb_nocharlm` | `pl/tokenize/pdb_nocharlm.pt` | 0.6 MB |
| mwt | `pdb` | `pl/mwt/pdb.pt` | 0.5 MB |
| pos | `pdb_charlm` | `pl/pos/pdb_charlm.pt` | 36 MB |
| lemma | `pdb_nocharlm` | `pl/lemma/pdb_nocharlm.pt` | 2.6 MB |
| depparse | `pdb_charlm` | `pl/depparse/pdb_charlm.pt` | 148 MB |
| ner | `nkjp` | `pl/ner/nkjp.pt` | 92 MB |
| pretrain | `conll17` | `pl/pretrain/conll17.pt` | 102 MB |
| charlm | `oscar` forward/backward | `pl/{forward,backward}_charlm/oscar.pt` | 27 MB each |

Total 436 MB. Other packages listed for `pl` but not downloaded: `lfg`, `mpdt`, and HerBERT variants (`pdb_herbert`).

Licence: Stanza code Apache-2.0 (<https://raw.githubusercontent.com/stanfordnlp/stanza/main/LICENSE>). The model card <https://huggingface.co/stanfordnlp/stanza-pl> declares `license: apache-2.0`. See section 7 for the treebank licence.

Smoke test (`processors='tokenize,mwt,pos,lemma'`, `download_method=None`, CPU; load 1.8 s, sentence 0.08 s):

```
1	Fotosynteza	fotosynteza	NOUN	subst:sg:nom:f	Case=Nom|Gender=Fem|Number=Sing
2	zachodzi	zachodzić	VERB	fin:sg:ter:imperf	Aspect=Imp|Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act
3	w	w	ADP	prep:loc:nwok	AdpType=Prep|Variant=Short
4	chloroplastach	chloroplasta	NOUN	subst:pl:loc:m3	Animacy=Inan|Case=Loc|Gender=Masc|Number=Plur
5	komórek	komórka	NOUN	subst:pl:gen:f	Case=Gen|Gender=Fem|Number=Plur
6	roślinnych	roślinny	ADJ	adj:pl:gen:f:pos	Case=Gen|Degree=Pos|Gender=Fem|Number=Plur
7	,	,	PUNCT	interp	PunctType=Comm
8	gdzie	gdzie	ADV	adv	PronType=Rel
9	chlorofil	chlorofil	NOUN	subst:sg:nom:m3	Animacy=Inan|Case=Nom|Gender=Masc|Number=Sing
10	pochłania	pochłaniać	VERB	fin:sg:ter:imperf	Aspect=Imp|Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act
11	światło	światło	NOUN	subst:sg:acc:n:ncol	Case=Acc|Gender=Neut|Number=Sing
12	.	.	PUNCT	interp	PunctType=Peri
```

To use the models without any network access or cache writes:

```python
stanza.Pipeline('pl', dir='resources/tools/stanza_resources', processors='tokenize,mwt,pos,lemma',
                download_method=None, use_gpu=False)
```

---

## 5. Concraft-pl

Sources: <https://zil.ipipan.waw.pl/Concraft> (page last edited 2022-02-22), <https://github.com/kawu/concraft-pl> (last push 2021-04-06, no GitHub releases).

| Option | Finding |
|---|---|
| **Prebuilt macOS binary** | Exists: `Concraft-MacOSX.zip` on the IPI PAN page (4.0 MB; one file `concraft-pl`, 17.3 MB, dated 2020-05-14, `Mach-O 64-bit executable x86_64`, `Concraft-pl 2.5.0`). No arm64 build. It runs here because Rosetta 2 is already installed (`arch -x86_64 /usr/bin/true` succeeds). Links only against system libraries. **Installed and working.** |
| Build from source | Needs the Haskell Tool Stack (`stack install`). Not attempted (no Haskell toolchain, long compilation). |
| pip package | None: `https://pypi.org/pypi/concraft-pl/json` and `…/concraft-pl2/json` return 404. The repository has a Python client (`bindings/python`) that only talks to a running `concraft-pl server`. |
| IPI PAN Multiservice | <https://zil.ipipan.waw.pl/Multiservice> documents a Thrift service (`multiservice.nlp.ipipan.waw.pl:20000`) and a SOAP WSDL. Today: `http://multiservice.nlp.ipipan.waw.pl/` returns 404, the WSDL URL returns 404, port 20000 does not accept connections. Not usable. |
| Morfeusz web demo | <https://morfeusz.sgjp.pl/demo/> has a "Tagowanie (Concraft-pl)" tab; interactive form, maximum 3000 characters, no API documented on the page. Not suitable for a corpus. |
| CLARIN-PL services | <https://wiki.clarin-pl.eu/pl/nlpservices/first-steps>: use requires a CLARIN-PL user account. Programmatic access through the `lpmn_client_biz` Python library or the LPMN CLI tool, authenticated with CLARIN-PL username/password or an API token (<https://wiki.clarin-pl.eu/pl/nlpservices/lpmn-client>). The "Postagger" service (<https://wiki.clarin-pl.eu/pl/nlpservices/list/postagger>) returns NKJP tags and lemmas; the wiki page does not say which tagger it runs, so it is not known to be Concraft. Not tried: needs an account, and the texts would be sent to an external server. No terms-of-use page was found on the pages read. |

Installed files (`resources/tools/concraft/`):

```
curl -L -o Concraft-MacOSX.zip "https://zil.ipipan.waw.pl/Concraft?action=AttachFile&do=get&target=Concraft-MacOSX.zip"                               # 4,024,213 bytes
curl -L -o concraft-pl-model-SGJP-20220221.gz "https://zil.ipipan.waw.pl/Concraft?action=AttachFile&do=get&target=concraft-pl-model-SGJP-20220221.gz"   # 84,150,136 bytes, 76 s
curl -L -o format-examples.zip "https://zil.ipipan.waw.pl/Concraft?action=AttachFile&do=get&target=format-examples.zip"
unzip Concraft-MacOSX.zip && chmod +x concraft-pl
```

SHA-256: binary `a2fbe4afa051230b06658c09bafff269c81b9138f7fb8e49a54a5eedab903ceb`, model `55cbdd4a42705210201eba00d1dfdb1f74038e33bfdb1f07a92b94bd180837fe`.
The page says this model is "for Morfeusz 1.99.5 (2022/02/20) and newer"; the venv has Morfeusz 1.99.15 with dictionary `pl.sgjp.sgjp-2026.06.01`.

Licence: Concraft-pl code BSD 2-clause, "Copyright (c) 2013 Jakub Waszczuk" (<https://raw.githubusercontent.com/kawu/concraft-pl/master/LICENSE>). **The page states no licence for the model file** ("trained on NKJP1M-SGJP … financed by CLARIN-PL"), and no licence for the prebuilt binaries beyond that of the source.

Working pipeline (main venv python; Morfeusz2 analysis, Concraft disambiguation, flat file for TermoPL):

```
cd resources/tools/concraft
. ../../../.venv/bin/activate
python concraft_tag.py ../termopl/test/txt test/work test/flat
```

```
biologia_01.txt: 163 tokens, concraft 5.9s
biologia_02.txt: 239 tokens, concraft 4.1s
```

10 s in total; almost all of it is loading the model once per file (the binary also has a `server` mode that loads it once; not tested). The tagging command inside the script is `./concraft-pl tag concraft-pl-model-SGJP-20220221.gz -i X.dag -o X.tagged.dag`.

Input DAG format (one line per Morfeusz interpretation, 11 tab-separated columns, blank line after each paragraph): start node, end node, form, lemma, tag, commonness, qualifiers, probability (`0.0`), interpretation meta, eos, segment meta. The output adds the probability, `eos` in column 10 at sentence ends, and `disamb` in column 12 on the chosen interpretation. Example from the test run:

```
4	5	w	w	prep:acc:nwok			0.0000
4	5	w	w	prep:loc:nwok			1.0000				disamb
```

Concraft does not lemmatise: when several lemmas share the chosen tag, all are marked `disamb` (2 of 402 segments here: `Ściana:Sf`/`ściana`, `stężeć`/`stężyć`). `concraft_tag.py` takes the first lemma that starts with a lower-case letter.

TermoPL on the Concraft output (`concraft/test/out/terms_concraft.txt`, 128 rows) gives the same top 12 rows as the Stanza-based run. One difference further down: `różnica stężeć gazy [różnica stężeń gazów]`, where Concraft chose a gerund reading for "stężeń".

---

## 6. COMBO and KRNNT (optional)

### 6.1 COMBO

Two different packages exist:

- **Legacy COMBO 1.0.7** (<https://gitlab.clarin-pl.eu/syntactic-tools/combo>, `master` branch `setup.py`; mirror <https://github.com/ipipan/combo>, last push 2021-01-20, GPL-3.0). Pins `allennlp==1.3.0`, `torch==1.7.1`, `spacy==2.3.2`, `transformers==4.0.1`, `numpy==1.22.0`, `scipy==1.6.0`, `scikit-learn==0.23.2`. Not installable on Python 3.12 arm64; not attempted.
- **`combo-nlp` 4.0.14** on PyPI (uploaded 2026-10-18; `requires_python >=3.10`; licence expression GPL-3.0; homepage `https://gitlab.clarin-pl.eu/syntactic-tools/combo-nlp`). Requires `torch>=2.0.0`, `transformers>=4.35.0`, `peft`, `wandb`, `accelerate`, `combo-seg>=0.1.1` and others. **Installed in a separate venv and run.**

```
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv resources/tools/combo/venv
. resources/tools/combo/venv/bin/activate
pip install --no-cache-dir combo-nlp==4.0.14      # 47 s, 205 MB of wheels, venv 1.0 GB
```

Installed among others: `torch-2.15.0`, `transformers-5.22.2`, `numpy-2.5.4`, `combo-seg-0.1.6`, `wandb-0.31.0` (which pulls `cwevals-0.0.1b1`, the CoreWeave Evaluations API client). The main venv was not touched.

Smoke test:

```
cd resources/tools/combo && . venv/bin/activate
export HF_HOME=$PWD/hf_cache HF_HUB_DISABLE_TELEMETRY=1 WANDB_MODE=disabled TOKENIZERS_PARALLELISM=false
python - <<'EOF'
from combo import COMBO
nlp = COMBO.from_pretrained("clarin-pl/combo-nlp-xlm-roberta-base-polish-pdb-ud2.17")
for sentence in nlp("Fotosynteza zachodzi w chloroplastach komórek roślinnych, gdzie chlorofil pochłania światło. Dwutlenek węgla przenika przez błonę komórkową."):
    for token in sentence:
        print(token.form, token.lemma, token.upos, token.xpos, token.head, token.deprel, sep='\t')
EOF
```

First load 80.9 s (including the downloads), the two sentences 6.1 s on CPU. Output (feature column omitted):

```
Fotosynteza	fotosynteza	NOUN	subst:sg:nom:f	2	nsubj
zachodzi	zachodzić	VERB	fin:sg:ter:imperf	0	root
w	w	ADP	prep:loc:nwok	4	case
chloroplastach	chloroplasta	NOUN	subst:pl:loc:m3	2	obl
komórek	komórka	NOUN	subst:pl:gen:f	4	nmod
roślinnych	roślinny	ADJ	adj:pl:gen:f:pos	5	amod
,	,	PUNCT	interp	10	punct
gdzie	gdzie	ADV	adv	10	advmod
chlorofil	chlorofil	NOUN	subst:sg:nom:m3	10	nsubj
pochłania	pochłaniać	VERB	fin:sg:ter:imperf	4	acl:relcl
światło	światło	NOUN	subst:sg:acc:n:ncol	10	obj
.	.	PUNCT	interp	2	punct

Dwutlenek	dwutlenek	NOUN	subst:sg:nom:m3	3	nsubj
węgla	węgiel	NOUN	subst:sg:gen:m3	1	nmod:arg
przenika	przenika	VERB	fin:sg:ter:imperf	0	root
przez	przez	ADP	prep:acc:nwok	5	case
błonę	błona	NOUN	subst:sg:acc:f	3	obl
komórkową	komórkowy	ADJ	adj:sg:acc:f:pos	5	amod
.	.	PUNCT	interp	3	punct
```

The XPOS column is the same NKJP-style tag as Stanza's, so COMBO output could feed TermoPL the same way (not run). Two lemmas in this sample are wrong (`chloroplasta`, `przenika`).

Models fetched on first use (3.36 GB in total, **deleted again** to respect the disk budget; they are re-downloaded automatically into `$HF_HOME` on the next run):

| Hugging Face repository | File | Bytes | Licence on the model card |
|---|---|---|---|
| `clarin-pl/combo-nlp-xlm-roberta-base-polish-pdb-ud2.17` | `pytorch_model.bin` | 1,134,134,447 | cc-by-nc-sa-4.0 |
| `clarin-pl/combo-seg-xlm-roberta-base-polish-pdb-ud2.17` | `pytorch_model.bin` | 1,114,773,902 | cc-by-nc-sa-4.0 |
| `FacebookAI/xlm-roberta-base` | `model.safetensors` | 1,115,567,652 | mit |

Whether the third file is needed at every load or only fetched once was not investigated.

**Licence flag:** the Polish COMBO models are CC BY-NC-SA 4.0 (non-commercial, share-alike). Whether that is acceptable for this project is a decision for the project owner.

### 6.2 KRNNT

<https://github.com/kwrobel-nlp/krnnt> (last push 2023-05-22, LGPL-3.0, <https://raw.githubusercontent.com/kwrobel-nlp/krnnt/master/LICENSE>). Not on PyPI (`https://pypi.org/pypi/krnnt/json` returns 404). Not installed. Reasons:

- `setup.py` (version 1.0.0) pins `Keras==2.2.5` and, as extras, `tensorflow==1.14.0` / `tensorflow-gpu==1.12.0`; `requirements.txt` pins `numpy==1.16.4`, `h5py==2.9.0`.
- TensorFlow 1.14.0 on PyPI has wheels only for cp27 and cp33–cp37, on `macosx_10_11_x86_64`, `manylinux1_x86_64`, `win_amd64`. Nothing for Python 3.12 or arm64. h5py 2.9.0 stops at cp38, x86_64.
- It also needs the external tools Maca and Toki (`maca-analyse -qc morfeusz2-nkjp`), which the README tells you to install by following a Dockerfile.
- The README's supported route is Docker (`docker run -p 9003:9003 -it djstrong/krnnt:1.0.0`); no Docker daemon here.

Trained models are attached to the GitHub releases (`reana.zip` 20 MB, `preana.zip` 21 MB, `reana10.zip` 146 MB); no separate model licence is stated in the README.

---

## 7. Licence flags (for a decision by the project owner)

1. **UD_Polish-PDB is CC BY-NC-SA 4.0.** Its `LICENSE.txt` and README (<https://github.com/UniversalDependencies/UD_Polish-PDB>) say so, and the README changelog records "License changed from GNU GPL 3.0 to CC BY-NC-SA 4.0" at release v2.4 (2019-05-15). All three neural pipelines' Polish models are trained on it:
   - spaCy `pl_core_news_lg` 3.8.0 declares itself GNU GPL 3.0 and lists "UD Polish PDB v2.8" with licence "GNU GPL 3.0". That does not match the treebank's own statement for v2.4 and later.
   - Stanza's `stanza-pl` model card declares Apache-2.0. The Stanza documentation page says the UD models are trained on Universal Dependencies v2.12, a release in which PDB is CC BY-NC-SA 4.0.
   - COMBO's model card says CC BY-NC-SA 4.0, consistent with the treebank.
   Whether a model inherits the licence of its training data is a legal question that this check does not answer.
2. **Concraft-pl model `concraft-pl-model-SGJP-20220221.gz`**: no licence stated on the download page.
3. **`pl_nask`**: no licence in the package metadata.
4. **GPL 3.0** (spaCy model, IPI PAN spaCy models, COMBO code) and **LGPL 3.0** (KRNNT) are copyleft licences; relevant if tools or models are redistributed.
5. TermoPL, Morfeusz2 with SGJP, and the Concraft-pl code are BSD 2-clause. Outputs of TermoPL (term lists) are not covered by any statement on the TermoPL page.

## 8. Download accounting

| Item | Bytes downloaded |
|---|---|
| TermoPL package, manual, licence, tagset, sources, languages, jars | 10.7 MB |
| `pl_core_news_lg` wheel | 573.7 MB |
| Stanza `resources.json` + `pl/default.zip` | 416.5 MB |
| Metadata checks of IPI PAN spaCy archives (streamed, nothing stored) | 116 MB measured for `pl_spacy_model_morfeusz`; `pl_spacy_model` and `pl_nask` (twice) not measured |
| Concraft binary, examples, model (plus 0.9 MB from an interrupted first attempt) | 89 MB |
| COMBO wheels | 205 MB |
| COMBO models from Hugging Face | 3,364 MB |
| **Total** | **about 4.8 GB measured, roughly 5 GB with the unmeasured streams** |
