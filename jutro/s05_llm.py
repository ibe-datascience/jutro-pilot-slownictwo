"""Krok 5. Klasyfikacja kandydatów przez LLM, ekstrakcja porównawcza i grupowanie w pojęcia (sekcja 5 / 4.2).

Schemat (prompt v2):
  1. Dwa modele (`llm.modele_porownywane`) klasyfikują niezależnie każdego kandydata: kategoria
     (T3 / T3_INNY / T2 / T1 / SZUM), typ szumu, poprawiona forma podstawowa, obrazowalność, pewność.
     Model widzi kandydata, obiektywne statystyki i do 3 zdań z korpusu – NIE widzi etykiety regułowej.
  2. Rozbieżności i przypadki o niskiej pewności dostaje – również „na ślepo” – model rozstrzygający.
     Etykieta końcowa to głos większości; przy trzech różnych głosach wygrywa model rozstrzygający,
     a wiersz jest oznaczany do przeglądu przez człowieka.
  3. Model ekstrakcji wypisuje terminy wprost z próbki materiałów (metoda porównawcza do wzorców z kroku 4).
  4. Model pojęć grupuje końcowe terminy T3 w pojęcia (synonimy i warianty) w jednym żądaniu.

Wyjście:
  llm_klasyfikacja.parquet, llm_ekstrakcja.jsonl, llm_pojecia.json, llm.done
  wyniki/.../terminy_llm_spoza_kandydatow.csv
Metryki: llm_5.json (zgodność między modelami, koszty; NIE trafność – brak etykiet ludzkich).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import llm
from .common import Ctx, Timer, log, read_jsonl
from .s04_kandydaci import term_lemma_keys

CAT_ENUM = ["T3", "T3_INNY", "T2", "T1", "SZUM"]
NOISE_ENUM = ["brak", "fragment_terminu", "luzne_polaczenie", "nazwa_wlasna", "blad_ekstrakcji", "interfejs", "inne"]
CLASS_SCHEMA = {
    "type": "object",
    "properties": {
        "uzasadnienie": {"type": "string"},
        "kategoria": {"type": "string", "enum": CAT_ENUM},
        "typ_szumu": {"type": "string", "enum": NOISE_ENUM},
        "forma_poprawna": {"type": "string"},
        "pelny_termin": {"type": "string"},
        "obrazowalnosc": {"type": "string", "enum": ["tak", "czesciowo", "nie"]},
        "pewnosc": {"type": "string", "enum": ["wysoka", "srednia", "niska"]},
    },
    "required": ["uzasadnienie", "kategoria", "typ_szumu", "forma_poprawna", "pelny_termin", "obrazowalnosc", "pewnosc"],
    "additionalProperties": False,
}

CLASS_SYSTEM = """Jesteś dydaktykiem biologii i językoznawcą. Pomagasz przygotować materiał słowny do testu JUTRO dla uczniów klas 5–8 szkoły podstawowej, w tym uczniów z doświadczeniem migracyjnym. Test ma oddzielić znajomość polszczyzny ogólnej od znajomości pojęć z biologii, dlatego każde słowo trzeba przypisać do jednej warstwy słownictwa.

Dostajesz JEDNEGO kandydata: słowo albo wyrażenie w formie podstawowej, wydobyte automatycznie z materiałów Zintegrowanej Platformy Edukacyjnej (ZPE), jego statystyki oraz do 3 zdań, w których wystąpił. Oceniaj znaczenie, w jakim kandydat występuje w tych zdaniach.

KATEGORIE

T3 – termin biologiczny. Nazwa pojęcia, którego uczeń uczy się na lekcjach biologii lub przyrody: struktury i narządy (chloroplast, tchawica, aparat szparkowy), procesy (fotosynteza, kiełkowanie, trawienie), grupy organizmów i gatunki poznawane w szkole (stawonóg, pantofelek, porost), pojęcia ekologii, genetyki, zdrowia i metody badawczej biologii (łańcuch pokarmowy, allel, próba kontrolna). Także:
 – przymiotniki, które samodzielnie klasyfikują organizmy lub procesy (samożywny, zmiennocieplny, jednokomórkowy);
 – czasowniki i rzeczowniki odczasownikowe nazywające procesy biologiczne (kiełkować, oddychanie komórkowe);
 – pojęcia chemii i fizyki, których naucza się w biologii jako części jej treści (dwutlenek węgla, białko, enzym).
Kryterium: to znaczenie uczeń poznaje w szkole na biologii, a nie w domu.

T3_INNY – termin innego przedmiotu szkolnego (matematyka, fizyka, chemia, geografia, historia, język polski, informatyka itd.), który nie należy do treści biologii: mianownik, epitet, napięcie elektryczne, południk, rozbiory.

T2 – słownictwo szkolno-akademickie wspólne dla wielu przedmiotów: język nauczania, podręczników i poleceń. Słowa rzadsze w potocznej mowie dzieci, ale nieprzypisane do jednej dziedziny: analizować, uzasadnić, wniosek, hipoteza, cecha, czynnik, proces, funkcja, występować, przystosowanie, zjawisko, porównanie, na podstawie, znaczenie, rodzaj, budowa (czegoś), wpływ.

