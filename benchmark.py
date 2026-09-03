"""
Load-spike benchmark: compares the plain round-robin baseline against
the adaptive load balancer (EWMA routing + circuit breaker + Rajomon-
inspired admission control) under a burst of concurrent traffic.

Usage:
    # start backends first (each in its own terminal or &):
    uvicorn backends.server_a:app --port 9001
    uvicorn backends.server_b:app --port 9002
    uvicorn backends.server_c:app --port 9003

    # then, to benchmark the baseline:
    uvicorn load_balancer.round_robin_lb:app --port 8000
    python benchmark.py --port 8000 --requests 200 --concurrency 40

    # and the adaptive LB:
    uvicorn load_balancer.main:app --port 8000
    python benchmark.py --port 8000 --requests 200 --concurrency 40
"""

import argparse
import asyncio
import time

import httpx


async def worker(client, url, results):
    start = time.perf_counter()

    try:
        response = await client.get(url)
        latency = time.perf_counter() - start
        results.append((response.status_code, latency))
    except (httpx.TimeoutException, httpx.RequestError):
        latency = time.perf_counter() - start
        results.append((None, latency))


async def run(url, total_requests, concurrency):
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=5.0) as client:

        async def bound_worker():
            async with semaphore:
                await worker(client, url, results)

        await asyncio.gather(
            *(bound_worker() for _ in range(total_requests))
        )

    return results


def percentile(sorted_values, p):
    if not sorted_values:
        return None

    index = min(
        len(sorted_values) - 1,
        int(len(sorted_values) * p),
    )

    return sorted_values[index]


def summarize(results):
    latencies = sorted(latency for _, latency in results)

    ok = sum(1 for status, _ in results if status == 200)
    shed = sum(1 for status, _ in results if status in (429, 503))
    errored = sum(1 for status, _ in results if status is None)

    print(f"total requests : {len(results)}")
    print(f"  200 OK       : {ok}")
    print(f"  429/503 shed : {shed}")
    print(f"  errored      : {errored}")
    print(f"p50 latency    : {percentile(latencies, 0.50) * 1000:.1f} ms")
    print(f"p95 latency    : {percentile(latencies, 0.95) * 1000:.1f} ms")
    print(f"p99 latency    : {percentile(latencies, 0.99) * 1000:.1f} ms")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=40)
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}/"

    print(
        f"hitting {url} with {args.requests} requests "
        f"at concurrency {args.concurrency}..."
    )

    results = asyncio.run(run(url, args.requests, args.concurrency))
    summarize(results)


if __name__ == "__main__":
    main()