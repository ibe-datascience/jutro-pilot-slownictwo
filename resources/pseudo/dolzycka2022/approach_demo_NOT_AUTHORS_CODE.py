"""NOT the authors' code.

The scripts of Dołżycka, Nikadon & Formanowicz (2022) could not be downloaded on 2026-11-13
(gin.g-node.org answered HTTP 503, see ../README_pseudo.md). This file is an independent,
minimal illustration of ONE step described in the paper's text: "for each real word used as a
source of pseudowords we used a regular expression that required generated pseudowords to
retain the ultimate syllable from the source word" (Wuggy "Matching Expression").

Wuggy 1.1.2 (Python package) has no matching-expression argument, so the regular expression
is applied to the candidates coming out of WuggyGenerator.generate_advanced(), with the same
settings generate_classic() uses (same subsyllabic segment lengths, concentric search on
transition frequencies, segment overlap ratio 2/3, non-words only).

It does not reproduce the paper's pipeline (Sketch Engine word lists, Morfeusz/SGJP filtering,
Pyphen hyphenation, Hungarian-algorithm pairing, OLD20-based selection, human ratings).

Run:  python approach_demo_NOT_AUTHORS_CODE.py komora wynik porównać
"""
import os
import random
import re
import sys
import time
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wuggy_plugins"))
from load_local_plugin import load_generator  # noqa: E402


def suffix_preserving(g, word, n=5, max_time=30, overlap=Fraction(2, 3)):
    syllabified = g.lookup_reference_segments(word)
    if syllabified is None:
        return None, [], 0
    pattern = re.compile(".+" + re.escape(syllabified.split("-")[-1]) + "$")
    g.clear_attribute_filters()
    g.clear_frequency_filter()
    g.set_reference_sequence(syllabified)
    g.set_output_mode("plain")
    g.set_attribute_filter("segment_length")
    g.clear_statistics()
    g.set_statistics(["overlap_ratio", "lexicality"])  # cheap ones only; OLD20 computed for kept items
    kept, seen, t0, first = [], 0, time.time(), True
    for exponent in range(1, 16):
        g.set_frequency_filter(2 ** exponent, 2 ** exponent)
        for pseudoword in g.generate_advanced(clear_cache=first):
            first = False
            seen += 1
            if time.time() - t0 > max_time:
                return pattern.pattern, kept, seen
            if not pattern.match(pseudoword) or pseudoword == word:
                continue
            if g.statistics["lexicality"] == "W" or g.statistics["overlap_ratio"] != overlap:
                continue
            old20 = g.language_plugin.statistic_old20(g, g.current_sequence)
            kept.append((pseudoword, round(old20, 2)))
            if len(kept) >= n:
                return pattern.pattern, kept, seen
    return pattern.pattern, kept, seen


if __name__ == "__main__":
    words = sys.argv[1:] or ["komora", "wynik", "porównać"]
    g = load_generator("orthographic_polish")
    for w in words:
        t = time.time()
        random.seed(20261113)  # Wuggy uses the global `random` module; seeding makes the output reproducible
        pattern, kept, seen = suffix_preserving(g, w)
        if pattern is None:
            print(f"{w}: not in the Wuggy Polish lexicon")
            continue
        print(f"{w}: regex {pattern!r}; {seen} candidates inspected in {time.time() - t:.1f}s; "
              f"{len(kept)} kept (pseudoword, OLD20): {kept}")
