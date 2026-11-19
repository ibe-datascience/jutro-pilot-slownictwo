"""Uruchomienie całego procesu jednym poleceniem.

    python -m jutro run --config config/biologia_sp.yaml            # pełny przebieg
    python -m jutro run --config config/biologia_sp.yaml --probka 50  # próbka 50 materiałów
    python -m jutro run --config ... --kroki korpus,tagowanie         # wybrane kroki

Kroki zapisują wyniki pośrednie w data/<nazwa>/<przebieg>/ i są pomijane, jeśli wynik już istnieje
(wymuś ponowne wykonanie przez --od-nowa).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from .common import load_ctx, log, now_iso, versions

STEPS = [
    ("korpus", "s01_korpus", "korpus.jsonl"),
    ("tagowanie", "s02_tagowanie", "tagi_produkcyjne.done"),
    ("frekwencje", "s03_frekwencje", "frekwencje.done"),
    ("kandydaci", "s04_kandydaci", "kandydaci_stat.parquet.done"),
    ("llm", "s05_llm", "llm.done"),
    ("pule", "s06_pule", "pule.done"),
    ("pseudoslowa", "s07_pseudoslowa", "pseudoslowa.done"),
    ("raport", "s08_raport", None),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jutro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="uruchom proces")
    run.add_argument("--config", required=True)
    run.add_argument("--probka", type=int, default=None, help="liczba materiałów docelowych w próbce")
    run.add_argument("--kroki", default=None, help="lista kroków po przecinku (domyślnie wszystkie)")
    run.add_argument("--od-nowa", action="store_true", help="nie używaj zapisanych wyników pośrednich")
    run.add_argument("--bez-llm", action="store_true", help="pomiń wywołania API (użyj zapisanych odpowiedzi)")
    args = ap.parse_args(argv)

    ctx = load_ctx(args.config, args.probka)
    ctx.bez_llm = args.bez_llm  # type: ignore[attr-defined]
    wanted = [s.strip() for s in args.kroki.split(",")] if args.kroki else [s[0] for s in STEPS]
    unknown = set(wanted) - {s[0] for s in STEPS}
    if unknown:
        ap.error(f"nieznane kroki: {sorted(unknown)}; dostępne: {[s[0] for s in STEPS]}")
    meta_path = ctx.out / "przebieg.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"kroki": {}}
    meta.update({"konfiguracja": str(ctx.cfg_path), "przebieg": ctx.run_name, "ziarno": ctx.seed,
                 "wersje": versions(), "polecenie": " ".join(sys.argv)})
    for name, module, marker in STEPS:
        if name not in wanted:
            continue
        done = marker and (ctx.data / marker).exists()
        if done and not args.od_nowa and args.kroki is None:
            log(f"== {name}: pominięty (wynik istnieje)")
            continue
        log(f"== {name}: start")
        mod = importlib.import_module(f"jutro.{module}")
        start = now_iso()
        mod.run(ctx)
        meta["kroki"][name] = {"start": start, "koniec": now_iso()}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
