"""Backpressure & concurrency primitives for LLM-heavy endpoints.

- LLM_SEMAPHORE / ACTIONS_SEMAPHORE: bound parallel LLM calls per process to
  protect Qwen / DB connection pool from request bursts.
- per-scenario reentrant lock: prevent the same scenario from launching
  duplicate heavy pipelines (idempotent + back-pressure).
- request_id helpers: stamp each request with an ID for log correlation.
- in-flight metrics: simple counters per route used by /metrics.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from typing import AsyncIterator


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return max(1, int(str(raw).strip()))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        v = float(str(raw).strip())
        return v if v > 0 else default
    except ValueError:
        return default


# Hard caps for in-flight LLM operations per worker.
LLM_PLAN_DETAIL_MAX_CONCURRENCY = _int_env("APS_LLM_PLAN_DETAIL_MAX", 4)
LLM_ACTIONS_GENERATE_MAX_CONCURRENCY = _int_env("APS_LLM_ACTIONS_GEN_MAX", 4)

# Default per-task LLM timeouts (seconds). Fail-fast to avoid worker starvation.
LLM_PLAN_DETAIL_TIMEOUT_S = _float_env("APS_LLM_PLAN_DETAIL_TIMEOUT", 60.0)
LLM_ACTIONS_GENERATE_TIMEOUT_S = _float_env("APS_LLM_ACTIONS_GEN_TIMEOUT", 60.0)

# Lazy singletons so unit tests can monkey-patch.
_llm_plan_sem: asyncio.Semaphore | None = None
_llm_actions_sem: asyncio.Semaphore | None = None


def llm_plan_detail_semaphore() -> asyncio.Semaphore:
    global _llm_plan_sem
    if _llm_plan_sem is None:
        _llm_plan_sem = asyncio.Semaphore(LLM_PLAN_DETAIL_MAX_CONCURRENCY)
    return _llm_plan_sem


def llm_actions_generate_semaphore() -> asyncio.Semaphore:
    global _llm_actions_sem
    if _llm_actions_sem is None:
        _llm_actions_sem = asyncio.Semaphore(LLM_ACTIONS_GENERATE_MAX_CONCURRENCY)
    return _llm_actions_sem


# ── Per-scenario non-blocking guard (try-acquire only — never blocks request).
_scenario_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _scenario_lock(scope: str, scenario_id: str) -> asyncio.Lock:
    key = (scope, scenario_id)
    lock = _scenario_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _scenario_locks[key] = lock
    return lock


@contextlib.asynccontextmanager
async def scenario_busy_guard(scope: str, scenario_id: str | None) -> AsyncIterator[bool]:
    """Acquire a per-scenario lock; queue (don't 429) when busy.

    Always yields True. Callers should re-check the LLM cache *after* acquiring
    so that piled-up duplicate requests benefit from the first run's result
    instead of all hitting the LLM (thundering-herd protection).
    """
    if not scenario_id:
        yield True
        return
    lock = _scenario_lock(scope, scenario_id)
    async with lock:
        yield True


# ── Single-flight per key ────────────────────────────────────────────────────
# Multiple requests asking for the same (scope, key) share one in-flight Future
# instead of doing duplicate LLM work. Critical for snappy UX when the user
# refreshes the page mid-batch.

_inflight_futures: dict[tuple[str, str], asyncio.Future] = {}
_inflight_lock = asyncio.Lock()


async def single_flight(scope: str, key: str, factory):
    """Run `factory()` only once per `(scope, key)`; concurrent callers await the same result.

    Args:
        scope: namespace for the key (e.g. "plan_detail").
        key: stable identity (e.g. f"{scenario_id}:{plan_id}").
        factory: zero-arg async callable producing the value.
    """
    full_key = (scope, key)
    async with _inflight_lock:
        existing = _inflight_futures.get(full_key)
        if existing is not None:
            fut = existing
            owner = False
        else:
            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            _inflight_futures[full_key] = fut
            owner = True

    if owner:
        try:
            result = await factory()
            if not fut.done():
                fut.set_result(result)
        except BaseException as exc:  # noqa: BLE001 — propagate to all waiters
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            async with _inflight_lock:
                _inflight_futures.pop(full_key, None)
        return fut.result()

    return await fut


# ── Request id (set by middleware, read by logs).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Lightweight in-process metrics for /metrics endpoint.
class _RouteMetrics:
    __slots__ = ("count", "errors", "in_flight", "p50_ms", "p95_ms", "_samples")

    def __init__(self) -> None:
        self.count = 0
        self.errors = 0
        self.in_flight = 0
        self.p50_ms = 0.0
        self.p95_ms = 0.0
        self._samples: list[float] = []

    def observe(self, elapsed_ms: float, error: bool) -> None:
        self.count += 1
        if error:
            self.errors += 1
        # Bounded reservoir; recompute summary every 32 samples.
        self._samples.append(elapsed_ms)
        if len(self._samples) > 256:
            self._samples = self._samples[-256:]
        if self.count % 32 == 0 or self.count < 32:
            ordered = sorted(self._samples)
            n = len(ordered)
            if n:
                self.p50_ms = ordered[max(0, int(n * 0.5) - 1)]
                self.p95_ms = ordered[max(0, int(n * 0.95) - 1)]


_route_metrics: dict[str, _RouteMetrics] = defaultdict(_RouteMetrics)


@contextlib.asynccontextmanager
async def measure_route(name: str) -> AsyncIterator[None]:
    m = _route_metrics[name]
    m.in_flight += 1
    start = time.perf_counter()
    err = False
    try:
        yield
    except Exception:
        err = True
        raise
    finally:
        m.in_flight = max(0, m.in_flight - 1)
        m.observe((time.perf_counter() - start) * 1000.0, err)


def metrics_snapshot() -> dict:
    return {
        name: {
            "count": m.count,
            "errors": m.errors,
            "in_flight": m.in_flight,
            "p50_ms": round(m.p50_ms, 1),
            "p95_ms": round(m.p95_ms, 1),
        }
        for name, m in _route_metrics.items()
    }


def configured_limits() -> dict:
    return {
        "llm_plan_detail_max": LLM_PLAN_DETAIL_MAX_CONCURRENCY,
        "llm_actions_generate_max": LLM_ACTIONS_GENERATE_MAX_CONCURRENCY,
        "llm_plan_detail_timeout_s": LLM_PLAN_DETAIL_TIMEOUT_S,
        "llm_actions_generate_timeout_s": LLM_ACTIONS_GENERATE_TIMEOUT_S,
    }
