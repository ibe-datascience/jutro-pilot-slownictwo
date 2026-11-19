"""Smoke test: 5 Wuggy pseudowords for each of komora, wynik, porównać (orthographic_polish)."""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_local_plugin import load_generator  # noqa: E402

import wuggy  # noqa: E402
from importlib.metadata import version  # noqa: E402

t0 = time.time()
g = load_generator("orthographic_polish")
print(f"wuggy {version('wuggy')} from {os.path.dirname(wuggy.__file__)}")
print(f"plugin data path: {g.language_plugin_data_path}")
print(f"loaded in {time.time() - t0:.1f}s; lookup_lexicon size = {len(g.lookup_lexicon)}; "
      f"neighbor_lexicon size = {len(g.neighbor_lexicon)}")
print("supported_statistics:", g.supported_statistics)
print("output modes:", g.list_output_modes())

words = ["komora", "wynik", "porównać"]
rows = []
for w in words:
    print(f"\n{w}: segments in lexicon = {g.lookup_reference_segments(w)!r}")
    t1 = time.time()
    random.seed(20261113)  # Wuggy shuffles start keys with the global `random` module; seed => reproducible output
    matches = g.generate_classic([w], ncandidates_per_sequence=5, max_search_time_per_sequence=30)
    print(f"  {len(matches)} matches in {time.time() - t1:.1f}s")
    for m in matches:
        s = m["statistics"]
        print(f"  {m['pseudoword']:<12} lexicality={s['lexicality']} old20={s['old20']:.2f} "
              f"ned1={s['ned1']} overlap_ratio={s['overlap_ratio']}")
        rows.append({"word": w, "segments": m["segments"], "pseudoword": m["pseudoword"],
                     "lexicality": s["lexicality"], "old20": s["old20"], "ned1": s["ned1"],
                     "overlap_ratio": str(s["overlap_ratio"])})

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_test_polish_output.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)
print(f"\nwrote {out}")
