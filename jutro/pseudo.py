"""Narzędzia językowe dla pseudosłów: leksykon odniesienia, ortotaktyka, fonologia, transliteracja UA/RU.

Wszystkie miary są deterministyczne i liczone względem tego samego leksykonu odniesienia:
lematów KWJP100 (CC BY 4.0) pisanych małymi literami i rozpoznawanych przez Morfeusza.
"""
from __future__ import annotations

import gzip
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Iterable

import numpy as np

from . import morf
from .common import ROOT

ALPHA_RE = re.compile(r"^[a-ząćęłńóśźż]+$")
VOWELS = "aąeęioóuy"
CONS = "bcćdfghjklłmnńprsśtwzźż"
CLUSTER_RE = re.compile(f"[{CONS}]+")
VOWEL_RE = re.compile(f"[{VOWELS}]+")
FREQ_DIR = ROOT / "resources" / "freq"
PSEUDO_DIR = ROOT / "resources" / "pseudo"


def syllables(word: str) -> int:
    """Liczba sylab = liczba ośrodków samogłoskowych; „i” przed samogłoską tylko zmiękcza (nie tworzy sylaby)."""
    w = re.sub(f"i(?=[{VOWELS}])", "", word.lower())
    w = re.sub(r"(?<=[ae])u", "", w)  # dyftongi au, eu (auto, Europa)
    return max(1, len(VOWEL_RE.findall(w)))


def max_cluster(word: str) -> int:
    """Najdłuższy ciąg liter spółgłoskowych."""
    return max((len(m.group(0)) for m in CLUSTER_RE.finditer(word.lower())), default=0)


def n_diacritics(word: str) -> int:
    return sum(1 for c in word if c in "ąćęłńóśźż")


def final_rime(word: str) -> str:
    """Rym ostatniej sylaby: od ostatniej grupy samogłosek do końca wyrazu (np. „komora” → „a”, „wynik” → „ik”)."""
    m = list(VOWEL_RE.finditer(word))
    return word[m[-1].start():] if m else word


def ending_class(word: str) -> str:
    """Klasa zakończenia: konkretna samogłoska, „ć” albo „C” (inna spółgłoska)."""
    last = word[-1]
    if last in VOWELS:
        return last
    return "ć" if last == "ć" else "C"


# --------------------------------------------------------------------------------------
# Fonologia: przybliżona transkrypcja do wykrywania homofonów
# --------------------------------------------------------------------------------------
_DIGRAPHS = [("dzi", "đi"), ("dź", "đ"), ("dż", "ǯ"), ("dz", "ʒ"), ("ch", "x"), ("cz", "č"), ("sz", "š"), ("rz", "ž")]
_SOFT = {"s": "ś", "z": "ź", "c": "ć", "n": "ń", "đ": "đ"}
_DEVOICE = {"b": "p", "d": "t", "g": "k", "w": "f", "z": "s", "ź": "ś", "ž": "š", "ʒ": "c", "đ": "ć", "ǯ": "č"}
_VOICE = {v: k for k, v in _DEVOICE.items()}
_VOICELESS = set("ptkfsśšcćčx")
_VOICED_OBS = set("bdgzźʒđǯ")  # „w” i „ž” (rz, ż) nie udźwięczniają tu poprzedzającej spółgłoski


