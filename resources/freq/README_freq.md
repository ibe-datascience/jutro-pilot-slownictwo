# General-Polish word-frequency resources

Collected on **2026-11-13**. Everything below was verified by fetching the URL or reading the downloaded file on that date; numbers marked *computed* were calculated locally from the downloaded file, numbers marked *stated* are quoted from the source. Machine-readable version: `manifest.json`.

## Summary

| Resource | Status | Main file(s) | Unit | Tokens | Licence |
|---|---|---|---|---|---|
| NKJP 1-grams (balanced 300M subcorpus) | downloaded | `nkjp_1grams.gz` | form, lower-cased, punctuation attached | 246,153,378 (computed sum); "300M" (stated) | CC-BY, version not stated |
| NKJP1M 1.2 (manually annotated 1M subcorpus) | downloaded, **licence version unclear** | `NKJP-PodkorpusMilionowy-1.2.tar.gz` + 3 lists derived locally (`nkjp1m-1.2_*.tsv`) | lemma (manual), lemma × class, form | 1,215,513 segments (computed); 1,003,956 words (stated) | CC BY; 3.0 PL vs 4.0 depending on where you read |
| SUBTLEX-PL | downloaded, **restrictive licence** | `subtlex-pl-cd-3.csv`, `subtlex-pl.csv`, `subtlex-pl-lemmas-master.csv` | form (lower-cased) and lemma + POS | 145,982,416 (computed); "about 146 million" (stated) | CC BY-NC-SA 4.0 |
| KWJP100 (balanced, 2011–2020) | downloaded | `kwjp100-slowa-{lemma,orth_lc,orth}-all.csv.gz` | lemma × class, form (case-insensitive and case-sensitive) | 81.0–81.7 M listed (computed); "100 million" (stated) | CC BY 4.0 |
| wordfreq 3.1.1 (Python) | already installed, nothing downloaded | venv package data | form, case-folded | n/a (merged sources) | code Apache-2.0, data CC BY-SA 4.0 |

### Licence points that need your decision

1. **SUBTLEX-PL is non-commercial and share-alike** (CC BY-NC-SA 4.0, `subtlex-pl_license.txt`). The 2015 paper says the database is "freely available for research purposes". Anything derived from it has to carry the same licence.
2. **NKJP1M licence version is inconsistent.** The README inside the archive says CC BY 3.0 PL (its English paragraph adds "Attribution 3.0 Unported" and links to the unported 3.0 deed), nkjp.pl says CC-BY 4.0, and the CLIP download page says just "CC-BY". All three are attribution-only, but I did not pick one. The four NKJP1M entries have status `licence_unclear` in `manifest.json`; the files are present.
3. **NKJP 1-grams** are "made available on CC-BY licence" with no version number on the page.
4. **wordfreq data is share-alike** (CC BY-SA 4.0).
5. KWJP: the CC BY 4.0 statement is in the repository `README.md` only; the repository has no `LICENSE` file (GitHub API reports `license: null`).

### Verification: counts for four test words

All values read from the downloaded files.

| File | Count column | `i` | `komórka` | `fotosynteza` | `proces` |
|---|---|---|---|---|---|
| `nkjp_1grams.gz` (exact entry) | count | 5,333,210 | 1,333 | 15 | 22,118 |
| `nkjp_1grams.gz` (after stripping edge punctuation and summing variants) | count | 5,374,967 | 1,863 | 27 | 24,879 |
| `nkjp1m-1.2_lemma_freq.tsv` | freq (lemma) | 21,860 | 85 | 1 | 288 |
| `nkjp1m-1.2_orth_lc_freq.tsv` | freq (form) | 22,004 | 7 | absent | 98 |
| `subtlex-pl-cd-3.csv` and `subtlex-pl.csv` | freq (form) | 1,460,952 | 1,063 | 18 | 4,125 |
| `subtlex-pl-lemmas-master.csv` | freq (lemma row) | 1,460,952 (`i`/conj) | 7,906 | 46 | 7,769 |
| `kwjp100-slowa-lemma-all.csv.gz` | freq (lemma × class) | 1,838,568 (`i`/conj); 1,885,543 over all classes | 6,470 | 89 | 20,429 |
| `kwjp100-slowa-orth_lc-all.csv.gz` | freq (form) | 1,896,274 | 682 | 17 | 7,861 |
| `kwjp100-slowa-orth-all.csv.gz` | freq (form, case-sensitive) | 1,783,629 | 589 | 9 | 6,759 |
| wordfreq `word_frequency(w, 'pl')` | proportion | 0.0263 | 5.25e-06 | 1.74e-07 | 9.33e-05 |

