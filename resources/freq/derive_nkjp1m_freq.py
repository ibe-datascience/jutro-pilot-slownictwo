#!/usr/bin/env python3
"""Derive frequency lists from the manually annotated NKJP 1-million subcorpus (NKJP1M 1.2).

Input : NKJP-PodkorpusMilionowy-1.2.tar.gz (TEI P5; one directory per text sample,
        each with ann_morphosyntax.xml). The archive is read as a stream, nothing is
        extracted to disk.
Output: nkjp1m-1.2_lemma_ctag_freq.tsv  lemma <TAB> ctag <TAB> freq
        nkjp1m-1.2_lemma_freq.tsv       lemma <TAB> freq           (summed over ctags)
        nkjp1m-1.2_orth_lc_freq.tsv     orth_lc <TAB> freq         (lower-cased segments)

Unit of counting: one <seg> in ann_morphosyntax.xml (an NKJP segment; punctuation
is a segment with ctag "interp", agglutinates such as "em" in "zrobiłem" are separate
segments). The lemma and ctag are taken from the manually disambiguated
interpretation: <f name="disamb"> ... <f name="choice" fVal="#...-msd"/>, resolved to
the enclosing <fs type="lex"> (features "base" and "ctag"). Lemmas keep the case used
in the annotation (proper names are capitalised). Nothing is filtered out; the only
normalisation is collapsing whitespace runs inside orth/base to a single space.
"""
import collections
import sys
import tarfile
import xml.etree.ElementTree as ET

TEI = "{http://www.tei-c.org/ns/1.0}"
XMLID = "{http://www.w3.org/XML/1998/namespace}id"

SRC = sys.argv[1] if len(sys.argv) > 1 else "NKJP-PodkorpusMilionowy-1.2.tar.gz"
PREFIX = "nkjp1m-1.2"


def feature(fs, name):
    for f in fs.findall(TEI + "f"):
        if f.get("name") == name:
            return f
    return None


def main():
    lemma_ctag = collections.Counter()
    orth_lc = collections.Counter()
    n_files = n_seg = n_fallback = 0

    with tarfile.open(SRC, "r:gz") as tar:
        for member in tar:
            if not member.name.endswith("/ann_morphosyntax.xml"):
                continue
            n_files += 1
            fh = tar.extractfile(member)
            for _, seg in ET.iterparse(fh, events=("end",)):
                if seg.tag != TEI + "seg":
                    continue
                morph = seg.find(TEI + "fs")
                orth = feature(morph, "orth").find(TEI + "string").text or ""

                msd2lex = {}
                for lex in feature(morph, "interps").iter(TEI + "fs"):
                    if lex.get("type") != "lex":
                        continue
                    base = feature(lex, "base").find(TEI + "string").text or ""
                    ctag = feature(lex, "ctag").find(TEI + "symbol").get("value")
                    for sym in feature(lex, "msd").iter(TEI + "symbol"):
                        msd2lex[sym.get(XMLID)] = (base, ctag)

                report = feature(morph, "disamb").find(TEI + "fs")
                choice = feature(report, "choice").get("fVal", "").lstrip("#")
                if choice in msd2lex:
                    base, ctag = msd2lex[choice]
                else:
                    # should not happen; fall back to the "base:ctag[:msd]" string
                    n_fallback += 1
                    interp = feature(report, "interpretation").find(TEI + "string").text
                    base, ctag = interp.split(":")[0], interp.split(":")[1]

                # one segment in the corpus has a TAB inside orth/base; collapse
                # whitespace runs so that the TSV output stays well-formed
                base = " ".join(base.split())
                orth = " ".join(orth.split())

                lemma_ctag[(base, ctag)] += 1
                orth_lc[orth.lower()] += 1
                n_seg += 1
                seg.clear()

    lemma = collections.Counter()
    for (base, _), c in lemma_ctag.items():
        lemma[base] += c

    def dump(path, header, rows):
        with open(path, "w", encoding="utf-8", newline="\n") as out:
            out.write("\t".join(header) + "\n")
            for row in rows:
                out.write("\t".join(str(x) for x in row) + "\n")

    dump(f"{PREFIX}_lemma_ctag_freq.tsv", ("lemma", "ctag", "freq"),
         ((b, t, c) for (b, t), c in sorted(lemma_ctag.items(), key=lambda kv: (-kv[1], kv[0]))))
    dump(f"{PREFIX}_lemma_freq.tsv", ("lemma", "freq"),
         sorted(lemma.items(), key=lambda kv: (-kv[1], kv[0])))
    dump(f"{PREFIX}_orth_lc_freq.tsv", ("orth_lc", "freq"),
         sorted(orth_lc.items(), key=lambda kv: (-kv[1], kv[0])))

    interp = sum(c for (_, t), c in lemma_ctag.items() if t == "interp")
    print(f"ann_morphosyntax.xml files : {n_files}")
    print(f"segments (tokens)          : {n_seg}")
    print(f"  of which ctag=interp     : {interp}")
    print(f"  non-punctuation segments : {n_seg - interp}")
    print(f"fallback parses            : {n_fallback}")
    print(f"lemma x ctag types         : {len(lemma_ctag)}")
    print(f"lemma types                : {len(lemma)}")
    print(f"orth_lc types              : {len(orth_lc)}")


if __name__ == "__main__":
    main()