@lru_cache(maxsize=1_000_000)
def phon(word: str) -> str:
    """Przybliżony zapis wymowy: ó=u, rz=ż, ch=h, si/ś, ą/ę przed zwartymi, ubezdźwięcznienia i upodobnienia."""
    s = word.lower().replace("ó", "u")
    for a, b in _DIGRAPHS:
        s = s.replace(a, b)
    s = s.replace("h", "x").replace("ż", "ž")
    # zmiękczenia zapisywane przez „i”
    s = re.sub(f"([sczn])i(?=[{VOWELS}])", lambda m: _SOFT[m.group(1)], s)
    s = re.sub("([sczn])i", lambda m: _SOFT[m.group(1)] + "i", s)
    s = re.sub(f"đi(?=[{VOWELS}])", "đ", s)
    # nosówki
    s = re.sub("ą(?=[pb])", "om", s)
    s = re.sub("ę(?=[pb])", "em", s)
    s = re.sub("ą(?=[tdcʒčǯkg])", "on", s)
    s = re.sub("ę(?=[tdcʒčǯkg])", "en", s)
    s = re.sub("ą(?=[ćđ])", "oń", s)
    s = re.sub("ę(?=[ćđ])", "eń", s)
    s = re.sub("ę(?=[lł])", "e", s)
    s = re.sub("ą(?=[lł])", "o", s)
    s = re.sub("ę$", "e", s)
    chars = list(s)
    # ubezdźwięcznienie na końcu wyrazu i wsteczne upodobnienie w grupach spółgłoskowych
    nxt_voiceless = True
    nxt_voiced = False
    for i in range(len(chars) - 1, -1, -1):
        c = chars[i]
        if c in _DEVOICE and nxt_voiceless:
            chars[i] = c = _DEVOICE[c]
        elif c in _VOICE and nxt_voiced:
            chars[i] = c = _VOICE[c]
        nxt_voiceless = c in _VOICELESS
        nxt_voiced = c in _VOICED_OBS
    # postępowe ubezdźwięcznienie „w” i „rz” po bezdźwięcznej (twój, krzak)
    for i in range(1, len(chars)):
        if chars[i] in ("w", "ž") and chars[i - 1] in _VOICELESS:
            chars[i] = _DEVOICE[chars[i]]
    out = "".join(chars)
    return re.sub(r"(.)\1+", r"\1", out)  # geminaty