T1 – słownictwo codzienne, które dziecko zna z domu i podwórka niezależnie od szkoły: pies, drzewo, ręka, serce, woda, jeść, duży, biegać, choroba, kwiat, ryba. Powszechnie znane nazwy zwierząt, roślin i części ciała to T1, nawet jeśli pojawiają się na biologii. Granica T1/T3: jeśli typowy dziesięciolatek zna słowo i jego znaczenie bez lekcji biologii – T1; jeśli poznaje je dopiero w szkole (tchawica, trzustka, pręcik) – T3.

SZUM – jednostka nie nadaje się na pozycję testu. Podaj typ:
 – fragment_terminu: część większego terminu bez samodzielnego znaczenia terminologicznego: przymiotnik występujący tylko w stałej nazwie („gębowy” ← „aparat gębowy”, „pławny” ← „pęcherz pławny”), ucięta fraza („choroba układu” ← „choroba układu krążenia”). Pełny termin wpisz w `pelny_termin`.
 – luzne_polaczenie: zwykłe zestawienie słów, a nie ustalony termin ani wyrażenie („duża ilość”, „organizm człowieka”, „różne rośliny”, „budowa liścia”). Wyrażenie wielowyrazowe jest T3 tylko wtedy, gdy mogłoby być hasłem w słowniku biologicznym lub w indeksie podręcznika.
 – nazwa_wlasna: imię, nazwisko, nazwa geograficzna, instytucja, tytuł.
 – blad_ekstrakcji: nie-słowo, błędny lemat, którego nie da się naprawić, zlepek bez sensu.
 – interfejs: tekst platformy lub polecenie techniczne (ćwiczenie interaktywne, rozwijana lista, wersja alternatywna).
 – inne: pozostałe przypadki (skrótowce bez znaczenia, słowa obce itp.).
Dla kategorii innych niż SZUM wpisz typ_szumu = "brak".

POLA ODPOWIEDZI

uzasadnienie – najwyżej 15 słów: co przesądza o kategorii.
kategoria, typ_szumu – jak wyżej.
forma_poprawna – forma podstawowa TEJ SAMEJ jednostki: mianownik liczby pojedynczej (rzeczownik, przymiotnik w rodzaju męskim), bezokolicznik (czasownik), cała fraza w mianowniku. Jeśli kandydat jest zapisany poprawnie, przepisz go bez zmian. Popraw tylko błąd lematyzacji (np. „odwłoka” → „odwłok”, „szkolny koł” → „szkolne koło”). Liczbę mnogą zostaw tylko dla wyrazów, które nie mają liczby pojedynczej (drożdże, nożyczki). NIE dodawaj ani nie usuwaj wyrazów i NIE rozszerzaj fragmentu do pełnego terminu.
pelny_termin – tylko dla fragment_terminu: pełny termin, którego częścią jest kandydat; w pozostałych przypadkach pusty napis.
obrazowalnosc – czy znaczenie da się jednoznacznie pokazać uczniowi na ilustracji, zdjęciu lub schemacie: tak (konkretny obiekt lub struktura: liść, szkielet, mitochondrium), czesciowo (proces lub relacja możliwa do pokazania schematem: fotosynteza, łańcuch pokarmowy), nie (pojęcie abstrakcyjne: przystosowanie, wniosek).
pewnosc – wysoka, srednia albo niska. Wybierz „niska”, gdy wahasz się między dwiema kategoriami.

WSKAZÓWKI

 – Statystyki są wskazówką, nie regułą: termin biologiczny zwykle jest częsty w biologii i rzadki gdzie indziej, słownictwo T2 występuje w wielu przedmiotach, a T1 ma wysoką frekwencję w polszczyźnie ogólnej (skala Zipfa około 4,5 i więcej). O kategorii decyduje jednak znaczenie.
 – Wyraz wieloznaczny oceniaj w znaczeniu z podanych zdań („komórka” w zdaniu o organizmach to T3, „tkanka” to T3, „klucz” w zdaniu o oznaczaniu gatunków to T3, a w zdaniu o drzwiach – T1).
 – Kandydat bez zdań z biologii pochodzi z innych przedmiotów; najczęściej będzie to T2, T1 albo T3_INNY.

PRZYKŁADY

