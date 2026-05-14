"""Adaptive concurrency limiter for GLM Coding Plan calls.

Handles three realities that a naive semaphore misses:

1. **Sub-agent fan-out** — a Claude Code headless session may spawn 1-2 sub-agents
   internally (Task tool). Each sub-agent is another LLM call against the same quota.
   Solution: per-call `weight` (1 for direct API, 3 for Claude Code harness).

2. **External contention** — the user is running their own Claude Code session in
   parallel and also hits the same Coding Plan quota. We can't see those calls
   directly, but we can leave headroom via ZAI_RESERVE_SLOTS and we can detect
   contention via 429 frequency.

3. **Transient 429 / 1302** — z.ai's risk-control rate-limit. Best response is
   immediate back-off, not retry-fast. We use an exponential cooldown that
   shrinks available slot count when 429s come fast, and slowly recovers when
   they don't.

Environment variables:
  ZAI_MAX_CONCURRENT       hard ceiling, default 10 (z.ai documented limit)
  ZAI_RESERVE_SLOTS        slots reserved for user, default 2
  ZAI_INITIAL_CONCURRENCY  starting effective slot count, default = max - reserve
  ZAI_HARNESS_WEIGHT       cost of a Claude Code harness call, default 3
                           (1 main + estimated 0-2 sub-agents internally)
  ZAI_RECOVERY_INTERVAL_S  seconds between slot-recovery attempts, default 60

Usage:

    budget = ConcurrencyBudget()
    with budget.acquire(weight=3, label="Notch:pass2"):
        resp = call_glm(...)
        if resp_was_429(resp):
            budget.report_429()
        else:
            budget.report_success()

The `with` releases the slot on exit. Outer code never needs to manually release.
"""
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


