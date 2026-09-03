"""
Admission control inspired by Rajomon (NSDI'25).

Rajomon attaches a *token* budget to each client and a *price* to each
API, derived from congestion, then drops/delays requests whose tokens
can't cover the price. This module implements a small, single-node
version of that idea:

  - Each client (by IP) gets a token bucket that refills at a fixed
    rate. This is the "budget" a client is allowed to spend.
  - The *price* of a request is derived from live backend congestion
    (EWMA latency x in-flight requests, see Backend.price()) instead
    of being fixed. The busier the backends are, the more tokens a
    request costs.
  - If a client doesn't have enough tokens, or if every backend is so
    congested that the system-wide price exceeds a hard ceiling, the
    request is shed immediately (fail fast) instead of being queued
    behind an already-overloaded backend.
"""

import time


# Below this price, a request costs the minimum (1 token). Roughly
# the latency (ms) of a healthy, idle backend in this setup.
BASE_PRICE = 15.0

# If the cheapest available backend's price is above this, the whole
# system is considered overloaded and we shed load outright rather
# than spending client tokens on a request likely to be slow anyway.
MAX_PRICE = 500.0

# Token bucket parameters.
BUCKET_CAPACITY = 20
REFILL_RATE = 10  # tokens per second


class TokenBucket:
    def __init__(self, capacity=BUCKET_CAPACITY, refill_rate=REFILL_RATE):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate,
        )
        self.last_refill = now

    def try_spend(self, cost):
        self._refill()

        if self.tokens < cost:
            return False

        self.tokens -= cost
        return True


class AdmissionController:
    def __init__(self):
        self._buckets = {}

    def _bucket_for(self, client_id):
        if client_id not in self._buckets:
            self._buckets[client_id] = TokenBucket()

        return self._buckets[client_id]

    @staticmethod
    def request_cost(price):
        """Translate a congestion price into a token cost. Cost grows
        with price so clients naturally get throttled harder as the
        system gets busier."""
        return max(1, round(price / BASE_PRICE))

    def admit(self, client_id, price):
        """
        Returns (allowed: bool, reason: str | None).
        """
        if price > MAX_PRICE:
            return False, "system_overloaded"

        bucket = self._bucket_for(client_id)
        cost = self.request_cost(price)

        if not bucket.try_spend(cost):
            return False, "rate_limited"

        return True, None

    def snapshot(self, client_id):
        bucket = self._buckets.get(client_id)

        if bucket is None:
            return {"tokens": BUCKET_CAPACITY, "capacity": BUCKET_CAPACITY}

        bucket._refill()

        return {
            "tokens": round(bucket.tokens, 2),
            "capacity": bucket.capacity,
        }