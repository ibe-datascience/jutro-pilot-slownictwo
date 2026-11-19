"""Morfeusz2: analiza z pamięcią podręczną, ujednoznacznianie sterowane tagerem, generowanie form.

Morfeusz2 zwraca wszystkie możliwe interpretacje formy. Concraft-pl (ujednoznacznianie) nie był dostępny
w tym środowisku, więc wybór interpretacji odbywa się na jeden z dwóch jawnie nazwanych sposobów:
  * `first`  – pierwsza interpretacja Morfeusza (bez kontekstu; wariant bazowy),
  * `guided` – interpretacja najlepiej zgodna z częścią mowy i cechami (przypadek, liczba, rodzaj)
               przypisanymi przez tager kontekstowy (spaCy albo Stanza).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, NamedTuple

import morfeusz2

_M = None


def morf() -> morfeusz2.Morfeusz:
    global _M
    if _M is None:
        _M = morfeusz2.Morfeusz(expand_tags=False, generate=True, whitespace=morfeusz2.SKIP_WHITESPACES)
    return _M


def dict_id() -> str:
    return morf().dict_id()


class Interp(NamedTuple):
    lemma: str
    cls: str          # klasa fleksyjna NKJP (subst, adj, ger, ...)
    tag: str          # pełny znacznik
    case: frozenset
    num: frozenset
    gen: frozenset
    labels: tuple     # kwalifikatory SGJP (np. 'biol.')
    proper: bool


CASES = {"nom", "gen", "dat", "acc", "inst", "loc", "voc"}
NUMS = {"sg", "pl"}
GENS = {"m1", "m2", "m3", "f", "n"}

UPOS2CLS = {
    "NOUN": {"subst", "depr", "ger", "brev", "num"},
    "PROPN": {"subst", "depr", "brev", "adj"},
    "ADJ": {"adj", "adja", "adjp", "adjc", "pact", "ppas", "num"},
    "VERB": {"fin", "praet", "inf", "impt", "imps", "bedzie", "pred", "winien", "pcon", "pant", "ger", "pact", "ppas"},
    "AUX": {"fin", "praet", "inf", "impt", "imps", "bedzie", "pred", "winien", "aglt", "pcon", "pant", "qub", "cond"},
    "ADV": {"adv", "qub", "adjp"},
    "NUM": {"num", "numcol", "adj"},
    "PRON": {"ppron12", "ppron3", "siebie", "subst", "adj", "qub"},
    "DET": {"adj", "num", "subst"},
    "ADP": {"prep"},
    "CCONJ": {"conj"},
    "SCONJ": {"comp", "conj"},
    "PART": {"qub", "part"},
    "INTJ": {"interj"},
    "PUNCT": {"interp"},
    "SYM": {"interp", "sym"},
}
UD_CASE = {"Nom": "nom", "Gen": "gen", "Dat": "dat", "Acc": "acc", "Ins": "inst", "Loc": "loc", "Voc": "voc"}
UD_NUM = {"Sing": "sg", "Plur": "pl"}


def ud_gender(feats: dict[str, str]) -> str | None:
    g = feats.get("Gender")
    if g == "Fem":
        return "f"
    if g == "Neut":
        return "n"
    if g == "Masc":
        a = feats.get("Animacy")
        return {"Hum": "m1", "Nhum": "m2", "Inan": "m3"}.get(a or "", "m3")
    return None


def clean_lemma(lemma: str) -> str:
    return lemma.split(":", 1)[0] if ":" in lemma and len(lemma) > 1 else lemma


def _parse_tag(tag: str):
    parts = tag.split(":")
    cls = parts[0]
    case, num, gen = set(), set(), set()
    for p in parts[1:]:
        vals = set(p.split("."))
        if vals & CASES:
            case |= vals & CASES
        elif vals & NUMS:
            num |= vals & NUMS
        elif vals & GENS:
            gen |= vals & GENS
    return cls, frozenset(case), frozenset(num), frozenset(gen)


@lru_cache(maxsize=400_000)
def analyse(form: str) -> tuple[Interp, ...]:
    """Interpretacje pierwszego segmentu formy (aglutynanty typu „-em” są pomijane)."""
    res = []
    try:
        dag = morf().analyse(form)
    except Exception:
        return ()
    if not dag:
        return ()
    # interpretacje obejmujące całą formę mają pierwszeństwo; w przeciwnym razie pierwszy segment
    end_max = max(e for _, e, _ in dag)
    whole = [i for s, e, i in dag if s == 0 and e == end_max]
    first = whole or [i for s, e, i in dag if s == 0]
    for orth, lemma, tag, names, labels in first:
        cls, case, num, gen = _parse_tag(tag)
        res.append(Interp(clean_lemma(lemma), cls, tag, case, num, gen, tuple(labels),
                          bool(names) and "nazwa_pospolita" not in names))
    return tuple(res)


def is_known(form: str) -> bool:
    ints = analyse(form)
    return bool(ints) and any(i.cls != "ign" for i in ints)


@lru_cache(maxsize=200_000)
def _generate(lemma: str) -> tuple[tuple[str, str], ...]:
    try:
        return tuple((f[0], f[2]) for f in morf().generate(lemma))
    except Exception:
        return ()


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def generate_form(lemma: str, cls: str, num: str, gen: str | None, case: str = "nom", neg: bool = False,
                  prefer: str | None = None) -> str | None:
    """Forma leksemu o zadanych cechach (domyślnie mianownik), np. przymiotnik uzgodniony z rzeczownikiem.

    Gdy Morfeusz ma kilka równorzędnych form (np. „sprzężony” / „sprzęgnięty”), a podano `prefer`
    (forma z tekstu), wybierana jest ta o najdłuższym wspólnym prefiksie z `prefer`.
    """
    cands: list[str] = []
    for form, tag in _generate(lemma):
        parts = tag.split(":")
        if parts[0] != cls:
            continue
        _c, cs, ns, gs = _parse_tag(tag)
        if case not in cs or num not in ns:
            continue
        if gen and gs and gen not in gs:
            continue
        if cls in ("adj",) and "pos" not in parts:
            continue
        if cls in ("ger", "pact", "ppas") and (("neg" in parts) != neg):
            continue
        if form[:1].isupper() and not lemma[:1].isupper():
            continue
        cands.append(form)
    if not cands:
        return None
    if prefer:
        pl = prefer.lower()
        return max(cands, key=lambda f: (_common_prefix(f.lower(), pl), -abs(len(f) - len(prefer))))
    return cands[0]


def nominal_lemma(interp: Interp, form: str) -> str:
    """Lemat „słownikowy” dla terminologii: odsłownik → rzeczownik (oddychanie), imiesłów → forma przymiotnikowa."""
    if interp.cls == "ger":
        neg = ":neg" in interp.tag
        f = generate_form(interp.lemma, "ger", "sg", "n", neg=neg, prefer=form)
        return f or interp.lemma
    if interp.cls in ("pact", "ppas"):
        return participle_form(form, interp.cls, "sg", "m1") or participle_form(form, interp.cls, "sg", "m3") or interp.lemma
    return interp.lemma


def participle_form(form: str, cls: str, num: str, gen: str | None) -> str | None:
    """Forma imiesłowu o zadanych cechach; przy wariantach (sprzężony/sprzęgnięty) wybiera najbliższą formie z tekstu."""
    low = form.lower()
    cands: list[str] = []
    seen: set[str] = set()
    for i in analyse(low) or analyse(form):
        if i.cls != cls:
            continue
        f = generate_form(i.lemma, cls, num, gen, neg=":neg" in i.tag, prefer=low)
        if f and f not in seen:
            seen.add(f)
            cands.append(f)
    if not cands:
        return None
    return max(cands, key=lambda f: (_common_prefix(f.lower(), low), -abs(len(f) - len(form))))


class Choice(NamedTuple):
    lemma: str
    cls: str
    case: str
    num: str
    gen: str
    known: bool
    n_interp: int
    biol: bool
    proper: bool


def _pick(vals: frozenset, pref: str | None, order: Iterable[str]) -> str:
    if pref and pref in vals:
        return pref
    for o in order:
        if o in vals:
            return o
    return ""


def choose(form: str, upos: str | None = None, feats: dict[str, str] | None = None,
           fallback_lemma: str | None = None, mode: str = "guided") -> Choice:
    ints = analyse(form)
    low = form.lower()
    if (not ints or all(i.cls == "ign" for i in ints)) and low != form:
        ints_low = analyse(low)
        if ints_low and any(i.cls != "ign" for i in ints_low):
            ints = ints_low
    elif low != form and upos != "PROPN":
        # początek zdania: uwzględnij też interpretacje formy pisanej małą literą
        ints = tuple(dict.fromkeys(analyse(low) + ints))
    known = bool(ints) and any(i.cls != "ign" for i in ints)
    if not known:
        lem = fallback_lemma or low
        f = feats or {}
        return Choice(lem, {"NOUN": "subst", "PROPN": "subst", "ADJ": "adj", "VERB": "fin", "ADV": "adv"}.get(upos or "", "ign"),
                      UD_CASE.get(f.get("Case", ""), ""), UD_NUM.get(f.get("Number", ""), ""), ud_gender(f) or "",
                      False, 0, False, upos == "PROPN")
    ints = tuple(i for i in ints if i.cls != "ign")
    feats = feats or {}
    w_case = UD_CASE.get(feats.get("Case", ""))
    w_num = UD_NUM.get(feats.get("Number", ""))
    w_gen = ud_gender(feats)
    if mode == "first" or upos is None:
        best = ints[0]
    else:
        allowed = UPOS2CLS.get(upos, set())
        best, best_sc = ints[0], -1.0
        for k, i in enumerate(ints):
            sc = 0.0
            if i.cls in allowed:
                sc += 4
            if upos in ("NOUN",) and i.cls == "subst":
                sc += 0.5  # zleksykalizowany rzeczownik przed odsłownikiem
            if upos == "ADJ" and i.cls == "adj":
                sc += 0.5
            if upos == "PROPN" and i.proper:
                sc += 1
            if upos != "PROPN" and i.proper:
                sc -= 0.75
            if w_case and w_case in i.case:
                sc += 1
            if w_num and w_num in i.num:
                sc += 1
            if w_gen and w_gen in i.gen:
                sc += 1
            if fallback_lemma and i.lemma.lower() == fallback_lemma.lower():
                sc += 0.25
            sc -= k * 0.001
            if sc > best_sc:
                best, best_sc = i, sc
    lemma = nominal_lemma(best, form)
    return Choice(
        lemma, best.cls,
        _pick(best.case, w_case, ["nom", "acc", "gen", "loc", "inst", "dat", "voc"]),
        _pick(best.num, w_num, ["sg", "pl"]),
        _pick(best.gen, w_gen, ["m3", "f", "n", "m1", "m2"]),
        True, len(ints), any("biol" in l or "med" in l or "bot" in l or "zool" in l or "anat" in l for l in best.labels),
        best.proper,
    )


# --------------------------------------------------------------------------------------
# Forma podstawowa wyrażenia wielowyrazowego
# --------------------------------------------------------------------------------------
NOUNISH = {"subst", "ger", "depr"}
ADJISH = {"adj", "pact", "ppas"}


class Tok(NamedTuple):
    form: str
    lemma: str
    cls: str
    case: str
    num: str
    gen: str
    known: bool = True


def phrase_structure(toks: list[Tok]) -> tuple[int, list[int]] | None:
    """Zwraca (indeks nadrzędnika, indeksy przymiotników uzgodnionych z nadrzędnikiem)."""
    head = next((k for k, t in enumerate(toks) if t.cls in NOUNISH), None)
    if head is None:
        return None
    h = toks[head]
    agree = []
    for k in range(head - 1, -1, -1):
        t = toks[k]
        if t.cls in ADJISH and (not t.case or not h.case or t.case == h.case):
            agree.append(k)
        else:
            return None  # coś innego niż przymiotnik przed nadrzędnikiem – nie umiemy sprowadzić do mianownika
    for k in range(head + 1, len(toks)):
        t = toks[k]
        if t.cls in ADJISH and t.case == h.case and (not t.num or not h.num or t.num == h.num) and h.case != "gen":
            agree.append(k)
        elif t.cls in ADJISH and t.case == h.case and h.case == "gen" \
                and (t.num == "pl" or not t.gen or not h.gen or t.gen == h.gen or (t.gen[0] == "m" and h.gen[0] == "m")) \
                and (not t.num or not h.num or t.num == h.num) and not any(x.cls in NOUNISH for x in toks[head + 1:k]):
            agree.append(k)
        else:
            break
    return head, sorted(agree)


def phrase_key(toks: list[Tok]) -> tuple[str, ...] | None:
    """Klucz grupujący warianty fleksyjne tej samej frazy."""
    st = phrase_structure(toks)
    if st is None:
        return None
    head, agree = st
    key = []
    for k, t in enumerate(toks):
        if k == head or k in agree:
            key.append(t.lemma.lower())
        elif t.cls == "prep":
            key.append("~" + t.form.lower())
        else:
            key.append(f"{t.lemma.lower()}/{t.case or '-'}")
    return tuple(key)


def phrase_base(toks: list[Tok], plural: bool = False) -> tuple[str, bool]:
    """Forma podstawowa frazy w mianowniku. Zwraca (forma, czy_pewna)."""
    st = phrase_structure(toks)
    if st is None:
        return " ".join(t.form.lower() for t in toks), False
    head, agree = st
    h = toks[head]
    num = "pl" if plural else "sg"
    ok = True
    out = []
    for k, t in enumerate(toks):
        if k == head:
            if not t.known:
                ok = False
                out.append(t.lemma)
            elif num == "sg":
                out.append(t.lemma)
            else:
                f = generate_form(t.lemma, "subst", "pl", None) if t.cls != "ger" else None
                if f is None:
                    ok = False
                out.append(f or t.lemma)
        elif k in agree:
            gen = h.gen or None
            if num == "pl":
                gen = "m1" if h.gen == "m1" else (h.gen or "f")
            f = None
            if t.known:
                if t.cls == "adj":
                    f = generate_form(t.lemma, "adj", num, gen)
                else:  # imiesłów: lemat ma już postać przymiotnikową (m. lp. r. męski) – szukamy po formie
                    f = participle_form(t.form, t.cls, num, gen)
            if f is None:
                ok = False
                f = t.lemma if (num == "sg" and h.gen in ("m1", "m2", "m3")) else t.form.lower()
            out.append(f)
        else:
            out.append(t.form if (t.form[:1].isupper() and t.cls in NOUNISH and t.lemma[:1].isupper()) else t.form.lower())
    return " ".join(out), ok
