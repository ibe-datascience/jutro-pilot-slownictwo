#!/usr/bin/env python
"""Morfeusz2 + Concraft-pl pipeline: plain text -> disambiguated tokens in TermoPL flat format.

For every *.txt file in IN_DIR:
  1. each non-empty line (paragraph) is analysed with Morfeusz2 (expand_tags=True) and written
     as a Concraft DAG (11 tab-separated columns, blank line after each paragraph)
     -> WORK_DIR/<name>.dag
  2. the prebuilt concraft-pl binary disambiguates it
     -> WORK_DIR/<name>.tagged.dag   (12th column = "disamb" on the chosen interpretation)
  3. the chosen interpretations are written as  form<TAB>lemma<TAB>tag, with an empty line
     at every sentence end (column 10 = "eos")
     -> OUT_DIR/<name>.txt           (TermoPL flat format)

Run with the main venv python (needs the morfeusz2 module):
    python concraft_tag.py IN_DIR WORK_DIR OUT_DIR
"""
import os
import subprocess
import sys
import time

import morfeusz2

HERE = os.path.dirname(os.path.abspath(__file__))
BINARY = os.path.join(HERE, "concraft-pl")
MODEL = os.path.join(HERE, "concraft-pl-model-SGJP-20220221.gz")


def write_dag(morf, text, path):
    with open(path, "w", encoding="utf-8") as out:
        for para in text.splitlines():
            para = para.strip()
            if not para:
                continue
            for start, end, (orth, lemma, tag, names, quals) in morf.analyse(para):
                cols = [str(start), str(end), orth, lemma, tag,
                        ",".join(names), ",".join(quals), "0.0", "", "", ""]
                out.write("\t".join(cols) + "\n")
            out.write("\n")


def dag_to_flat(tagged, flat):
    """Keep the interpretation marked disamb for every chosen segment.

    Concraft does not lemmatise: when several lemmas share the chosen tag, all of them are
    marked disamb (e.g. Ściana:Sf / ściana for sentence-initial "Ściany"). We then take the
    first lemma that starts with a lower-case letter, otherwise the first one listed.
    """
    n = 0
    with open(tagged, encoding="utf-8") as fin, open(flat, "w", encoding="utf-8") as fout:
        segments = {}  # (start, end) -> [form, tag, eos, [lemmas]], in file order

        def flush():
            nonlocal n
            for form, tag, eos, lemmas in segments.values():
                lemma = next((l for l in lemmas if l[:1].islower()), lemmas[0])
                fout.write(f"{form}\t{lemma}\t{tag}\n")
                n += 1
                if eos:
                    fout.write("\n")
            segments.clear()

        for line in fin:
            line = line.rstrip("\n")
            if not line:
                flush()
                continue
            cols = line.split("\t")
            if len(cols) < 12 or cols[11] != "disamb":
                continue
            lemma = cols[3].split(":")[0] or cols[3]
            seg = segments.setdefault((cols[0], cols[1]), [cols[2], cols[4], False, []])
            seg[2] = seg[2] or cols[9] == "eos"
            seg[3].append(lemma)
        flush()
    return n


def main():
    in_dir, work_dir, out_dir = sys.argv[1:4]
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    morf = morfeusz2.Morfeusz(expand_tags=True)
    for name in sorted(os.listdir(in_dir)):
        if not name.endswith(".txt"):
            continue
        stem = os.path.splitext(name)[0]
        dag = os.path.join(work_dir, stem + ".dag")
        tagged = os.path.join(work_dir, stem + ".tagged.dag")
        with open(os.path.join(in_dir, name), encoding="utf-8") as f:
            write_dag(morf, f.read(), dag)
        t0 = time.time()
        subprocess.run([BINARY, "tag", MODEL, "-i", dag, "-o", tagged], check=True)
        n = dag_to_flat(tagged, os.path.join(out_dir, stem + ".txt"))
        print(f"{name}: {n} tokens, concraft {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
