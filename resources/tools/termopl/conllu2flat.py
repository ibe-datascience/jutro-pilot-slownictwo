#!/usr/bin/env python
"""Convert CoNLL-U files (e.g. from txt2conllu.py) to TermoPL's flat input format.

Flat format (TermoPL manual 8.1, section 2.1), UTF-8, one token per line:

    form<TAB>lemma<TAB>tag

Sentences are separated by an empty line; a line starting with %% separates documents
inside one file. The tag is an NKJP-style tag (subst:sg:nom:f); we copy the XPOS column.
Multi-word-token range lines (1-2) and empty nodes (1.1) are skipped; only syntactic
words are written.

Usage:
    python conllu2flat.py IN_DIR OUT_DIR      # IN_DIR/*.conllu -> OUT_DIR/<name>.txt
"""
import os
import sys


def convert(src, dst):
    n = 0
    with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.rstrip("\n")
            if not line.strip():
                fout.write("\n")
                continue
            if line.startswith("#"):
                continue
            cols = line.split("\t")
            if not cols[0].isdigit():
                continue
            form, lemma, xpos = cols[1], cols[2], cols[4]
            fout.write(f"{form}\t{lemma}\t{xpos}\n")
            n += 1
    return n


def main():
    in_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(os.listdir(in_dir)):
        if name.endswith(".conllu"):
            dst = os.path.join(out_dir, os.path.splitext(name)[0] + ".txt")
            n = convert(os.path.join(in_dir, name), dst)
            print(f"{name} -> {dst} ({n} tokens)", file=sys.stderr)


if __name__ == "__main__":
    main()