Kandydat: aparat szparkowy → {"uzasadnienie": "Struktura skórki liścia poznawana na biologii.", "kategoria": "T3", "typ_szumu": "brak", "forma_poprawna": "aparat szparkowy", "pelny_termin": "", "obrazowalnosc": "tak", "pewnosc": "wysoka"}
Kandydat: gębowy → {"uzasadnienie": "Przymiotnik występuje tylko w nazwie „aparat gębowy”.", "kategoria": "SZUM", "typ_szumu": "fragment_terminu", "forma_poprawna": "gębowy", "pelny_termin": "aparat gębowy", "obrazowalnosc": "nie", "pewnosc": "wysoka"}
Kandydat: zmiennocieplny → {"uzasadnienie": "Samodzielny przymiotnik klasyfikujący zwierzęta, treść biologii.", "kategoria": "T3", "typ_szumu": "brak", "forma_poprawna": "zmiennocieplny", "pelny_termin": "", "obrazowalnosc": "czesciowo", "pewnosc": "wysoka"}
Kandydat: wniosek → {"uzasadnienie": "Słowo języka szkolnego używane na wszystkich przedmiotach.", "kategoria": "T2", "typ_szumu": "brak", "forma_poprawna": "wniosek", "pelny_termin": "", "obrazowalnosc": "nie", "pewnosc": "wysoka"}
Kandydat: ryba → {"uzasadnienie": "Powszechnie znana nazwa zwierzęcia, znana bez nauki szkolnej.", "kategoria": "T1", "typ_szumu": "brak", "forma_poprawna": "ryba", "pelny_termin": "", "obrazowalnosc": "tak", "pewnosc": "srednia"}
Kandydat: organizm człowieka → {"uzasadnienie": "Zwykłe połączenie rzeczownika z dopełniaczem, nie ustalony termin.", "kategoria": "SZUM", "typ_szumu": "luzne_polaczenie", "forma_poprawna": "organizm człowieka", "pelny_termin": "", "obrazowalnosc": "czesciowo", "pewnosc": "srednia"}
Kandydat: odwłoka → {"uzasadnienie": "Błędny lemat słowa „odwłok”, części ciała stawonogów.", "kategoria": "T3", "typ_szumu": "brak", "forma_poprawna": "odwłok", "pelny_termin": "", "obrazowalnosc": "tak", "pewnosc": "wysoka"}
Kandydat: ułamek → {"uzasadnienie": "Pojęcie matematyki, nie biologii.", "kategoria": "T3_INNY", "typ_szumu": "brak", "forma_poprawna": "ułamek", "pelny_termin": "", "obrazowalnosc": "czesciowo", "pewnosc": "wysoka"}
Kandydat: rozwijana lista → {"uzasadnienie": "Element interfejsu ćwiczenia na platformie.", "kategoria": "SZUM", "typ_szumu": "interfejs", "forma_poprawna": "rozwijana lista", "pelny_termin": "", "obrazowalnosc": "nie", "pewnosc": "wysoka"}
Kandydat: występować → {"uzasadnienie": "Czasownik języka podręczników wspólny dla wielu przedmiotów.", "kategoria": "T2", "typ_szumu": "brak", "forma_poprawna": "występować", "pelny_termin": "", "obrazowalnosc": "nie", "pewnosc": "wysoka"}

Odpowiedz wyłącznie obiektem JSON zgodnym ze schematem."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "terminy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "forma_podstawowa": {"type": "string"},
                    "kategoria": {"type": "string", "enum": ["T3", "T2"]},
                },
                "required": ["forma_podstawowa", "kategoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["terminy"],
    "additionalProperties": False,
}
EXTRACT_SYSTEM = (
    "Dostajesz tekst jednego materiału z biologii (szkoła podstawowa, klasy 5–8) z platformy ZPE. "
    "Wypisz wszystkie terminy, których znajomość jest potrzebna do zrozumienia tego materiału:\n"
    " – T3: terminy biologiczne (jedno- i wielowyrazowe), które uczeń poznaje na lekcjach biologii;\n"
    " – T2: słownictwo szkolno-akademickie wspólne dla wielu przedmiotów (np. hipoteza, czynnik, występować).\n"
    "Zasady: forma podstawowa (mianownik liczby pojedynczej, bezokolicznik), małymi literami; tylko jednostki, "
    "które rzeczywiście występują w tekście (w dowolnej formie fleksyjnej); bez słów codziennych, nazw własnych "
    "i tekstów interfejsu; wyrażenie wielowyrazowe tylko wtedy, gdy jest ustalonym terminem, a nie luźnym "
    "połączeniem słów; każda jednostka raz. Najwyżej 120 pozycji, najważniejsze najpierw."
)

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "grupy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pojecie": {"type": "string"},
                    "terminy": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["pojecie", "terminy"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["grupy"],
    "additionalProperties": False,
}
CONCEPT_SYSTEM = (
    "Dostajesz listę terminów biologicznych (szkoła podstawowa), po jednym w wierszu. Znajdź grupy terminów, "
    "które nazywają TO SAMO pojęcie, tak aby w teście nie pytać dwa razy o to samo:\n"
    " – synonimy (erytrocyt = krwinka czerwona = czerwona krwinka; cudzożywność = heterotrofizm),\n"
    " – warianty szyku i zapisu (błona komórkowa = komórkowa błona),\n"
    " – formy słowotwórcze tego samego pojęcia: rzeczownik, przymiotnik i czasownik (fotosynteza, fotosyntetyczny; "
    "kiełkowanie, kiełkować; samożywny, samożywność).\n"
    "NIE łącz pojęcia nadrzędnego z podrzędnym (komórka ≠ komórka jajowa; układ ≠ układ krwionośny), części z całością "
    "(liść ≠ blaszka liściowa) ani pojęć pokrewnych, ale różnych (tętnica ≠ żyła).\n"
    "Zwróć tylko grupy liczące co najmniej 2 terminy z listy. `pojecie` to najbardziej typowa nazwa pojęcia "
    "(jeden z terminów grupy). Terminy przepisuj dokładnie tak, jak na liście; każdy termin najwyżej w jednej grupie."
)


