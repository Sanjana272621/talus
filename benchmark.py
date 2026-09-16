import argparse
import asyncio
import statistics
import time

import httpx


async def worker(client, url, semaphore, results):
    async with semaphore:
        start = time.perf_counter()

        try:
            response = await client.get(url)
            status = response.status_code
        except httpx.TimeoutException:
            status = None
        except httpx.RequestError:
            status = None

        latency = time.perf_counter() - start
        results.append((status, latency))


async def run(url, total_requests, concurrency):
    results = []

    # At most `concurrency` requests can be in flight at once.
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=5.0) as client:

        tasks = [
            asyncio.create_task(
                worker(client, url, semaphore, results)
            )
            for _ in range(total_requests)
        ]

        await asyncio.gather(*tasks)

    return results


def percentile(values, p):
    """
    Calculate percentile using linear interpolation.

    p should be between 0 and 1.
    Example:
        percentile(values, 0.50) -> p50
        percentile(values, 0.95) -> p95
        percentile(values, 0.99) -> p99
    """
    if not values:
        return None

    if not 0 <= p <= 1:
        raise ValueError("p must be between 0 and 1")

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * p

    lower = int(position)
    upper = min(lower + 1, len(values) - 1)

    fraction = position - lower

    return (
        values[lower]
        + fraction * (values[upper] - values[lower])
    )


def summarize(results, elapsed):
    latencies = [latency for _, latency in results]

    if not latencies:
        print("No completed requests.")
        return

    ok = sum(
        1 for status, _ in results
        if status is not None and 200 <= status < 300
    )

    shed_429 = sum(
        1 for status, _ in results
        if status == 429
    )

    shed_503 = sum(
        1 for status, _ in results
        if status == 503
    )

    errored = sum(
        1 for status, _ in results
        if status is None
    )

    p50 = percentile(latencies, 0.50)
    p90 = percentile(latencies, 0.90)
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)

    throughput = len(results) / elapsed

    print()
    print("========== RESULTS ==========")
    print(f"total requests : {len(results)}")
    print(f"2xx responses  : {ok}")
    print(f"429 responses  : {shed_429}")
    print(f"503 responses  : {shed_503}")
    print(f"network errors : {errored}")
    print()
    print(f"p50 latency    : {p50 * 1000:.2f} ms")
    print(f"p90 latency    : {p90 * 1000:.2f} ms")
    print(f"p95 latency    : {p95 * 1000:.2f} ms")
    print(f"p99 latency    : {p99 * 1000:.2f} ms")
    print()
    print(f"throughput     : {throughput:.2f} requests/sec")


async def main_async(args):
    url = f"http://127.0.0.1:{args.port}/"

    print(f"URL         : {url}")
    print(f"Requests    : {args.requests}")
    print(f"Concurrency : {args.concurrency}")
    print()

    start = time.perf_counter()

    results = await run(
        url,
        args.requests,
        args.concurrency,
    )

    elapsed = time.perf_counter() - start

    summarize(results, elapsed)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=40,
    )

    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()