---

## 1. NKJP (Narodowy Korpus Języka Polskiego)

What is downloadable today:

- A ready-made **form** frequency list: the 1-gram file from <https://zil.ipipan.waw.pl/NKJPNGrams>.
- No ready-made **lemma** frequency list was found. The pages checked were <https://zil.ipipan.waw.pl/NKJPNGrams>, <https://clip.ipipan.waw.pl/NationalCorpusOfPolish>, <https://zil.ipipan.waw.pl/DistrNKJP> and `https://nkjp.pl/index.php?page=N&lang=0` for N = 0…25. A lemma list can be derived from the manually annotated 1-million subcorpus, which is downloadable, so that was done (section 1b).
- <https://nkjp.nlp.ipipan.waw.pl/> ("NKJP 300M", re-tagged in 2020) is a query interface; its landing page offers no download link.
- <https://zil.ipipan.waw.pl/DistrNKJP> offers two redistributable subcorpora as raw corpora (`5SCAL-free.tar`, `nkjp-wikipedia.tar.gz`). They are not frequency lists and were not downloaded.

### 1a. `nkjp_1grams.gz` — form frequencies, balanced 300M subcorpus

| | |
|---|---|
| Source page | <https://zil.ipipan.waw.pl/NKJPNGrams> |
| Download URL | <https://zil.ipipan.waw.pl/NKJPNGrams?action=AttachFile&do=get&target=1grams.gz> (saved as `nkjp_1grams.gz`) |
| Downloaded | 2026-11-13 (server `Last-Modified`: 2014-12-29) |
| Size | 22,692,778 bytes (106,027,837 uncompressed) |
| sha256 | `73af49094621b2f86b594beba783c14aee8c8212f1aff3d61f281ab5d99e3dc9` |
| Format | gzip; UTF-8, no BOM, LF; no header; `<count> <unigram>`, count right-aligned with leading spaces (`uniq -c` style), sorted by descending count; 5,364,398 lines |
| Unit | **orthographic form, lower-cased**. Stated: "Each unigram is maximum continuous chunk of non-whitespace lower-case characters." |
| Corpus size | stated: balanced subcorpus of NKJP, "300M tokens"; computed: counts sum to 246,153,378 |
| Licence | stated: "NKJP ngrams are made available on CC-BY licence." (<https://zil.ipipan.waw.pl/NKJPNGrams>); no version given |

First 5 lines:

```
7692997 w
5333210 i
4235003 na
4158902 z
3981525 się
```

Caveats, checked in the file:

- Tokens are whitespace-delimited, so **punctuation stays attached**. `proces` (22,118), `proces,` (1,421) and `proces.` (926) are separate entries; `.` (93,298) and `,` (68,284) also occur as entries of their own. Mandera et al. (2015) describe handling this by "summing frequencies of all forms that were identical after removing punctuation marks attached to some of the forms". The second row of the verification table shows what that does for four words.
- No entry contains upper-case characters; 1,413,827 of the 5,364,398 entries are purely alphabetic (194,119,824 tokens).
- Parse with `line.lstrip().split(' ', 1)`. Splitting on single spaces breaks because of the padding.

### 1b. NKJP1M 1.2 — manually annotated 1-million subcorpus, and lists derived from it

**`NKJP-PodkorpusMilionowy-1.2.tar.gz`** (source corpus)

| | |
|---|---|
| Source page | <https://clip.ipipan.waw.pl/NationalCorpusOfPolish> (also linked from <https://nkjp.pl/index.php?page=14&lang=1>) |
| Download URL | <https://clip.ipipan.waw.pl/NationalCorpusOfPolish?action=AttachFile&do=get&target=NKJP-PodkorpusMilionowy-1.2.tar.gz> |
| Downloaded | 2026-11-13 (server `Last-Modified`: 2021-07-08) |
| Size | 170,796,368 bytes |
| sha256 | `1ad87f5a653bf30c986bd791fa64d0b93989f8056887dbc28957596747ef953e` |
| Format | tar.gz; TEI P5 XML, UTF-8; 3,889 sample directories, each with `ann_morphosyntax.xml` (segments with `orth`, candidate interpretations and the manually chosen one) |
| Corpus size | stated in `statystyki.txt`: "Słów razem: 1003956"; computed: 1,215,513 segments, of which 223,499 are punctuation (`interp`), leaving 992,014 |
| Licence | **inconsistent version, see below** |

Licence statements found:

- `README` inside the archive: "Podkorpus dostępny jest na licencji CC BY 3.0 PL (Uznanie autorstwa 3.0 Polska). Więcej informacji: https://creativecommons.org/licenses/by/3.0/pl/." Its English paragraph reads "available on CC BY 3.0 PL licence (Attribution 3.0 Unported). More information: https://creativecommons.org/licenses/by/3.0/."
- <https://clip.ipipan.waw.pl/NationalCorpusOfPolish>: "available on CC-BY licence (NKJP tagset)".
- <https://nkjp.pl/index.php?page=14&lang=1>: "available on CC-BY 4.0".
- `NKJP_1M_header.xml` inside the archive: "available publicly for free".

The archive is kept so the lists can be re-derived. It can be deleted (171 MB) if you only need the lists.

**Derived lists** (not published files; produced by `derive_nkjp1m_freq.py` in this directory, which streams the archive without extracting it)

| File | Bytes | sha256 | Columns | Rows |
|---|---|---|---|---|
| `nkjp1m-1.2_lemma_ctag_freq.tsv` | 1,175,401 | `440b2159b9634d20830bb12e7229093b0c4d1449e5d3c410e600f9edda9d7858` | `lemma`, `ctag`, `freq` | 69,419 |
| `nkjp1m-1.2_lemma_freq.tsv` | 628,402 | `72d8f89973bebc0f4555106c25279efc5bacd534f4b70592911b69c4726c586e` | `lemma`, `freq` | 54,168 |
| `nkjp1m-1.2_orth_lc_freq.tsv` | 1,566,326 | `9703a38f7870de22dc201a7b76e5982eedf78ef5f418529e268a8bd294083f7f` | `orth_lc`, `freq` | 126,752 |

Format: TSV, UTF-8, LF, header row, sorted by descending frequency. Each file sums to 1,215,513.

How the counts are made:

- The unit counted is one NKJP segment (`<seg>`). Punctuation is its own segment, and so are agglutinates such as `em` in `zrobiłem`.
- The lemma and class are the **manually disambiguated** ones: the `choice` pointer in `<f name="disamb">` is resolved to its `<fs type="lex">` (`base`, `ctag`). All 1,215,513 segments resolved this way.
- Lemma case is kept as annotated, so proper names are capitalised. `orth_lc` is the segment lower-cased.
- Nothing is filtered: punctuation, numbers and foreign strings are included. The only normalisation is trimming and collapsing whitespace inside a segment's form and lemma, needed because one URL segment contains a TAB.
- In the NKJP tagset verb forms belong to separate classes (`fin`, `praet`, `inf`, `ger`, `ppas`, …), so one verb is spread over several rows of the lemma × ctag file; the lemma-only file sums them, and also merges homonyms of different classes.

First 5 lines of each:

```
# nkjp1m-1.2_lemma_ctag_freq.tsv
lemma	ctag	freq
.	interp	90945
,	interp	70307
w	prep	31618
i	conj	21308

# nkjp1m-1.2_lemma_freq.tsv
lemma	freq
.	90945
,	70307
w	31623
być	28381

# nkjp1m-1.2_orth_lc_freq.tsv
orth_lc	freq
.	90945
,	70309
w	31387
i	22004
```

With one million words the list is coarse for rare vocabulary: `fotosynteza` occurs once as a lemma.

---

## 2. SUBTLEX-PL (Mandera, Keuleers, Wodniecka & Brysbaert, 2015)

Where it is today:

- `http://crr.ugent.be/subtlex-pl` (the URL given in the paper) redirects to https and returns **HTTP 404**. <https://crr.ugent.be/> shows a notice that the website was removed and is "under reconstruction", with a pointer to the Internet Archive.
- The files are on **OSF**: <https://osf.io/5a76z/> (project "SUBTLEX-PL", contributor Marc Brysbaert, created 2023-12-18). The project wiki says: "These files are the same as the ones referred to in the article."
- All files below were downloaded from OSF on 2026-11-13, and each local sha256 equals the hash reported by the OSF API.

Licence: the OSF licence field is "Other" with the text "Please see the file named license.txt in the OSF Storage of this project." That file (<https://osf.io/qra8w/>, saved as `subtlex-pl_license.txt`) says:

> The materials on this website is subject to the following CC license: CC BY-NC-SA 4.0, Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

The paper's abstract says "The database is freely available for research purposes".

Corpus (stated in the paper, a copy of which is in the OSF project): 27,767 subtitle files after de-duplication, "about 146 million tokens (individual strings, including punctuation marks, numbers, etc.), out of which 101 million tokens (449,300 types) were accepted as correctly spelled Polish words" by Aspell. "All words were converted to lowercase before spell-checking." Lemmas and POS come from automatic tagging with TaKIPI and Morfeusz.

| File | OSF URL | Bytes | sha256 |
|---|---|---|---|
| `subtlex-pl-cd-3.csv` | <https://osf.io/download/qnjpx/> | 82,602,912 | `7f944a4b65f399e70410ccddbca56cb96ad59bbe318f2ba3a0330c374da2e1fc` |
| `subtlex-pl.csv` | <https://osf.io/download/z65qb/> | 211,854,502 | `3f23f98aa99074a17d866aa626dc8ed31a6368d43affea89b0403d1e248bad06` |
| `subtlex-pl-lemmas-master.csv` | <https://osf.io/download/ab9ym/> | 59,196,902 | `65a07a6d0a12aa22d63481d2a77ac0e5ac398b673f302d67c8da640ecf62e5b2` |
| `subtlex-pl_tag-mapping.txt` (OSF name `tag-mapping.txt`) | <https://osf.io/download/7w28r/> | 412 | `8a77f4ca14822e38b052688e2cdd8bc8ec6b88b2652b2a2710026a712a541864` |
| `subtlex-pl_license.txt` (OSF name `license.txt`) | <https://osf.io/download/qra8w/> | 471 | `1c96df5fcc840ebf7e2147ea7f13820fcda223ef78eb55cb505972dfed43248b` |

Not downloaded from the same project: the `.RData` and `.xlsx` duplicates of these tables and the paper PDF. The bigram file mentioned in the paper is not in the OSF project.

### 2a. `subtlex-pl-cd-3.csv` and `subtlex-pl.csv` — word forms

- Format: **TAB-separated** despite the `.csv` name; UTF-8, no BOM, LF, header row, no quoting; 25 columns.
- Unit: **orthographic form, lower-cased** (no row contains upper case). `capit.freq` records how often the form was capitalised in the subtitles.
- `subtlex-pl.csv` is the full list: 987,911 rows, `freq` sums to 145,982,416 (computed). It includes numbers and non-words; rows with `spellcheck=1` and `alphabetical=1` number 449,302 types and 101,060,958 tokens (computed), matching the paper.
- `subtlex-pl-cd-3.csv` is the subset of strings found in at least 3 films: 377,843 rows, `freq` sums to 144,937,876. The OSF wiki recommends this subset to new users (as the `.xlsx`).

Columns (definitions from the paper's Availability section):

| Column | Meaning |
|---|---|
| `spelling` | the string |
| `spellcheck` | 1 if accepted by Aspell as a correct word |
| `alphabetical` | 1 if only alphabetical characters |
| `nchar` | number of characters |
| `freq` | number of occurrences in the subtitles |
| `capit.freq` | how many times the type was capitalised |
| `cd`, `cd.count` | proportion and count of films in which the type appears |
| `dom.pos`, `dom.pos.freq` | most frequent POS assigned to the type and its count |
| `dom.lemma.pos`, `dom.lemma.pos.freq`, `dom.lemma.pos.total.freq` | dominant lemma, its count for this type, and the lemma's total frequency |
| `all.pos`, `all.pos.freq`, `all.lemma.pos`, `all.lemma.pos.freq`, `all.lemma.pos.total.freq` | `.`-delimited lists over all POS and lemma assignments |
| `lg.freq`, `lg.mln.freq`, `zipf.freq`, `lg.cd` | log10 frequency, log10 frequency per million, Zipf-scale frequency, log10 contextual diversity |
| `freq.sn.sum`, `zipf.freq.sn.sum`, `avg.zipf.freq.sn` | compound measures combining SUBTLEX-PL with the NKJP balanced-subcorpus 1-gram list (the same list as `nkjp_1grams.gz`) |

First 5 lines, first 8 of 25 columns (identical in both files):

```
spelling	spellcheck	alphabetical	nchar	freq	capit.freq	cd	cd.count
nie	1	1	3	3831292	1627827	0.997767133648	27705
to	1	1	2	2865227	977969	0.998199301329	27717
się	1	1	3	2265417	1801	0.968091619548	26881
w	1	1	1	1779688	273279	0.997911189542	27709
```

### 2b. `subtlex-pl-lemmas-master.csv` — lemmas with their forms

- Format: TAB-separated, UTF-8, no BOM, LF, header row; 6 columns: `lemma`, `pos`, `spelling`, `freq`, `cd.count`, `cd`.
- Unit: **lemma + simplified POS**, automatically assigned. Lemmas of proper names are capitalised.
- Two row types alternate. A lemma row has `spelling` = `%` and `freq` = the lemma's total. It is followed by its form rows, which have `lemma` = `@`, `pos` = `@` and the inflected form in `spelling`.
- 537,490 lemma rows and 1,044,717 form rows; the lemma rows sum to 145,982,416. That total includes punctuation (`interp`), numbers (`tnum`), symbols (`tsym`) and unrecognised strings (`ign`).
- `subtlex-pl_tag-mapping.txt` maps IPI PAN tagset classes to the simplified POS labels (for example `fin`, `praet`, `inf`, `ger` → `verb`).

First 5 lines:

```
lemma	pos	spelling	freq	cd.count	cd
!	interp	%	2149119	27327	0.984153851694
@	@	!	2149119	27327	0.984153851694
$	interp	%	13842	4415	0.159001692657
@	@	$	13842	4415	0.159001692657
```

Example of the structure:

```
fotosynteza	subst	%	46	28	0.00100839125581
@	@	fotosynteza	18	12	0.00043216768106
@	@	fotosyntezie	3	3	0.000108041920265
@	@	fotosyntezy	20	15	0.000540209601325
```

---

## 3. KWJP (Korpus Współczesnego Języka Polskiego, dekada 2011–2020)

A downloadable frequency list exists.

- <https://kwjp.pl/lists/> is an online browser of the frequency lists. Its help page <https://kwjp.pl/lists/doc/about/> ends with "Listy frekwencyjne KWJP można również pobrać z repozytorium", linking to <https://github.com/ipipan/kwjp100-varia/tree/main/freqlists>.
- That repository holds 48 gzipped CSV lists: words and 2/3/4-grams × {`lemma`, `orth`, `orth_lc`} × {`all`, `fakt`, `fikcja`, `publicystyka`}. The three single-word lists for the whole balanced corpus were downloaded. The genre-specific word lists (2.4–6.5 MB each) and the n-gram lists were not.
- CLARIN-PL repository: a search for "KWJP" through `https://clarin-pl.eu/dspace/server/api/discover/search/objects?query=KWJP` returned 0 results (the old `https://clarin-pl.eu/dspace/discover?query=KWJP` URL returns 404).

Licence: the repository `README.md` says "Ze wszystkich zasobów zamieszczonych w tym repozytorium można korzystać na zasadach licencji CC-BY 4.0 (Creative Commons Attribution 4.0)" — <https://github.com/ipipan/kwjp100-varia/blob/main/README.md>. There is no separate `LICENSE` file.

Corpus (stated at <https://kwjp.pl/overview>): texts from 2011–2020; "over one billion words, 100 million of which have been included in the balanced corpus", made up of 35% news and journalistic texts, 30% fiction and 35% non-fiction. It has no spoken or internet texts. The requested citation is Kieraś et al., *Język Polski* 105(2):5–20, 2025, doi 10.31286/JP.001055.

How the lists were built (stated on the help page): compiled automatically from the balanced corpus using automatic lemmatisation and tagging, so they may contain errors; only words in Latin letters (optionally with a hyphen); only units occurring at least 5 times in the whole corpus.

Files were fetched from commit-pinned URLs `https://raw.githubusercontent.com/ipipan/kwjp100-varia/26d82bd8b906dfed1cfcf8f903b1650b56daeabf/freqlists/<file>` on 2026-11-13 (the lists were committed on 2024-04-15). Git blob hashes match the GitHub API listing.

| File | Bytes (uncompressed) | sha256 | Unit | Rows | Sum of `freq` |
|---|---|---|---|---|---|
| `kwjp100-slowa-lemma-all.csv.gz` | 3,133,438 (10,850,919) | `5206e80669a054ad4d3c9d39b7643d13e75435afa3612a15d2847f39f42bb5fc` | **lemma × grammatical class**, case preserved | 184,917 | 81,664,894 |
| `kwjp100-slowa-orth_lc-all.csv.gz` | 5,870,924 (19,614,720) | `20f71004b99ba9ebb158e68360aa88c627aa2e0f4ce43e18979187b0a2fa3949` | **form, case-insensitive** | 360,472 | 81,318,653 |
| `kwjp100-slowa-orth-all.csv.gz` | 6,869,102 (22,740,520) | `95e27d103250f23533bf5b87accf846fb489d2b5ea3914950857163a22ae4a5a` | **form, case-sensitive** | 419,961 | 81,042,800 |

Format: gzip; CSV, comma-separated, UTF-8, no BOM, LF; header row in which the unit column (and, in the lemma list, the class column) has an empty name; numbers written as floats (`2629030.0`). One row in the lemma list is CSV-quoted (the lemma `"`), so use a CSV parser.

Columns: unit; class (lemma list only); `freq` (occurrences); `ipm` (per million); `ARF` (average reduced frequency); `DP`, `DP_norm`, `1-DP` (deviation of proportions and its rescaling, where values near 1 mean an even spread across texts); `total_freq` (equal to `freq` in every row of these three "all" lists).

Corpus size for normalisation: the `ipm` values are consistent with a denominator equal to the sum of `freq` in the same list (for example 2,629,030 / 32,192.9 × 10⁶ ≈ 81.66 M). That is the listed units only, not the stated 100 million.

First 5 lines:

```
# kwjp100-slowa-lemma-all.csv.gz
,,freq,ipm,ARF,DP,DP_norm,1-DP,total_freq
w,prep,2629030.0,32192.9,1672033.55,0.08825,0.08826,0.91175,2629030.0
i,conj,1838568.0,22513.57,1183653.22,0.08181,0.08182,0.91819,1838568.0
się,part,1733236.0,21223.76,1102686.8,0.11098,0.11099,0.88902,1733236.0
z,prep,1641565.0,20101.23,1028430.84,0.0519,0.05191,0.9481,1641565.0

# kwjp100-slowa-orth_lc-all.csv.gz
,freq,ipm,ARF,DP,DP_norm,1-DP,total_freq
w,2588225.0,31828.18,1644669.95,0.08887,0.08888,0.91113,2588225.0
i,1896274.0,23319.05,1224915.94,0.08039,0.0804,0.91961,1896274.0
się,1733421.0,21316.4,1102800.25,0.11094,0.11095,0.88906,1733421.0
na,1577107.0,19394.16,992885.45,0.06431,0.06432,0.93569,1577107.0

# kwjp100-slowa-orth-all.csv.gz
,freq,ipm,ARF,DP,DP_norm,1-DP,total_freq
w,2276113.0,28085.32,1441369.16,0.08403,0.08404,0.91597,2276113.0
i,1783629.0,22008.48,1145167.17,0.08271,0.08272,0.91729,1783629.0
się,1732459.0,21377.09,1102114.92,0.11098,0.11099,0.88902,1732459.0
na,1457312.0,17982.0,916774.51,0.06219,0.0622,0.93781,1457312.0
```

In the lemma list a lemma can appear under several classes. `i` has 15 rows (conj 1,838,568; part 45,668; and smaller ones), and verbs are split over `fin`, `praet`, `inf`, `ger`, `ppas` and so on. Sum over classes if you need one number per lemma.

---

## 4. wordfreq 3.1.1 (Python library, already in the venv)

Nothing was downloaded. Facts below come from the installed package (`wordfreq-3.1.1.dist-info/METADATA`, which embeds the README) and were cross-checked against <https://github.com/rspeer/wordfreq/blob/master/README.md>.

- **It runs**: `wordfreq.word_frequency('fotosynteza', 'pl')` returns `1.74e-07` (Zipf 2.24).
- **Sources for Polish** (README table row `Polish pl 6 Yes │ Yes Yes Yes - Yes Yes Yes -`): six domains from the "Exquisite Corpus" project.
  - Wikipedia
  - Subtitles: "OPUS OpenSubtitles 2018 and SUBTLEX". The SUBTLEX lists the README names are US, UK, CH, DE and NL; SUBTLEX-PL is not among them.
  - News: NewsCrawl 2014 and GlobalVoices
  - Web: OSCAR
  - Twitter
  - Reddit
  - Not used for Polish: Google Books.
- **How they are combined**: per word, the sources giving the highest and lowest frequency are dropped, the rest averaged, and the list rescaled to sum to 1. There is therefore no single corpus size.
- **Unit**: **orthographic forms**, not lemmas. Text is tokenised with a regex tokenizer following Unicode UAX #29 and case-folded: `Proces` and `proces` return the same value, and `tokenize('Fotosynteza i KOMÓRKA', 'pl')` gives `['fotosynteza', 'i', 'komórka']`. Inflected forms have their own entries (`komórka` 5.25e-06, `komórki` 2.95e-05).
- **Resolution**: frequencies are stored in bins of 0.01 on the Zipf scale. Polish has a "large" list (used by default as `best`; 453,320 entries, down to Zipf 1.0) and a "small" one. Multi-digit numbers are pooled by shape.
- **Licence**: code Apache-2.0 (`LICENSE.txt`); the README says it "includes data files that may be redistributed under a Creative Commons Attribution-ShareAlike 4.0 license". See <https://github.com/rspeer/wordfreq#license>.
- Data file: `.venv/lib/python3.12/site-packages/wordfreq/data/large_pl.msgpack.gz`, 2,368,608 bytes, sha256 `fac63e49c49ea2e39dd8a48152d7e54cec0920abbc59993088063ed5d9b528c2`.

---

## Fetches that failed or returned nothing

| URL | Result on 2026-11-13 |
|---|---|
| `http://crr.ugent.be/subtlex-pl` and `https://crr.ugent.be/subtlex-pl/` | 404 |
| `http://crr.ugent.be/subtlex-pl/subtlex-pl-cd-3.csv` | 404 |
| `https://crr.ugent.be/programs-data/subtitle-frequencies` | 404 |
| `https://clarin-pl.eu/dspace/discover?query=KWJP` | 404 |
| `https://clarin-pl.eu/dspace/server/api/discover/search/objects?query=KWJP` | 200, 0 results |
| `https://raw.githubusercontent.com/ipipan/kwjp100-varia/main/LICENSE` (also `.md`, `.txt`, `COPYING`) | 404 |

## Files in this directory

| File | What it is |
|---|---|
| `README_freq.md`, `manifest.json` | this description and its machine-readable form |
| `nkjp_1grams.gz` | NKJP balanced-subcorpus 1-grams (forms) |
| `NKJP-PodkorpusMilionowy-1.2.tar.gz` | NKJP1M source corpus |
| `derive_nkjp1m_freq.py` | script that derives the three lists below from the archive |
| `nkjp1m-1.2_lemma_ctag_freq.tsv`, `nkjp1m-1.2_lemma_freq.tsv`, `nkjp1m-1.2_orth_lc_freq.tsv` | derived NKJP1M lists |
| `subtlex-pl-cd-3.csv`, `subtlex-pl.csv`, `subtlex-pl-lemmas-master.csv` | SUBTLEX-PL forms (filtered, full) and lemmas |
| `subtlex-pl_tag-mapping.txt`, `subtlex-pl_license.txt` | SUBTLEX-PL POS mapping and licence text |
| `kwjp100-slowa-lemma-all.csv.gz`, `kwjp100-slowa-orth_lc-all.csv.gz`, `kwjp100-slowa-orth-all.csv.gz` | KWJP100 word lists |

Total size: about 540 MB. Compressed files were left compressed; they were read and checked as streams.
