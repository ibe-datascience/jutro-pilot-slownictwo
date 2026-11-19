#!/usr/bin/env python
"""Proof of concept: tag plain text with spaCy pl_core_news_lg and write TermoPL's flat format.

    form<TAB>lemma<TAB>tag        (empty line = sentence boundary)

pl_core_news_lg gives only the NKJP grammatical class in token.tag_ (SUBST, ADJ, GER ...);
number/case/gender are in token.morph as UD features. TermoPL's built-in grammar needs
pos plus number, case and gender (agreement test, genitive modifiers), so the tag is
rebuilt as class:number:case:gender[:degree] from the UD features.

Usage:
    python spacy2flat.py IN_DIR OUT_DIR       # IN_DIR/*.txt -> OUT_DIR/<name>.txt
"""
import os
import sys

import spacy

NUMBER = {"Sing": "sg", "Plur": "pl"}
CASE = {"Nom": "nom", "Gen": "gen", "Dat": "dat", "Acc": "acc", "Ins": "inst", "Loc": "loc", "Voc": "voc"}
DEGREE = {"Pos": "pos", "Cmp": "com", "Sup": "sup"}
POS = {"qub": "part", "numcol": "num", "burk": "frag", "xxx": "ign", "_sp": "interp"}


def gender(morph):
    g = morph.get("Gender")
    if not g:
        return None
    if g[0] == "Fem":
        return "f"
    if g[0] == "Neut":
        return "n"
    anim = (morph.get("Animacy") or ["Inan"])[0]
    return {"Hum": "m1", "Nhum": "m2", "Anim": "m2", "Inan": "m3"}.get(anim, "m3")


def nkjp_tag(tok):
    if tok.is_punct:
        return "interp"
    pos = tok.tag_.lower()
    pos = POS.get(pos, pos)
    parts = [pos]
    m = tok.morph
    for value in (NUMBER.get((m.get("Number") or [None])[0]),
                  CASE.get((m.get("Case") or [None])[0]),
                  gender(m)):
        if value:
            parts.append(value)
    if pos == "adj":
        deg = DEGREE.get((m.get("Degree") or [None])[0])
        if deg:
            parts.append(deg)
    return ":".join(parts)


def main():
    in_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    nlp = spacy.load("pl_core_news_lg", exclude=["ner"])
    for name in sorted(os.listdir(in_dir)):
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(in_dir, name), encoding="utf-8") as f:
            doc = nlp(f.read())
        dst = os.path.join(out_dir, name)
        n = 0
        with open(dst, "w", encoding="utf-8") as out:
            for sent in doc.sents:
                for tok in sent:
                    if tok.is_space:
                        continue
                    out.write(f"{tok.text}\t{tok.lemma_}\t{nkjp_tag(tok)}\n")
                    n += 1
                out.write("\n")
        print(f"{name} -> {dst} ({n} tokens)", file=sys.stderr)


if __name__ == "__main__":
    main()
