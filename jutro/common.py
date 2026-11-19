"""Wspólne narzędzia: konfiguracja, ścieżki, logowanie, zapis wyników pośrednich."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

ROOT = Path(__file__).resolve().parent.parent
SF_DATALESS = 0x40000000  # macOS: plik wypchnięty do iCloud (odczyt = pobranie)


def expand(path: str | os.PathLike) -> Path:
    p = Path(os.path.expanduser(str(path)))
    return p if p.is_absolute() else ROOT / p


@dataclass
class Ctx:
    """Kontekst przebiegu: konfiguracja + katalogi robocze dla danej próbki."""

    cfg: dict[str, Any]
    cfg_path: Path
    probka: int | None

    @property
    def run_name(self) -> str:
        return f"probka{self.probka}" if self.probka else "pelny"

    @property
    def data(self) -> Path:
        d = ROOT / "data" / self.cfg["nazwa"] / self.run_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def out(self) -> Path:
        d = ROOT / "wyniki" / self.cfg["nazwa"] / self.run_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def metrics_dir(self) -> Path:
        d = self.out / "metryki"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def seed(self) -> int:
        return int(self.cfg.get("ziarno", 0))

    def rng(self, salt: str = "") -> random.Random:
        return random.Random(f"{self.seed}:{salt}")

    def save_metrics(self, name: str, obj: Any) -> Path:
        """Każda liczba w raporcie pochodzi z pliku zapisanego tą funkcją."""
        p = self.metrics_dir / f"{name}.json"
        payload = {"_zapisano": now_iso(), "_przebieg": self.run_name, "dane": obj}
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        return p

    def load_metrics(self, name: str, default: Any = None) -> Any:
        p = self.metrics_dir / f"{name}.json"
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))["dane"]


def _json_default(o: Any) -> Any:
    try:
        import numpy as np

        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return None if o != o else float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:  # pragma: no cover
        pass
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


def load_ctx(cfg_path: str | os.PathLike, probka: int | None = None) -> Ctx:
    cfg_path = expand(cfg_path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return Ctx(cfg=cfg, cfg_path=cfg_path, probka=probka)


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


class Timer:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()

    @property
    def s(self) -> float:
        return time.perf_counter() - self.t0


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
            n += 1
    tmp.replace(path)
    return n


def sha256_file(path: Path, limit_mb: int = 2048) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def is_dataless(path: Path) -> bool:
    try:
        return bool(os.stat(path).st_flags & SF_DATALESS)  # type: ignore[attr-defined]
    except (AttributeError, FileNotFoundError):
        return False


def versions() -> dict[str, str]:
    """Wersje bibliotek zapisywane razem z wynikami."""
    from importlib import metadata

    out = {"python": sys.version.split()[0], "platforma": platform.platform()}
    for pkg in [
        "morfeusz2", "spacy", "pl_core_news_lg", "stanza", "torch", "wordfreq", "Wuggy", "anthropic",
        "pandas", "numpy", "scipy", "scikit-learn", "rapidfuzz", "lxml", "openpyxl", "PyYAML",
    ]:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = "brak"
    return out
