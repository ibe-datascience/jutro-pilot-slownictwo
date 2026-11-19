"""Wywołania API Claude: Batch API, buforowanie promptu, wymuszona struktura wyjścia, księgowanie kosztów.

Parametry sprawdzone w dokumentacji platform.claude.com w dniu 2026-11-13:
  * Message Batches: `client.messages.batches.create(requests=[{custom_id, params}])`, 50% zniżki,
    limit 100 000 żądań / 256 MB, `custom_id` zgodne z ^[a-zA-Z0-9_-]{1,64}$, wyniki strumieniowane (JSONL).
  * Struktura wyjścia: `output_config={"format": {"type": "json_schema", "schema": ...}}`
    (obiekty z `additionalProperties: false`, `enum` dozwolone, bez ograniczeń długości/zakresów).
  * Buforowanie promptu: `cache_control={"type": "ephemeral", "ttl": "1h"}` na bloku systemowym;
    minimum 512 tokenów dla modeli 5.5; w batchach trafienia w bufor „best effort”.
  * Ceny (USD/MTok; wejście / zapis bufora 1 h / odczyt bufora / wyjście) – tabela PRICES poniżej.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .common import Ctx, expand, log, now_iso, read_jsonl

# USD za milion tokenów, cennik z platform.claude.com/docs/en/about-claude/pricing (odczyt 2026-11-13)
PRICES = {
    "claude-haiku-5-5": {"in": 0.10, "cache_write_1h": 0.20, "cache_write_5m": 0.125, "cache_read": 0.01, "out": 0.50},
    "claude-sonnet-5-5": {"in": 2.00, "cache_write_1h": 4.00, "cache_write_5m": 2.50, "cache_read": 0.10, "out": 10.00},
    "claude-opus-5-5": {"in": 4.00, "cache_write_1h": 8.00, "cache_write_5m": 5.00, "cache_read": 0.20, "out": 20.00},
    # odczyt 2026-11-19; trafienia w bufor dla Fable 5.2 kosztują 0,025x ceny wejścia
    "claude-fable-5-2": {"in": 8.00, "cache_write_1h": 16.00, "cache_write_5m": 10.00, "cache_read": 0.20, "out": 40.00},
}
BATCH_DISCOUNT = 0.5


class BudgetExceeded(RuntimeError):
    pass


def _client(ctx: Ctx):
    import anthropic
    from dotenv import dotenv_values

    vals = dotenv_values(expand(ctx.cfg["zrodlo"]["env_file"]))
    key = vals.get("ANTHROPIC_API_KEY") or vals.get("anthropic_api_key")
    if not key:
        import os

        key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Brak klucza API (ANTHROPIC_API_KEY / anthropic_api_key)")
    return anthropic.Anthropic(api_key=key, max_retries=4)


def llm_dir(ctx: Ctx) -> Path:
    d = ctx.data / "llm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cost_of(model: str, usage: dict[str, int], batch: bool) -> float:
    p = PRICES[model]
    c = (
        usage.get("input_tokens", 0) * p["in"]
        + usage.get("cache_creation_input_tokens", 0) * p["cache_write_1h"]
        + usage.get("cache_read_input_tokens", 0) * p["cache_read"]
        + usage.get("output_tokens", 0) * p["out"]
    ) / 1e6
    return c * (BATCH_DISCOUNT if batch else 1.0)


def spent(ctx: Ctx) -> float:
    """Łączny koszt zaksięgowany we wszystkich przebiegach tej konfiguracji (próbka + pełny)."""
    total = 0.0
    base = ctx.data.parent
    for p in base.glob("*/llm/koszty.jsonl"):
        for r in read_jsonl(p):
            total += r.get("koszt_usd", 0.0)
    return total


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def _usage_dict(u: Any) -> dict[str, int]:
    out = {}
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        v = getattr(u, k, None) if not isinstance(u, dict) else u.get(k)
        out[k] = int(v or 0)
    return out


def _parse_message(msg: Any) -> tuple[Any, str]:
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(text), text
    except Exception:
        return None, text


def run_requests(
    ctx: Ctx,
    task: str,
    model: str,
    system: str,
    items: list[tuple[str, str]],
    schema: dict[str, Any],
    max_tokens: int = 400,
    batch: bool | None = None,
    prompt_version: str | None = None,
    est_out_tokens: int = 150,
    min_batch: int = 2,
) -> dict[str, Any]:
    """Wykonuje żądania (klucz, treść użytkownika) i zwraca {klucz: sparsowany JSON}.

    Odpowiedzi są zapisywane w data/.../llm/<task>__<model>.jsonl; ponowne uruchomienie nie powtarza
    żądań o tym samym modelu, prompcie i treści. `min_batch` – od ilu żądań używać Batch API
    (1 = zawsze; przydatne dla pojedynczych żądań z bardzo długą odpowiedzią).
    """
    prompt_version = prompt_version or ctx.cfg["llm"]["wersja_promptu"]
    batch = ctx.cfg["llm"].get("batch", True) if batch is None else batch
    store = llm_dir(ctx) / f"{task}__{model}.jsonl"
    sys_hash = _hash(system, json.dumps(schema, sort_keys=True))
    cached: dict[str, dict[str, Any]] = {}
    if store.exists():
        for r in read_jsonl(store):
            cached[r["hash"]] = r
    results: dict[str, Any] = {}
    todo: list[tuple[str, str, str]] = []
    for key, user in items:
        h = _hash(model, sys_hash, user)
        if h in cached and cached[h].get("output") is not None:
            results[key] = cached[h]["output"]
        else:
            todo.append((key, user, h))
    if not todo:
        return results
    if getattr(ctx, "bez_llm", False):
        log(f"  llm[{task}/{model}]: {len(todo)} żądań pominiętych (--bez-llm)")
        return results

    # --- kontrola budżetu (szacunek z góry: ~3 znaki na token dla polskiego tekstu)
    p = PRICES[model]
    disc = BATCH_DISCOUNT if batch else 1.0
    est_in = sum(len(u) for _, u, _ in todo) / 3 + len(todo) * len(system) / 3
    est = (est_in * p["in"] + len(todo) * est_out_tokens * p["out"]) / 1e6 * disc
    limit = float(ctx.cfg["llm"]["limit_kosztu_usd"])
    already = spent(ctx)
    log(f"  llm[{task}/{model}]: {len(todo)} żądań, szacunek ≤ {est:.2f} USD (bez bufora), wydano dotąd {already:.2f} USD")
    if already + est > limit:
        raise BudgetExceeded(
            f"Prognozowany koszt {already + est:.2f} USD przekracza limit {limit:.2f} USD (zadanie {task}, model {model})")

    use_batch = bool(batch) and len(todo) >= min_batch
    client = _client(ctx)
    sys_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": ctx.cfg["llm"].get("cache_ttl", "1h")}}]
    out_cfg = {"format": {"type": "json_schema", "schema": schema}}

    # Ustawienia myślenia zależne od modelu (dokumentacja „Effort”, odczyt 2026-11-13):
    #   Haiku 5.5  – myślenie domyślnie włączone, można wyłączyć: thinking={"type": "disabled"};
    #   Sonnet 5.5 – odpowiedź bez myślenia wstępnego: thinking={"type": "between_tools"};
    #   Opus 5.5 / Fable 5.2 – myślenie adaptacyjne zawsze włączone; sterowanie przez output_config.effort
    #   (sprawdzone wywołaniem 2026-11-19: `effort` przyjmują Sonnet 5.5, Opus 5.5 i Fable 5.2).
    # Tokeny myślenia liczą się do max_tokens i są rozliczane jak wyjście.
    extra = dict((ctx.cfg["llm"].get("parametry") or {}).get(model) or {})
    effort = extra.pop("effort", None)
    if effort:
        out_cfg["effort"] = effort
    mt = max(max_tokens, int(extra.pop("min_max_tokens", 0)))

    def params(user: str) -> dict[str, Any]:
        return {"model": model, "max_tokens": mt, "system": sys_block,
                "messages": [{"role": "user", "content": user}], "output_config": out_cfg, **extra}

    usage_total = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    n_ok = n_err = 0
    batch_ids: list[str] = []
    t0 = time.time()
    with open(store, "a", encoding="utf-8") as fh:
        def record(key: str, user: str, h: str, msg: Any, err: str | None = None) -> None:
            nonlocal n_ok, n_err
            if msg is None:
                n_err += 1
                fh.write(json.dumps({"hash": h, "key": key, "output": None, "error": err, "data": now_iso()}, ensure_ascii=False) + "\n")
                return
            out, raw = _parse_message(msg)
            u = _usage_dict(msg.usage)
            for k in usage_total:
                usage_total[k] += u[k]
            rec = {"hash": h, "key": key, "output": out, "usage": u, "stop": msg.stop_reason, "model": msg.model, "data": now_iso()}
            if out is None:
                rec["raw"] = raw[:2000]
                n_err += 1
            else:
                n_ok += 1
                results[key] = out
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if use_batch:
            # Identyfikatory wysłanych batchy są zapisywane na dysk; jeśli proces zostanie przerwany przed
            # odebraniem wyników, kolejne uruchomienie odbiera je zamiast wysyłać (i opłacać) żądania ponownie.
            pending_path = llm_dir(ctx) / f"{task}__{model}.oczekujace.json"
            pending: list[str] = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else []

            def save_pending() -> None:
                if pending:
                    pending_path.write_text(json.dumps(pending), encoding="utf-8")
                elif pending_path.exists():
                    pending_path.unlink()

            def collect(bid: str, by_hash: dict[str, tuple[str, str, str]]) -> None:
                while True:
                    b = client.messages.batches.retrieve(bid)
                    if b.processing_status == "ended":
                        break
                    time.sleep(20)
                rc = b.request_counts
                log(f"  batch {bid}: zakończony po {time.time() - t0:.0f}s (ok={rc.succeeded}, błędy={rc.errored}, wygasłe={rc.expired})")
                n_other = 0
                for res in client.messages.batches.results(bid):
                    item = by_hash.pop(res.custom_id.split("-", 1)[-1], None)
                    if item is None:  # żądanie spoza bieżącej listy (zmieniony prompt lub dane): opłacone, więc księgowane
                        n_other += 1
                        if res.result.type == "succeeded":
                            u = _usage_dict(res.result.message.usage)
                            for k in usage_total:
                                usage_total[k] += u[k]
                        continue
                    key, user, h = item
                    if res.result.type == "succeeded":
                        record(key, user, h, res.result.message)
                    else:
                        record(key, user, h, None, err=res.result.type)
                fh.flush()
                if n_other:
                    log(f"  batch {bid}: {n_other} wyników nie pasuje do bieżących żądań – pominięte")
                batch_ids.append(bid)
                pending.remove(bid)
                save_pending()

            by_hash = {h: (key, user, h) for key, user, h in todo}
            for bid in list(pending):
                log(f"  batch {bid}: wznawiam odbiór wyników przerwanego przebiegu")
                collect(bid, by_hash)
            rest = list(by_hash.values())
            for start in range(0, len(rest), 20000):
                chunk = rest[start:start + 20000]
                reqs = [{"custom_id": f"r{start + n}-{h}", "params": params(user)} for n, (_, user, h) in enumerate(chunk)]
                b = client.messages.batches.create(requests=reqs)
                pending.append(b.id)
                save_pending()
                log(f"  batch {b.id}: {len(chunk)} żądań wysłanych")
                collect(b.id, by_hash)
        else:
            from concurrent.futures import ThreadPoolExecutor

            def one(item: tuple[str, str, str]):
                key, user, h = item
                try:
                    return item, client.messages.create(**params(user)), None
                except Exception as exc:  # noqa: BLE001
                    return item, None, f"{type(exc).__name__}: {exc}"[:300]

            with ThreadPoolExecutor(max_workers=int(ctx.cfg["llm"].get("watki_sync", 8))) as pool:
                for (key, user, h), msg, err in pool.map(one, todo):
                    record(key, user, h, msg, err)
                    fh.flush()

    cost = cost_of(model, usage_total, use_batch)
    entry = {
        "data": now_iso(), "zadanie": task, "model": model, "wersja_promptu": prompt_version, "prompt_hash": sys_hash,
        "tryb": "batch" if use_batch else "sync", "batch_ids": batch_ids, "zadan": len(todo),
        "ok": n_ok, "bledy": n_err, "uzycie": usage_total, "koszt_usd": round(cost, 5), "czas_s": round(time.time() - t0, 1),
    }
    with open(llm_dir(ctx) / "koszty.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log(f"  llm[{task}/{model}]: ok={n_ok} błędy={n_err} koszt={cost:.3f} USD "
        f"(in={usage_total['input_tokens']}, cache_r={usage_total['cache_read_input_tokens']}, "
        f"cache_w={usage_total['cache_creation_input_tokens']}, out={usage_total['output_tokens']})")
    return results


def cost_summary(ctx: Ctx) -> list[dict[str, Any]]:
    p = llm_dir(ctx) / "koszty.jsonl"
    return list(read_jsonl(p)) if p.exists() else []