# --------------------------------------------------------------------------------------
# Leksykon odniesienia
# --------------------------------------------------------------------------------------
class Lexicon:
    """Leksykon odniesienia i statystyki ortotaktyczne."""

    def __init__(self, zipf_frequent: float = 3.0, corpus_forms: Iterable[str] = ()) -> None:
        self.lemmas: dict[str, float] = {}
        skip = {"brev", "ign", "xxx", "frag", "interp", "dig", "romandig", "sym", "xxs"}
        with gzip.open(FREQ_DIR / "kwjp100-slowa-lemma-all.csv.gz", "rt", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split(",")
                if len(p) < 3 or p[1] in skip or not ALPHA_RE.match(p[0]) or len(p[0]) < 2:
                    continue
                try:
                    self.lemmas[p[0]] = self.lemmas.get(p[0], 0.0) + float(p[2])
                except ValueError:
                    continue
        self.lemmas = {w: f for w, f in self.lemmas.items() if morf.is_known(w)}
        self.forms: dict[str, float] = {}
        total = 0.0
        with gzip.open(FREQ_DIR / "kwjp100-slowa-orth_lc-all.csv.gz", "rt", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split(",")
                if len(p) < 2:
                    continue
                try:
                    f = float(p[1])
                except ValueError:
                    continue
                total += f
                if ALPHA_RE.match(p[0]):
                    self.forms[p[0]] = f
        self.forms_total = total
        thr = 10 ** (zipf_frequent - 9) * total
        self.zipf_frequent = zipf_frequent
        self.frequent = sorted(w for w, f in self.forms.items() if f >= thr and len(w) >= 2)
        self.frequent_by_len: dict[int, list[str]] = defaultdict(list)
        for w in self.frequent:
            self.frequent_by_len[len(w)].append(w)
        self.lemma_list = sorted(self.lemmas)
        self.lemma_by_len: dict[int, list[str]] = defaultdict(list)
        for w in self.lemma_list:
            self.lemma_by_len[len(w)].append(w)

        self.worldlex: set[str] = set()
        wl = PSEUDO_DIR / "unipseudo" / "data" / "worldlex_polish_words.tsv"
        if wl.exists():
            with open(wl, encoding="utf-8") as fh:
                next(fh)
                for line in fh:
                    self.worldlex.add(line.split("\t", 1)[0].lower())
        self.corpus_forms = {w for w in corpus_forms if ALPHA_RE.match(w)}

        # statystyki ortotaktyczne na typach (lematach)
        self.trigrams: Counter = Counter()
        self.bigrams: Counter = Counter()
        self.onsets: Counter = Counter()
        self.codas: Counter = Counter()
        self.medials: Counter = Counter()
        self.vowel_seqs: Counter = Counter()
        for w in self.lemma_list:
            p = f"^{w}$"
            self.trigrams.update({p[i:i + 3] for i in range(len(p) - 2)})
            self.bigrams.update(p[i:i + 2] for i in range(len(p) - 1))
            on, co, med = clusters(w)
            self.onsets[on] += 1
            self.codas[co] += 1
            self.medials.update(set(med))
            self.vowel_seqs.update(set(VOWEL_RE.findall(w)))
        self.bigram_total = float(sum(self.bigrams.values()))
        self.phon_index: dict[str, str] = {}
        for w in self.frequent + self.lemma_list:
            self.phon_index.setdefault(phon(w), w)

    def zipf_form(self, form: str) -> float:
        return math.log10((self.forms.get(form, 0.0) + 1.0) / (self.forms_total + 1.0) * 1e9)

    def is_real(self, cand: str) -> str | None:
        """Powód uznania ciągu za istniejące słowo (albo None)."""
        import wordfreq

        if morf.is_known(cand) or morf.is_known(cand.capitalize()):
            return "znane_morfeusz"
        if cand in self.forms:
            return "w_kwjp"
        if cand in self.worldlex:
            return "w_worldlex"
        if wordfreq.zipf_frequency(cand, "pl") > 0:
            return "w_wordfreq"
        if cand in self.corpus_forms:
            return "w_korpusie_zpe"
        return None

    def orthotactic_problem(self, cand: str, min_types: int) -> str | None:
        """Pierwsze naruszenie ortotaktyki (albo None): trigram, nagłos, wygłos, zbitka śródgłosowa, ciąg samogłosek."""
        if not VOWEL_RE.search(cand):
            return "brak samogłoski"
        if re.search(r"(.)\1\1", cand):
            return "potrójna litera"
        on, co, med = clusters(cand)
        if self.onsets[on] < min_types:
            return f"nagłos „{on}”"
        if self.codas[co] < min_types:
            return f"wygłos „{co}”"
        for m in med:
            if self.medials[m] < min_types:
                return f"zbitka „{m}”"
        for v in VOWEL_RE.findall(cand):
            if self.vowel_seqs[v] < min_types:
                return f"samogłoski „{v}”"
        p = f"^{cand}$"
        for i in range(len(p) - 2):
            if self.trigrams[p[i:i + 3]] < min_types:
                return f"trigram „{p[i:i + 3]}”"
        return None

    def min_trigram(self, cand: str) -> int:
        p = f"^{cand}$"
        return min(self.trigrams[p[i:i + 3]] for i in range(len(p) - 2))

    def bigram_logprob(self, word: str) -> float:
        """Średni log10 prawdopodobieństwa bigramu literowego (z granicami wyrazu), wygładzenie 0,5."""
        p = f"^{word}$"
        vals = [math.log10((self.bigrams.get(p[i:i + 2], 0) + 0.5) / self.bigram_total) for i in range(len(p) - 1)]
        return sum(vals) / len(vals)

    def nearest_frequent(self, cand: str, max_dist: int = 1) -> tuple[str, int] | None:
        """Częste słowo (forma) w odległości Damerau-Levenshteina <= max_dist."""
        from rapidfuzz import process
        from rapidfuzz.distance import OSA

        best = None
        for L in range(len(cand) - max_dist, len(cand) + max_dist + 1):
            pool = self.frequent_by_len.get(L)
            if not pool:
                continue
            hit = process.extractOne(cand, pool, scorer=OSA.distance, score_cutoff=max_dist)
            if hit and (best is None or hit[1] < best[1]):
                best = (hit[0], int(hit[1]))
        return best

    def neighbours(self, cand: str) -> list[str]:
        """Sąsiedzi ortograficzni wśród lematów (odległość Levenshteina 1)."""
        from rapidfuzz import process
        from rapidfuzz.distance import Levenshtein

        out = []
        for L in (len(cand) - 1, len(cand), len(cand) + 1):
            pool = self.lemma_by_len.get(L)
            if pool:
                out += [h[0] for h in process.extract(cand, pool, scorer=Levenshtein.distance, score_cutoff=1, limit=None)
                        if h[0] != cand]
        return out

    def old20(self, words: list[str], exclude_self: bool = False) -> list[float]:
        """OLD20: średnia odległość Levenshteina do 20 najbliższych lematów (pełny leksykon, bez próbkowania)."""
        from rapidfuzz import process
        from rapidfuzz.distance import Levenshtein

        out: list[float] = []
        k = 21 if exclude_self else 20
        for start in range(0, len(words), 256):
            chunk = words[start:start + 256]
            d = process.cdist(chunk, self.lemma_list, scorer=Levenshtein.distance, dtype=np.uint8, workers=-1)
            part = np.partition(d, k, axis=1)[:, :k].astype(float)
            part.sort(axis=1)
            for row, w in zip(part, chunk):
                vals = row[1:] if (exclude_self and row[0] == 0) else row[:20]
                out.append(float(vals[:20].mean()))
        return out


def clusters(word: str) -> tuple[str, str, list[str]]:
    """(nagłos, wygłos, zbitki śródgłosowe) – ciągi liter spółgłoskowych; „” gdy wyraz zaczyna/kończy się samogłoską."""
    m = list(CLUSTER_RE.finditer(word))
    onset = m[0].group(0) if m and m[0].start() == 0 else ""
    coda = m[-1].group(0) if m and m[-1].end() == len(word) else ""
    med = [x.group(0) for x in m if x.start() > 0 and x.end() < len(word)]
    return onset, coda, med


# --------------------------------------------------------------------------------------
# Przejrzysta budowa słowotwórcza
# --------------------------------------------------------------------------------------
PREFIXES = [
    "nie", "bez", "do", "na", "nad", "ob", "od", "po", "pod", "prze", "przed", "przy", "roz", "wy", "ws", "wz", "za",
    "anty", "auto", "bio", "eko", "mikro", "makro", "super", "hiper", "pseudo", "pół", "współ", "między", "pra", "arcy",
    "eks", "kontr", "mini", "tele", "foto", "hydro", "elektro", "neo", "para", "poli", "multi", "mono", "inter", "trans",
    "ultra", "wice", "samo", "nowo", "wielo", "jedno", "dwu", "trój", "o", "u", "w", "z", "s",
]
SUFFIXES = [
    "ować", "iwać", "ywać", "anie", "enie", "ość", "owy", "owa", "owe", "ski", "cki", "nik", "arz", "acz", "ista", "ysta",
    "izm", "yzm", "acja", "yjny", "alny", "owiec", "stwo", "ctwo", "isko", "ysko", "arka", "ownia", "arnia", "ątko",
    "ek", "ka", "ko", "ik", "yk", "ny", "ina", "ać", "ić", "yć",
]
STEM_ENDS = ["", "a", "o", "e", "y", "i", "ć", "ać", "ić", "ek", "ka"]
VULGAR = ["kurw", "chuj", "pizd", "jeb", "pierd", "dup", "cip", "kutas", "fiut", "gówn", "gown", "sra", "szczyn",
          "cyc", "pedał", "pedal", "dziwk", "seks", "siur", "pup"]


def transparent_structure(cand: str, lex: Lexicon) -> str | None:
    """Czy ciąg rozkłada się na istniejące cząstki: przedrostek + słowo, rdzeń + przyrostek, słowo + słowo."""
    lem = lex.lemmas
    for pref in PREFIXES:
        rest = cand[len(pref):]
        if cand.startswith(pref) and len(rest) >= (4 if len(pref) > 1 else 5) and (rest in lem or morf.is_known(rest)):
            return f"przedrostek {pref}- + {rest}"
    for suf in SUFFIXES:
        if cand.endswith(suf) and len(cand) - len(suf) >= 3:
            stem = cand[:-len(suf)]
            # rdzeń wprost, z typową końcówką albo z „e” ruchomym (ziomk- ← ziomek)
            variants = [stem + e for e in STEM_ENDS] + [stem[:-1] + "e" + stem[-1]]
            for w in variants:
                f = lem.get(w, 0.0)
                if (len(w) >= 4 and f >= 20) or (len(w) == 3 and f >= 500):
                    return f"{w} + -{suf}"
    for i in range(3, len(cand) - 2):
        a, b = cand[:i], cand[i:]
        if max(len(a), len(b)) < 4:
            continue
        if lem.get(b, 0.0) >= 20 and (lem.get(a, 0.0) >= 20 or (a.endswith("o") and len(a) >= 4 and (
                lem.get(a[:-1], 0.0) >= 20 or lem.get(a[:-1] + "a", 0.0) >= 20))):
            return f"zrost {a} + {b}"
    return None


def vulgar(cand: str) -> str | None:
    p = phon(cand)
    for v in VULGAR:
        if v in cand or phon(v) in p:
            return v
    return None


# --------------------------------------------------------------------------------------
# Ukraiński / rosyjski: transliteracja do polskiej ortografii
# --------------------------------------------------------------------------------------
_BASE = {
    "а": "a", "б": "b", "в": "w", "д": "d", "ж": "ż", "з": "z", "й": "j", "к": "k", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "ch", "ц": "c", "ч": "cz", "ш": "sz", "щ": "szcz",
    "ъ": "", "'": "", "’": "", "ʼ": "", "-": "",
}
_UK = {**_BASE, "г": "h", "ґ": "g", "е": "e", "и": "y", "і": "i", "ї": "ji"}
_RU = {**_BASE, "г": "g", "и": "i", "ы": "y", "э": "e"}
_SOFT_SIGN = {"n": "ń", "s": "ś", "z": "ź", "c": "ć", "t": "ć", "d": "dź", "l": "l"}
_IOT = {"я": "a", "ю": "u", "є": "e", "ё": "o"}
_CYR_VOW = set("аеєиіїоуюяыэё")


def translit(word: str, lang: str) -> str:
    """Słowo ukraińskie lub rosyjskie zapisane polską ortografią (przybliżenie wymowy)."""
    table = _UK if lang == "uk" else _RU
    w = word.lower()
    out: list[str] = []
    for i, ch in enumerate(w):
        prev = w[i - 1] if i else ""
        nxt = w[i + 1] if i + 1 < len(w) else ""
        after_cons = bool(prev) and prev not in _CYR_VOW and prev not in "ьъ'’ʼ"
        if ch == "л":
            soft = nxt in "ьяюєё" or (lang == "uk" and nxt == "і") or (lang == "ru" and nxt in "еи")
            out.append("l" if soft else "ł")
        elif ch == "ь":
            if out and out[-1] in _SOFT_SIGN and nxt not in _CYR_VOW:
                out[-1] = _SOFT_SIGN[out[-1]]
        elif ch in _IOT:
            out.append(("i" if after_cons and prev != "л" else "" if prev == "л" else "j") + _IOT[ch])
        elif ch == "е" and lang == "ru":
            out.append(("ie" if prev != "л" else "e") if after_cons else "je")
        elif ch in table:
            out.append(table[ch])
        else:
            return ""
    return "".join(out)


def ua_ru_index(n: int = 30000) -> dict[str, str]:
    """Zapis wymowy (phon) transliterowanego słowa → „słowo (język)” dla n najczęstszych słów UA i RU."""
    import wordfreq

    idx: dict[str, str] = {}
    for lang in ("uk", "ru"):
        for w in wordfreq.top_n_list(lang, n):
            if len(w) < 3 or not re.fullmatch(r"[а-яёіїєґ'’ʼ-]+", w):
                continue
            t = translit(w, lang)
            if len(t) >= 3 and ALPHA_RE.match(t):
                idx.setdefault(phon(t), f"{w} ({lang})")
    return idx
