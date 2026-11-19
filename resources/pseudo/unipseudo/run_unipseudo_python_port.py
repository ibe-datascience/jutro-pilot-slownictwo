"""Run the pure-Python UniPseudo generator (branch `django_dev` of chrplr/openlexicon, commit 5d6f5188)
from the command line, without Django.

Only `generator.py` (no Django imports) is used, loaded by file path; `filters.py` is also Django-free
and is used for the optional constraints.

Usage:
    python run_unipseudo_python_port.py [n=20] [len=6] [seed=1] [constraints: none|r_presets]

Word lists (exported from data/WorldLex-Polish.rds with the R one-liner given in ../README_pseudo.md):
    data/worldlex_polish_len6_models_BlogFreqPm_gt0.5.txt   models (BlogFreqPm > 0.5, 6 letters, lower-cased)
    data/worldlex_polish_len6_all.txt                       exclusion list (all 6-letter WorldLex-Polish entries)
Other lengths: export the corresponding lists first, or pass your own files via UNIPSEUDO_MODELS / UNIPSEUDO_EXCLUDE.
"""
import importlib.util
import os
import random
import sys

here = os.path.dirname(os.path.abspath(__file__))
port = os.path.join(here, "openlexicon_django_dev_5d6f5188", "unipseudo")


def load(name):
    spec = importlib.util.spec_from_file_location(f"unipseudo_port_{name}", os.path.join(port, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


generator = load("generator")
filters = load("filters")

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
length = int(sys.argv[2]) if len(sys.argv) > 2 else 6
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
constraints = sys.argv[4] if len(sys.argv) > 4 else "none"

models_file = os.environ.get("UNIPSEUDO_MODELS", os.path.join(here, "data", "worldlex_polish_len6_models_BlogFreqPm_gt0.5.txt"))
exclude_file = os.environ.get("UNIPSEUDO_EXCLUDE", os.path.join(here, "data", "worldlex_polish_len6_all.txt"))
models = [w for w in dict.fromkeys(l.strip().lower() for l in open(models_file, encoding="utf-8")) if len(w) == length]
exclude = [l.strip() for l in open(exclude_file, encoding="utf-8")]

# "none" = what the live web app reported for Polish on 2026-11-13 (presets: {});
# "r_presets" = the presets of the original R Shiny app for "latin" languages (max 3 consonants, max 2 same letters)
values = {"filterConsonants": 3, "filterSameLetter": 2} if constraints == "r_presets" else {}
checks = filters.build_checks(values)

res = generator.generate_pseudowords(n, length, models, generator.default_algorithm(length), exclude=exclude,
                                     checks=checks, rng=random.Random(seed))
print(f"UniPseudo python port: len={length} n={n} algorithm={generator.default_algorithm(length)} seed={seed} "
      f"constraints={values or 'none'} models={res.n_models} exclusion={len(exclude)} generated={len(res.pseudowords)}")
for p in res.pseudowords:
    print(p.pseudoword, "<-", " ".join(p.sources))