def _intenv(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


@dataclass
class ConcurrencyBudget:
    max_concurrent: int = field(default_factory=lambda: _intenv("ZAI_MAX_CONCURRENT", 10))
    reserve: int = field(default_factory=lambda: _intenv("ZAI_RESERVE_SLOTS", 2))
    harness_weight: int = field(default_factory=lambda: _intenv("ZAI_HARNESS_WEIGHT", 3))
    recovery_interval_s: int = field(default_factory=lambda: _intenv("ZAI_RECOVERY_INTERVAL_S", 60))
    # Quota-exhaustion (5h window full): pause all workers for this long before checking again.
    quota_wait_s: int = field(default_factory=lambda: _intenv("ZAI_QUOTA_WAIT_S", 300))   # 5 min poll
    # Trip into quota-exhausted mode if >= this many 429s within window
    quota_exhausted_threshold: int = field(default_factory=lambda: _intenv("ZAI_QUOTA_EXHAUSTED_THRESHOLD", 15))
    quota_exhausted_window_s: int = field(default_factory=lambda: _intenv("ZAI_QUOTA_EXHAUSTED_WINDOW_S", 300))

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _slots_available: int = 0
    _slots_in_use: int = 0
    _effective_cap: int = 0      # current ceiling, may shrink on 429s
    _initial_cap: int = 0

    # 429 tracking
    _recent_429s: list = field(default_factory=list)   # timestamps
    _last_recovery_attempt: float = 0.0

    # quota-exhaustion state
    _quota_exhausted_until: float = 0.0
    _quota_pause_count: int = 0

    # counter for unique slot waiters (for fair queueing)
    _waiter_cond: threading.Condition = None

    def __post_init__(self):
        self._waiter_cond = threading.Condition(self._lock)
        initial = _intenv("ZAI_INITIAL_CONCURRENCY", self.max_concurrent - self.reserve)
        initial = max(1, min(self.max_concurrent - self.reserve, initial))
        self._effective_cap = initial
        self._initial_cap = initial
        self._slots_available = initial

    @property
    def state(self) -> dict:
        with self._lock:
            now = time.time()
            return {
                "max": self.max_concurrent,
                "reserve": self.reserve,
                "effective_cap": self._effective_cap,
                "in_use": self._slots_in_use,
                "available": self._slots_available,
                "recent_429s_60s": len([t for t in self._recent_429s if t > now - 60]),
                "quota_exhausted_until_s": max(0, self._quota_exhausted_until - now),
                "quota_pause_count": self._quota_pause_count,
            }

    @contextmanager
    def acquire(self, weight: int = 1, label: str = ""):
        """Block until `weight` slots are free, then take them.

        Three blocking conditions:
          1. quota-exhausted mode: all workers paused until _quota_exhausted_until expires
          2. effective_cap throttled below requested weight: wait for recovery
          3. all slots currently in use: wait for a release
        """
        weight = max(1, weight)
        with self._waiter_cond:
            while True:
                now = time.time()
                # Condition 1: quota exhaustion suspends EVERYBODY
                if self._quota_exhausted_until > now:
                    remaining = self._quota_exhausted_until - now
                    self._waiter_cond.wait(timeout=min(30, remaining))
                    continue
                # Conditions 2 + 3: slots available
                self._try_recover_locked()
                if self._slots_available >= weight:
                    self._slots_available -= weight
                    self._slots_in_use += weight
                    break
                self._waiter_cond.wait(timeout=2)
        try:
            yield
        finally:
            with self._waiter_cond:
                self._slots_available += weight
                self._slots_in_use -= weight
                self._waiter_cond.notify_all()

    def report_429(self):
        """Pull effective_cap down by 1 (down to 1 minimum). If 429 rate within window
        crosses the quota_exhausted threshold, trip into quota-exhausted mode that
        suspends ALL workers for quota_wait_s before next attempt."""
        with self._waiter_cond:
            now = time.time()
            self._recent_429s.append(now)
            self._recent_429s = [t for t in self._recent_429s if t > now - self.quota_exhausted_window_s]

            # mild backoff
            old_cap = self._effective_cap
            self._effective_cap = max(1, self._effective_cap - 1)
            delta = old_cap - self._effective_cap
            self._slots_available = max(0, self._slots_available - delta)
            self._last_recovery_attempt = now

            # severe: if too many 429s in window, treat as quota exhaustion
            if len(self._recent_429s) >= self.quota_exhausted_threshold:
                self._quota_exhausted_until = now + self.quota_wait_s
                self._quota_pause_count += 1
                # also collapse cap to 1 — we'll have to feel our way back up
                self._effective_cap = 1
                self._slots_available = min(self._slots_available, 1)
            self._waiter_cond.notify_all()

    def report_quota_exhausted(self, cooldown_s: int = None):
        """Explicitly trip into quota-pause mode (e.g. when error body says
        'insufficient balance' or 'quota'). Suspends acquirers until cooldown elapses."""
        with self._waiter_cond:
            now = time.time()
            cooldown = cooldown_s if cooldown_s is not None else self.quota_wait_s
            self._quota_exhausted_until = max(self._quota_exhausted_until, now + cooldown)
            self._quota_pause_count += 1
            self._waiter_cond.notify_all()

    def report_success(self):
        """Recorded for adaptive recovery. Doesn't grow cap by itself — that's done
        on a timer to avoid oscillation."""
        # no-op for now; recovery is timer-driven, not success-driven
        pass

    def _try_recover_locked(self):
        """If we've been throttled below initial cap AND no 429s in last recovery_interval,
        bump effective_cap by 1. Called under lock."""
        now = time.time()
        if self._effective_cap >= self._initial_cap:
            return
        if now - self._last_recovery_attempt < self.recovery_interval_s:
            return
        recent = [t for t in self._recent_429s if t > now - self.recovery_interval_s]
        if recent:
            return
        # safe to expand
        self._effective_cap += 1
        self._slots_available += 1
        self._last_recovery_attempt = now


# ---------- helpers --------------------------------------------------------

def is_rate_limit_response(http_code: str, body_text: str = "") -> bool:
    """z.ai signals risk-control via HTTP 429 + error code '1302' (or '1303')."""
    if str(http_code) in ("429", "503"):
        return True
    if "\"code\":\"1302\"" in body_text or "\"code\":\"1303\"" in body_text:
        return True
    return False


def is_quota_exhausted_response(http_code: str, body_text: str = "") -> bool:
    """Hard quota exhaustion (vs transient rate-limit): error code 1113 'Insufficient balance',
    or message text containing quota / subscription / balance keywords."""
    low = (body_text or "").lower()
    if "\"code\":\"1113\"" in body_text:
        return True
    for kw in ("insufficient balance", "quota exhausted", "subscription benefits may be restricted",
               "recharge", "exceeded daily", "exceeded 5-hour"):
        if kw in low:
            return True
    return False


# ---------- module-level singleton ---------------------------------------

_BUDGET = None


def budget() -> ConcurrencyBudget:
    global _BUDGET
    if _BUDGET is None:
        _BUDGET = ConcurrencyBudget()
    return _BUDGET