def _short(model: str) -> str:
    return model.replace("claude-", "").replace("-", "_")


def _cid(form: str) -> str:
    return "C" + hashlib.sha1(form.encode()).hexdigest()[:15]


# --------------------------------------------------------------------------------------
def _select_subject(df: pd.DataFrame, top: int) -> pd.DataFrame:
    subj = df[df["kand_przedmiotowy"]]
    if len(subj) <= top:
        return subj.copy()
    chosen = set(subj.nsmallest(top, "rank_rrf")["forma_podstawowa"])
    for col in ["ll_vs_kontrast", "simple_maths_kwjp", "tfidf_biol", "cvalue", "logdice", "pmi"]:
        chosen |= set(subj.nsmallest(max(top // 10, 50), f"rank_{col}")["forma_podstawowa"])
    return subj[subj["forma_podstawowa"].isin(chosen)].copy()


def _select_general(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Próba kandydatów ogólnych o rozkładzie frekwencji zbliżonym do prawdopodobnych terminów.

    Terminy są rzadkie w polszczyźnie ogólnej, a słowa szeroko rozproszone po przedmiotach – częste. Żeby pulę
    ogólną dało się dopasować frekwencyjnie do puli przedmiotowej, kwoty w przedziałach skali Zipfa są
    proporcjonalne do rozkładu kandydatów wyraźnie częstszych w biologii (log ratio >= 1); w przedziale
    pierwszeństwo mają jednostki obecne w większej liczbie przedmiotów.
    """
    gen = df[df["kand_ogolny"] & ~df["kand_przedmiotowy"]].copy()
    if len(gen) <= n:
        return gen
    key = lambda d: np.where(d["dlugosc"] == 1, d["zipf_kwjp"], d["zipf_zpe"])  # noqa: E731
    bins = np.arange(0.0, 8.5, 0.5)
    gen["_bin"] = np.digitize(key(gen), bins) + 100 * (gen["dlugosc"] > 1)
    ref = df[df["kand_przedmiotowy"] & (df["log_ratio_kontrast"] >= 1.0)]
    ref_bins = pd.Series(np.digitize(key(ref), bins) + 100 * (ref["dlugosc"] > 1).to_numpy()).value_counts()
    avail = gen["_bin"].value_counts()
    share = (ref_bins.reindex(avail.index).fillna(0) + 1.0)
    quota = (share / share.sum() * n).round().astype(int)
    take = {b: int(min(quota[b], avail[b])) for b in avail.index}
    left = n - sum(take.values())
    while left > 0:
        spare = [b for b in avail.index if take[b] < avail[b]]
        if not spare:
            break
        for b in sorted(spare, key=lambda x: -share[x]):
            if left <= 0:
                break
            take[b] += 1
            left -= 1
    parts = []
    for b, k in take.items():
        g = gen[gen["_bin"] == b].sort_values(["n_przedmiotow", "n_mat_kontrast", "forma_podstawowa"],
                                              ascending=[False, False, True])
        parts.append(g.head(k))
    return pd.concat(parts).drop(columns="_bin")


def _contexts(ctx: Ctx) -> dict[str, list[tuple[bool, str, str]]]:
    k = pq.read_table(ctx.data / "kandydaci_konteksty.parquet").to_pandas()
    out: dict[str, list[tuple[bool, str, str]]] = defaultdict(list)
    for f, cel, subj, text in zip(k["forma_podstawowa"], k["cel"], k["przedmiot"], k["tekst"]):
        out[f].append((bool(cel), subj, text))
    return out


def context_lines(ctxs: list[tuple[bool, str, str]], subject_first: bool, n: int = 3) -> list[str]:
    """Do n zdań: dla kandydata przedmiotowego najpierw z korpusu docelowego, dla ogólnego – z kontrastu."""
    ordered = sorted(ctxs, key=lambda c: (c[0] != subject_first))
    return [f"[{s}] {t}" for _c, s, t in ordered[:n]]


def _prompt_item(row: pd.Series, lines: list[str], n_mat_cel: int, n_subj: int, cel_name: str) -> str:
    z = row["zipf_kwjp"]
    zipf = f"{z:.1f}" if z == z else "brak danych (wyrażenie wielowyrazowe)"
    ctx = "\n".join(f"- {c}" for c in lines) if lines else "(brak zdań)"
    return (
        f"Kandydat: {row['forma_podstawowa']}\n"
        f"Liczba wyrazów: {int(row['dlugosc'])}\n"
        f"Przedmiot {cel_name}: {int(row['freq_cel'])} wystąpień w {int(row['n_mat_cel'])} z {n_mat_cel} materiałów\n"
        f"Inne przedmioty: {int(row['freq_kontrast'])} wystąpień, {int(row['n_przedmiotow'])} z {n_subj} przedmiotów\n"
        f"Frekwencja w polszczyźnie ogólnej (skala Zipfa 1–7): {zipf}\n"
        f"Zdania:\n{ctx}"
    )


def _cohen_kappa(a: list[str], b: list[str]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    pa_ = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((sum(x == c for x in a) / n) * (sum(x == c for x in b) / n) for c in cats)
    if pe >= 1:
        return 1.0
    return round((pa_ - pe) / (1 - pe), 4)


def _agreement(out: pd.DataFrame, ca: str, cb: str) -> dict[str, Any]:
    sub = out.dropna(subset=[ca, cb])
    a, b = sub[ca].tolist(), sub[cb].tolist()
    return {"n": len(sub), "prosta": round(sum(x == y for x, y in zip(a, b)) / len(a), 4) if a else None,
            "kappa": _cohen_kappa(a, b)}


# --------------------------------------------------------------------------------------
def _classify(ctx: Ctx, df: pd.DataFrame) -> pd.DataFrame:
    kc = ctx.cfg["kandydaci"]
    sub = pd.concat([
        _select_subject(df, int(kc["top_do_llm"])),
        _select_general(df, int(kc.get("ogolne_do_llm", 1500)), ctx.seed),
    ]).drop_duplicates("forma_podstawowa").reset_index(drop=True)
    m42 = ctx.load_metrics("ekstrakcja_42", {}) or {}
    n_subj = int((m42.get("mianowniki") or {}).get("przedmioty_kontrastu") or 0)
    opis = ctx.load_metrics("opis_danych", {}) or {}
    n_mat_cel = int(opis.get("materialy_cel") or 0)
    cel_name = str(ctx.cfg["cel"]["przedmiot"]).lower()
    ctx_map = _contexts(ctx)

    items, by_id = [], {}
    for _, row in sub.iterrows():
        f = row["forma_podstawowa"]
        lines = context_lines(ctx_map.get(f, []), bool(row["kand_przedmiotowy"]))
        cid = _cid(f)
        items.append((cid, _prompt_item(row, lines, n_mat_cel, n_subj, cel_name)))
        by_id[cid] = f
    text_by_id = dict(items)
    log(f"s05: klasyfikacja {len(items)} kandydatów "
        f"({int(sub['kand_przedmiotowy'].sum())} przedmiotowych, {int((~sub['kand_przedmiotowy']).sum())} ogólnych)…")

    models = list(ctx.cfg["llm"]["modele_porownywane"])
    judge = ctx.cfg["llm"]["model_rozstrzygajacy"]
    batch = bool(ctx.cfg["llm"].get("batch", True))
    results = {m: llm.run_requests(ctx, "klasyfikacja_v2", m, CLASS_SYSTEM, items, CLASS_SCHEMA,
                                   max_tokens=500, batch=batch, est_out_tokens=120) for m in models}

    need = []
    for cid in by_id:
        labs = [results[m].get(cid, {}).get("kategoria") for m in models]
        pew = [results[m].get(cid, {}).get("pewnosc") for m in models]
        if None in labs or len(set(labs)) > 1 or "niska" in pew:
            need.append((cid, text_by_id[cid]))
    log(f"s05: {judge} rozstrzyga {len(need)} przypadków…")
    judged = llm.run_requests(ctx, "klasyfikacja_v2_rozstrzygniecie", judge, CLASS_SYSTEM, need, CLASS_SCHEMA,
                              max_tokens=500, batch=batch, est_out_tokens=250) if need else {}

    fields = ["kategoria", "typ_szumu", "forma_poprawna", "pelny_termin", "obrazowalnosc", "pewnosc", "uzasadnienie"]
    stat = sub.set_index("forma_podstawowa")
    rows = []
    for cid, form in by_id.items():
        row: dict[str, Any] = {"id": cid, "forma_wejsciowa": form}
        votes: list[tuple[str, dict]] = []
        for m in models:
            r = results[m].get(cid) or {}
            for k in fields:
                row[f"{_short(m)}_{k}"] = r.get(k)
            if r.get("kategoria"):
                votes.append((m, r))
        j = judged.get(cid) or {}
        for k in fields:
            row[f"sedzia_{k}"] = j.get(k)
        row["model_sedzia"] = judge if j else None
        if j.get("kategoria"):
            votes.append((judge, j))
        cnt = Counter(r["kategoria"] for _m, r in votes)
        if not votes:
            final, src, review, zg = None, None, True, "brak odpowiedzi"
        else:
            top, n_top = cnt.most_common(1)[0]
            if len(votes) == 2 and n_top == 2 and not j:
                final, review, zg = top, False, "2 z 2"
            elif n_top >= 2:
                final, review, zg = top, False, f"{n_top} z {len(votes)}"
            else:  # każdy głos inny (albo tylko jeden głos)
                final = j.get("kategoria") or votes[-1][1]["kategoria"]
                review, zg = True, f"1 z {len(votes)}"
            # pola opisowe: od sędziego, jeśli jego etykieta jest końcowa; inaczej od ostatniego (mocniejszego) modelu
            src = next(r for _m, r in reversed(votes) if r["kategoria"] == final)
            if j.get("pewnosc") == "niska" and j.get("kategoria") == final:
                review = True
        row["kategoria_final"] = final
        row["zgodnosc_glosow"] = zg
        row["do_przegladu"] = review
        src = src or {}
        row["typ_szumu"] = (src.get("typ_szumu") or "brak") if final == "SZUM" else "brak"
        fp = (src.get("forma_poprawna") or "").strip().lower()
        # poprawka formy jest przyjmowana tylko wtedy, gdy nie zmienia liczby wyrazów
        row["forma_poprawna"] = fp if fp and len(fp.split()) == len(form.split()) else form
        row["pelny_termin"] = (src.get("pelny_termin") or "").strip().lower() if row["typ_szumu"] == "fragment_terminu" else ""
        row["obrazowalnosc"] = src.get("obrazowalnosc")
        st = stat.loc[form]
        row["kand_przedmiotowy"], row["kand_ogolny"] = bool(st["kand_przedmiotowy"]), bool(st["kand_ogolny"])
        row["dlugosc"] = int(st["dlugosc"])
        row["etykieta_regulowa"] = st["etykieta_regulowa"]
        rows.append(row)
    return pd.DataFrame(rows)


def _extract(ctx: Ctx, out: pd.DataFrame, df: pd.DataFrame) -> dict[str, Any]:
    """Ekstrakcja terminów wprost z materiałów + porównanie z kandydatami wzorcowymi."""
    rng = ctx.rng("llm_ekstrakcja")
    mats = [r for r in read_jsonl(ctx.data / "korpus.jsonl") if r["cel"] and r.get("n_slow", 0) >= 150]
    rng.shuffle(mats)
    n_ext = min(int(ctx.cfg["llm"].get("n_materialow_ekstrakcja", 30)), len(mats))
    stat = set(ctx.cfg["czyszczenie"]["segmenty_do_statystyk"])
    items = []
    for r in mats[:n_ext]:
        text = "\n".join(s["tekst"] for s in r["segmenty"] if s["typ"] in stat)[:24000]
        items.append((r["id"][:64], f"Tytuł: {r['tytul']}\n\n{text}"))
    model = ctx.cfg["llm"]["model_ekstrakcji"]
    log(f"s05: ekstrakcja LLM z {len(items)} materiałów ({model})…")
    ext = llm.run_requests(ctx, "ekstrakcja_terminow_v2", model, EXTRACT_SYSTEM, items, EXTRACT_SCHEMA,
                           max_tokens=8000, batch=bool(ctx.cfg["llm"].get("batch", True)), est_out_tokens=1500)
    with open(ctx.data / "llm_ekstrakcja.jsonl", "w", encoding="utf-8") as fh:
        for mid, payload in ext.items():
            fh.write(json.dumps({"material_id": mid, **payload}, ensure_ascii=False) + "\n")

    subj = df[df["kand_przedmiotowy"]]
    by_lem = dict(zip(subj["lematy"], subj["forma_podstawowa"]))
    by_form = set(subj["forma_podstawowa"])
    final = dict(zip(out["forma_wejsciowa"], out["kategoria_final"]))
    terms: dict[str, dict[str, Any]] = {}
    for mid, payload in ext.items():
        for tr in payload.get("terminy", []):
            f = str(tr.get("forma_podstawowa", "")).strip().lower()
            if not f:
                continue
            rec = terms.setdefault(f, {"termin": f, "kategoria_ekstrakcji": tr.get("kategoria"), "n_materialow": 0})
            rec["n_materialow"] += 1
    rows = []
    for f, rec in terms.items():
        cand = f if f in by_form else next((by_lem[k] for k in term_lemma_keys(f) if k in by_lem), None)
        rec["kandydat"] = cand
        rec["kategoria_kandydata"] = final.get(cand) if cand else None
        rec["dlugosc"] = len(f.split())
        rows.append(rec)
    tdf = pd.DataFrame(rows)
    res: dict[str, Any] = {"model": model, "n_materialow": n_ext, "n_odpowiedzi": len(ext), "n_terminow": int(len(tdf))}
    if len(tdf):
        t3 = tdf[tdf["kategoria_ekstrakcji"] == "T3"]
        res.update({
            "n_terminow_T3": int(len(t3)),
            "n_terminow_T3_wielowyrazowych": int((t3["dlugosc"] > 1).sum()),
            "T3_wsrod_kandydatow": round(float(t3["kandydat"].notna().mean()), 4) if len(t3) else None,
            "T3_jednowyrazowe_wsrod_kandydatow": round(float(t3.loc[t3["dlugosc"] == 1, "kandydat"].notna().mean()), 4)
            if (t3["dlugosc"] == 1).any() else None,
            "T3_wielowyrazowe_wsrod_kandydatow": round(float(t3.loc[t3["dlugosc"] > 1, "kandydat"].notna().mean()), 4)
            if (t3["dlugosc"] > 1).any() else None,
            "T3_z_etykieta_koncowa_T3": round(float((t3["kategoria_kandydata"] == "T3").mean()), 4) if len(t3) else None,
            "uwaga": "Terminy wypisane przez model z próbki materiałów; kandydat = jednostka z kroku 4 po progach "
                     "frekwencji. Termin spoza kandydatów mógł wystąpić za rzadko albo nie pasować do wzorca składniowego.",
        })
        tdf[tdf["kandydat"].isna()].sort_values(["n_materialow", "termin"], ascending=[False, True]) \
            .drop(columns=["kandydat", "kategoria_kandydata"]).to_csv(ctx.out / "terminy_llm_spoza_kandydatow.csv", index=False)
    return res


def _concepts(ctx: Ctx, out: pd.DataFrame) -> dict[str, Any]:
    """Grupowanie końcowych terminów T3 w pojęcia – jedno żądanie na całą listę."""
    terms = sorted(set(out.loc[out["kategoria_final"] == "T3", "forma_poprawna"].dropna()))
    path = ctx.data / "llm_pojecia.json"
    if len(terms) < 2:
        path.write_text(json.dumps({"grupy": []}), encoding="utf-8")
        return {"n_terminow": len(terms), "n_grup": 0}
    model = ctx.cfg["llm"].get("model_pojec") or ctx.cfg["llm"]["model_rozstrzygajacy"]
    log(f"s05: grupowanie {len(terms)} terminów T3 w pojęcia ({model})…")
    user = "Terminy:\n" + "\n".join(terms)
    res = llm.run_requests(ctx, "pojecia_v2", model, CONCEPT_SYSTEM, [("pojecia", user)], CONCEPT_SCHEMA,
                           max_tokens=48000, batch=True, min_batch=1, est_out_tokens=12000)
    groups_raw = (res.get("pojecia") or {}).get("grupy") or []
    known, used, groups, n_unknown = set(terms), set(), [], 0
    for g in groups_raw:
        ts = []
        for x in g.get("terminy", []):
            x = str(x).strip().lower()
            if x not in known:
                n_unknown += 1
            elif x not in used:
                ts.append(x)
        if len(ts) >= 2:
            used.update(ts)
            name = str(g.get("pojecie", "")).strip().lower()
            groups.append({"pojecie": name if name in ts else ts[0], "terminy": ts})
    path.write_text(json.dumps({"grupy": groups, "model": model}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"model": model, "n_terminow": len(terms), "n_grup": len(groups), "n_terminow_w_grupach": len(used),
            "n_terminow_spoza_listy_pominietych": n_unknown, "odpowiedz_otrzymana": bool(res.get("pojecia"))}


def run(ctx: Ctx) -> None:
    t = Timer()
    if getattr(ctx, "bez_llm", False) and not (ctx.data / "llm" / "koszty.jsonl").exists():
        log("s05: --bez-llm – pomijam wywołania API")
        (ctx.data / "llm.done").write_text("skipped\n", encoding="utf-8")
        return
    df = pq.read_table(ctx.data / "kandydaci_stat.parquet").to_pandas()
    out = _classify(ctx, df)
    pq.write_table(pa.Table.from_pandas(out, preserve_index=False), ctx.data / "llm_klasyfikacja.parquet", compression="zstd")

    ext_metrics = _extract(ctx, out, df)
    concept_metrics = _concepts(ctx, out)

    # --- metryki: zgodność (nie trafność!)
    models = list(ctx.cfg["llm"]["modele_porownywane"])
    sa, sb = _short(models[0]), _short(models[1])
    ca, cb = f"{sa}_kategoria", f"{sb}_kategoria"
    segments = {
        "wszystkie": out,
        "przedmiotowe": out[out["kand_przedmiotowy"]],
        "tylko_ogolne": out[~out["kand_przedmiotowy"]],
        "jednowyrazowe": out[out["dlugosc"] == 1],
        "wielowyrazowe": out[out["dlugosc"] > 1],
    }
    agree = {name: _agreement(seg, ca, cb) for name, seg in segments.items()}
    both = out.dropna(subset=[ca, cb])
    confusion = pd.crosstab(both[ca], both[cb]).to_dict()
    vs_final = {s: _agreement(out, f"{s}_kategoria", "kategoria_final") for s in (sa, sb)}
    jd = out[out["sedzia_kategoria"].notna()]
    judge_stats = {
        "n": int(len(jd)),
        "zgodny_z": {s: int((jd[f"{s}_kategoria"] == jd["sedzia_kategoria"]).sum()) for s in (sa, sb)},
        "inny_niz_oba": int(((jd[ca] != jd["sedzia_kategoria"]) & (jd[cb] != jd["sedzia_kategoria"])).sum()),
        "powod_rozbieznosc_etykiet": int((jd[ca] != jd[cb]).sum()),
        "powod_niska_pewnosc_przy_zgodzie": int((jd[ca] == jd[cb]).sum()),
    }
    # punkt odniesienia: etykiety regułowe z kroku 4 wobec etykiety końcowej (kandydaci przedmiotowi)
    sp = out[out["kand_przedmiotowy"] & out["kategoria_final"].notna()].copy()
    sp["_rule"] = sp["etykieta_regulowa"].str.replace("?", "", regex=False)
    sp["_fin"] = sp["kategoria_final"].replace({"T3_INNY": "inne", "SZUM": "inne"})
    dec = sp[sp["_rule"].isin(["T1", "T2", "T3"])]
    rule = {
        "n_kandydatow_przedmiotowych": int(len(sp)),
        "regula_rozstrzygnela": int(len(dec)),
        "zgodnosc_z_etykieta_koncowa": round(float((dec["_rule"] == dec["_fin"]).mean()), 4) if len(dec) else None,
        "precyzja_T3_reguly": round(float((dec.loc[dec["_rule"] == "T3", "_fin"] == "T3").mean()), 4)
        if (dec["_rule"] == "T3").any() else None,
        "pelnosc_T3_reguly": round(float((sp.loc[sp["_fin"] == "T3", "_rule"] == "T3").mean()), 4)
        if (sp["_fin"] == "T3").any() else None,
    }
    # metody rankingowe wobec etykiety końcowej T3 (tylko gdy sklasyfikowano wszystkich kandydatów przedmiotowych)
    subj_all = df[df["kand_przedmiotowy"]]
    final = dict(zip(out["forma_wejsciowa"], out["kategoria_final"]))
    methods_vs_llm: dict[str, Any] = {}
    if subj_all["forma_podstawowa"].isin(final).all():
        lab = subj_all.assign(_t3=subj_all["forma_podstawowa"].map(final) == "T3")
        cols = {"ll_kontrast": "ll_vs_kontrast", "log_ratio_kontrast": "log_ratio_kontrast", "tfidf_biol": "tfidf_biol",
                "simple_maths_kwjp": "simple_maths_kwjp", "ll_kwjp": "ll_vs_kwjp", "pmi_mwu": "pmi", "logdice_mwu": "logdice",
                "cvalue_termopl": "cvalue", "rrf": "rrf", "frekwencja_cel": "freq_cel"}
        univ = {"wszystkie": lab, "jednowyrazowe": lab[lab["dlugosc"] == 1], "wielowyrazowe": lab[lab["dlugosc"] > 1]}
        methods_vs_llm["poziom_odniesienia"] = {u: round(float(d["_t3"].mean()), 4) for u, d in univ.items()}
        for name, col in cols.items():
            methods_vs_llm[name] = {}
            for u, d in univ.items():
                r = d[d[col].notna()].sort_values(col, ascending=False)
                if len(r) < 50:
                    continue
                n_t3 = int(r["_t3"].sum())
                methods_vs_llm[name][u] = {"n_ranking": int(len(r)), "n_T3": n_t3, **{
                    f"p@{k}": round(float(r["_t3"].head(k).mean()), 4) for k in (100, 300, 1000)}, **{
                    f"r@{k}": round(float(r["_t3"].head(k).sum() / n_t3), 4) if n_t3 else None for k in (100, 300, 1000)}}

    costs = defaultdict(float)
    for r in llm.cost_summary(ctx):
        costs[f"{r['zadanie']} / {r['model']}"] += r.get("koszt_usd", 0.0)
    metrics = {
        "wersja_promptu": ctx.cfg["llm"].get("wersja_promptu"),
        "modele": {"porownywane": models, "rozstrzygajacy": ctx.cfg["llm"]["model_rozstrzygajacy"],
                   "ekstrakcji": ctx.cfg["llm"]["model_ekstrakcji"], "pojec": concept_metrics.get("model")},
        "n_klasyfikowanych": int(len(out)),
        "n_klasyfikowanych_przedmiotowych": int(out["kand_przedmiotowy"].sum()),
        "n_klasyfikowanych_ogolnych": int((~out["kand_przedmiotowy"]).sum()),
        "n_rozstrzyganych": int(len(jd)),
        "n_do_przegladu": int(out["do_przegladu"].sum()),
        "rozklad_final": out["kategoria_final"].value_counts().to_dict(),
        "rozklad_final_przedmiotowe": out.loc[out["kand_przedmiotowy"], "kategoria_final"].value_counts().to_dict(),
        "rozklad_final_tylko_ogolne": out.loc[~out["kand_przedmiotowy"], "kategoria_final"].value_counts().to_dict(),
        "typy_szumu": out.loc[out["kategoria_final"] == "SZUM", "typ_szumu"].value_counts().to_dict(),
        "n_form_poprawionych": int((out["forma_poprawna"] != out["forma_wejsciowa"]).sum()),
        "zgodnosc_miedzy_modelami": {"para": f"{sa} vs {sb}", "prosta": agree["wszystkie"]["prosta"],
                                     "kappa": agree["wszystkie"]["kappa"], "wg_segmentu": agree},
        "macierz_pomylek": {"wiersze": sb, "kolumny": sa, "dane": confusion},
        "zgodnosc_z_etykieta_koncowa": vs_final,
        "rozstrzygniecia": judge_stats,
        "regula_wzgledem_llm": rule,
        "metody_wzgledem_etykiet_llm": methods_vs_llm,
        "ekstrakcja_llm": ext_metrics,
        "pojecia": concept_metrics,
        "koszty_usd_wg_zadania": {k: round(v, 4) for k, v in sorted(costs.items())},
        "koszt_usd_przebieg": round(sum(costs.values()), 4),
        "koszt_usd_dotychczas": round(llm.spent(ctx), 4),
        "uwaga": "Zgodność między modelami NIE jest miarą trafności – brak etykiet ludzkich ze złotego zbioru.",
        "czas_s": round(t.s, 1),
    }
    ctx.save_metrics("llm_5", metrics)
    (ctx.data / "llm.done").write_text("ok\n", encoding="utf-8")
    log(f"s05: gotowe; zgodność={agree['wszystkie']['prosta']} κ={agree['wszystkie']['kappa']}, "
        f"koszt łączny=${metrics['koszt_usd_dotychczas']}")
