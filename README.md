# talus

An HTTP load balancer written in Python (FastAPI), built to explore
adaptive routing and overload control for microservices — going beyond
static round-robin toward decisions driven by live backend congestion.

## What it does

- **Adaptive routing**: routes each request to the backend with the best
  live performance score, computed from an exponentially-weighted moving
  average (EWMA) of latency and current in-flight request count — not a
  fixed round-robin order.
- **Circuit breaker**: backends that fail repeatedly are marked `OPEN`
  and skipped for a cooldown period, then probed via `HALF_OPEN` before
  being trusted again.
- **Congestion-priced admission control**: inspired by
  [Rajomon](https://github.com/pennsail/rajomon) (NSDI '25), a
  decentralized overload-control system for microservices. Each client
  gets a token bucket; the *cost* of a request scales with how congested
  the backends currently are (their price), so clients are throttled
  harder as the system gets busier — and requests are shed outright
  ("fail fast") if every backend is overloaded, instead of queuing
  behind a system that's already struggling.

This is a simplified, single-node analogue of Rajomon's core idea
(dynamic, congestion-based pricing driving admission decisions) — not
its full decentralized, multi-service token/price propagation protocol.

## Project Layout

### `backends/`
Contains three simulated backend services with different response latencies:
- `server_a.py` — ~10 ms latency
- `server_b.py` — ~50 ms latency
- `server_c.py` — ~200 ms latency

### `load_balancer/`
Contains the core load-balancing components:
- `backend.py` — Tracks backend state using EWMA latency, performance score, and price.
- `admission_control.py` — Implements token-bucket and congestion-based admission control.
- `main.py` — Implements the adaptive load balancer, including backend routing, circuit breakers, and admission control.
- `round_robin_lb.py` — Implements a round-robin load balancer as a baseline for comparison.

### `benchmark.py`
Runs load-spike experiments and measures latency percentiles and request shed rate.


## How to run

Start the three backends:

```bash
uvicorn backends.server_a:app --port 9001
uvicorn backends.server_b:app --port 9002
uvicorn backends.server_c:app --port 9003
```

Start the load balancer:

```bash
uvicorn load_balancer.main:app --port 8000
```

Send a request:

```bash
curl localhost:8000/
```

Inspect live backend state (latency, score, price, circuit state):

```bash
curl localhost:8000/stats
```

Check your remaining token budget:

```bash
curl localhost:8000/tokens
```

## Benchmarking

Compare the round-robin baseline against the adaptive load balancer
under a concurrent traffic spike:

```bash
# baseline
uvicorn load_balancer.round_robin_lb:app --port 8000
python benchmark.py --port 8000 --requests 150 --concurrency 40

# adaptive
uvicorn load_balancer.main:app --port 8000
python benchmark.py --port 8000 --requests 150 --concurrency 40
```

### Results (150 requests, concurrency 40)

Isolating routing quality (EWMA-weighted routing vs. round-robin):

| Metric | Round robin | Adaptive routing |
|---|---|---|
| p50 latency | 190.3 ms | 129.3 ms |
| p95 latency | 327.0 ms | 304.7 ms |
| p99 latency | 404.4 ms | 312.5 ms |

Routing purely by live congestion cuts p50 latency by ~32% compared to
round-robin.

Under a single-client flood, the admission controller sheds excess load
early — tokens visibly drain from 20 to near-zero, and later requests get
`429 rate_limited` instead of queuing behind already-saturated backends.
This is expected: a per-client token bucket protects the system from any
one noisy source, at the cost of not being able to distinguish multiple
real users sharing one IP — a known limitation of IP-based rate limiting.

## Notes / limitations

- Admission control keys clients by source IP, so multiple real users
  behind the same IP/NAT share one budget.
- Pricing and token-bucket constants (`BASE_PRICE`, `MAX_PRICE`,
  `BUCKET_CAPACITY`, `REFILL_RATE`) are tuned for this local demo and
  would need retuning for real traffic patterns.
- This does not implement Rajomon's cross-service price propagation —
  pricing here is local to this one load balancer, not passed along a
  multi-hop service graph.