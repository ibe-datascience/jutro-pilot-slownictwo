"""Wzorce składniowe grup nominalnych (kandydaci wielowyrazowi).

Gramatyka (na klasach fleksyjnych, z uzgodnieniem):
    NP      := A* N A*            przymiotniki/imiesłowy uzgodnione z rzeczownikiem co do przypadka (i liczby/rodzaju)
    fraza   := NP (NP_dop){0,2}   dopełniaczowe człony podrzędne („narząd wymiany gazowej”)
Długość 2..max_len wyrazów. Generowane są wszystkie poprawne podfrazy (zagnieżdżenia rozstrzyga C-value).
Frazy przyimkowe („odporność na choroby”) nie są obsługiwane – ograniczenie opisane w raporcie.
"""
from __future__ import annotations

from typing import Iterator, Sequence

from .morf import ADJISH, NOUNISH, Tok


def _agree(a: Tok, n: Tok) -> bool:
    if not a.case or not n.case or a.case != n.case:
        return False
    if a.num and n.num and a.num != n.num:
        return False
    if a.gen and n.gen and a.num == "sg" and a.gen != n.gen:
        # w lp. rodzaj musi się zgadzać (z tolerancją m1/m2/m3 – tagery często je mylą)
        if not (a.gen.startswith("m") and n.gen.startswith("m")):
            return False
    return True


# Zaimki przymiotne, liczebniki porządkowe „tekstowe” i zaimki rzeczowne: gramatycznie pasują do wzorca NP,
# ale nie tworzą terminów („ten sposób”, „jaka rola”, „coś trudności”).
STOP_ADJ = {
    "ten", "tamten", "ów", "taki", "jaki", "jakiś", "jakikolwiek", "który", "któryś", "każdy", "żaden", "wszystek",
    "wszelki", "inny", "pewien", "niektóry", "niejeden", "sam", "mój", "twój", "swój", "nasz", "wasz", "czyj",
    "następujący", "poniższy", "powyższy", "kolejny", "dany", "dowolny", "niniejszy", "wspomniany", "wyżej",
}
STOP_NOUN = {"coś", "ktoś", "nic", "nikt", "co", "kto", "to", "cokolwiek", "ktokolwiek", "wszystko", "wszyscy"}


def _content(t: Tok) -> bool:
    f = t.form
    if len(f) < 2 or not f.replace("-", "").isalpha():
        return False
    low = t.lemma.lower()
    return low not in (STOP_ADJ if t.cls in ADJISH else STOP_NOUN)


def np_spans(toks: Sequence[Tok], max_len: int) -> list[tuple[int, int, int]]:
    """Wszystkie NP: (start, koniec_wyłącznie, indeks_nadrzędnika)."""
    out = []
    n = len(toks)
    for h in range(n):
        t = toks[h]
        if t.cls not in NOUNISH or not _content(t):
            continue
        left = 0
        while h - left - 1 >= 0 and toks[h - left - 1].cls in ADJISH and _content(toks[h - left - 1]) \
                and _agree(toks[h - left - 1], t) and left < max_len - 1:
            left += 1
        right = 0
        while h + right + 1 < n and toks[h + right + 1].cls in ADJISH and _content(toks[h + right + 1]) \
                and _agree(toks[h + right + 1], t) and right < max_len - 1:
            right += 1
        for l in range(left + 1):
            for r in range(right + 1):
                if 1 + l + r <= max_len:
                    out.append((h - l, h + r + 1, h))
    return out


def iter_phrases(toks: Sequence[Tok], max_len: int = 4) -> Iterator[tuple[int, int]]:
    """Zakresy (start, koniec) fraz wielowyrazowych w zdaniu."""
    nps = np_spans(toks, max_len)
    by_start: dict[int, list[tuple[int, int, int]]] = {}
    for s, e, h in nps:
        by_start.setdefault(s, []).append((s, e, h))
    seen = set()

    def is_gen_np(s: int, e: int) -> bool:
        return all(toks[k].case == "gen" for k in range(s, e))

    for s, e, h in nps:
        if e - s >= 2 and (s, e) not in seen:
            seen.add((s, e))
            yield s, e
        # człony dopełniaczowe
        frontier = [(s, e)]
        for _depth in range(2):
            nxt = []
            for fs, fe in frontier:
                for s2, e2, h2 in by_start.get(fe, []):
                    if e2 - fs <= max_len and is_gen_np(s2, e2):
                        if (fs, e2) not in seen:
                            seen.add((fs, e2))
                            yield fs, e2
                        nxt.append((fs, e2))
            frontier = nxt
            if not frontier:
                break
