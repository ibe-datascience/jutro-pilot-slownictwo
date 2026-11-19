#!/usr/bin/env python
"""Tag/parse plain-text Polish files with Stanza and write CoNLL-U files that TermoPL reads.

This replaces TermoPL's bundled parse.py for our pipeline: it does NOT call
stanza.download() (no network, nothing written to ~/stanza_resources) and uses the
models stored under resources/tools/stanza_resources.

Usage:
    python txt2conllu.py IN_DIR OUT_DIR                      # every *.txt in IN_DIR -> OUT_DIR/<name>.conllu
    python txt2conllu.py --no-depparse IN_DIR OUT_DIR        # faster; enough for -method gt
    python txt2conllu.py --morfeusz-lemmas IN_DIR OUT_DIR    # proof of concept: replace Stanza lemmas
                                                             # by Morfeusz2 lemmas when unambiguous

TermoPL reads from CoNLL-U: FORM (col 2), LEMMA (col 3), UPOS (col 4), XPOS (col 5),
FEATS (col 6), HEAD (col 7), DEPREL (col 8), MISC (col 10: SpaceAfter=No or
start_char/end_char, optional ner=). The grammar-template method (-method gt) uses
FORM, LEMMA and XPOS (NKJP-style tag such as subst:sg:nom:f); the UD method
(-method ud) additionally needs UPOS, HEAD and DEPREL, i.e. the depparse processor.

--morfeusz-lemmas: for every word, Morfeusz2 analyses of the surface form are compared
with the XPOS tag chosen by Stanza. If exactly one lemma is compatible with that tag
(or Morfeusz knows only one lemma for the form at all), it replaces Stanza's lemma.
Otherwise Stanza's lemma is kept (always for gerunds). Tags and tokenisation are never changed.
"""
import argparse
import os
import sys
import time

import stanza
from stanza.utils.conll import CoNLL

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(HERE), "stanza_resources")


def _compatible(xpos, mtag):
    """True if the Stanza XPOS (subst:sg:gen:f) is one reading of a Morfeusz tag (subst:sg:gen.acc:f)."""
    xp = xpos.split(":")
    mp = [set(p.split(".")) for p in mtag.split(":")]
    if xp[0] not in mp[0]:
        return False
    return all(a in b for a, b in zip(xp[1:], mp[1:]))


def morfeusz_lemma(morf, form, xpos):
    """Return a Morfeusz2 lemma for form given the tag picked by the tagger, or None to keep the old one."""
    # Gerunds are left alone: UD Polish-PDB (Stanza) lemmatises them as nouns (oddychanie),
    # Morfeusz as infinitives (oddychać); mixing both conventions would split one term in two.
    if (xpos or "").startswith("ger"):
        return None
    analyses = morf.analyse(form)
    # only forms that Morfeusz treats as one segment
    if not analyses or any((a[0], a[1]) != (0, 1) for a in analyses):
        return None
    readings = [(a[2][1].split(":")[0] or a[2][1], a[2][2]) for a in analyses]
    if all(tag == "ign" for _, tag in readings):
        return None
    compatible = {lemma for lemma, tag in readings if _compatible(xpos or "", tag)}
    if len(compatible) == 1:
        return compatible.pop()
    if not compatible:
        every = {lemma for lemma, _ in readings}
        if len(every) == 1:
            return every.pop()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--model-dir", default=os.environ.get("STANZA_RESOURCES_DIR", DEFAULT_MODEL_DIR))
    ap.add_argument("--no-depparse", action="store_true")
    ap.add_argument("--morfeusz-lemmas", action="store_true")
    args = ap.parse_args()

    processors = "tokenize,mwt,pos,lemma" if args.no_depparse else "tokenize,mwt,pos,lemma,depparse"
    t0 = time.time()
    nlp = stanza.Pipeline("pl", dir=args.model_dir, processors=processors,
                          download_method=None, use_gpu=False, logging_level="WARN")
    print(f"pipeline loaded in {time.time() - t0:.1f}s ({processors})", file=sys.stderr)

    morf = None
    if args.morfeusz_lemmas:
        import morfeusz2
        morf = morfeusz2.Morfeusz()

    os.makedirs(args.out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(args.in_dir) if n.lower().endswith(".txt"))
    for name in names:
        t1 = time.time()
        with open(os.path.join(args.in_dir, name), encoding="utf-8") as f:
            doc = nlp(f.read())
        changed = 0
        if morf is not None:
            for sent in doc.sentences:
                for word in sent.words:
                    new = morfeusz_lemma(morf, word.text, word.xpos)
                    if new and new != word.lemma:
                        print(f"  lemma {word.text}: {word.lemma} -> {new}", file=sys.stderr)
                        word.lemma = new
                        changed += 1
        out = os.path.join(args.out_dir, os.path.splitext(name)[0] + ".conllu")
        CoNLL.write_doc2conll(doc, out)
        extra = f", {changed} lemmas replaced" if morf is not None else ""
        print(f"{name} -> {out} ({doc.num_tokens} tokens, {time.time() - t1:.1f}s{extra})", file=sys.stderr)


if __name__ == "__main__":
    main()
