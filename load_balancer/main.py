from fastapi import FastAPI, Request
import httpx
import time
import random

from load_balancer.backend import Backend


app = FastAPI()

ALPHA = 0.2
TIMEOUT = 2.0
FAILURE_THRESHOLD = 3


client = httpx.AsyncClient(
    timeout=TIMEOUT
)


BACKENDS = [
    Backend("A", "http://127.0.0.1:9001"),
    Backend("B", "http://127.0.0.1:9002"),
    Backend("C", "http://127.0.0.1:9003"),
]


def choose_backend():
    healthy_backends = [
        backend
        for backend in BACKENDS
        if backend.healthy
    ]

    if not healthy_backends:
        raise RuntimeError("No healthy backends available")

    scores = [
        backend.performance_score()
        for backend in healthy_backends
    ]

    return random.choices(
        healthy_backends,
        weights=scores,
        k=1
    )[0]


@app.get("/")
async def proxy(request: Request):

    #choose backend based on its score
    try:
        backend = choose_backend()
    except RuntimeError:
        return {
            "error": "No healthy backends available"
        }


    backend.active_requests += 1

    start = time.perf_counter()


    try:

        response = await client.get(
            f"{backend.url}/"
        )

        end = time.perf_counter()
        latency = end - start
        backend.latency = latency

        #update EWMA Latency
        if backend.ewma_latency is None:
            backend.ewma_latency = latency

        else:

            backend.ewma_latency = (
                ALPHA * latency
                + (1 - ALPHA) * backend.ewma_latency
            )

        backend.requests += 1

        # Successful request -> reset failures
        backend.consecutive_failures = 0

        backend.healthy = True

        return response.json()


    except httpx.TimeoutException:

        backend.failures += 1
        backend.consecutive_failures += 1

        print(
            f"[TIMEOUT] {backend.name} "
            f"consecutive failures = "
            f"{backend.consecutive_failures}"
        )

        if backend.consecutive_failures >= FAILURE_THRESHOLD:

            backend.healthy = False

            print(
                f"[UNHEALTHY] Backend {backend.name} "
                f"removed from routing"
            )


        return {
            "error": f"Backend {backend.name} timed out"
        }


    except httpx.RequestError as e:

        backend.failures += 1
        backend.consecutive_failures += 1

        print(
            f"[ERROR] {backend.name}: {e}"
        )


        if backend.consecutive_failures >= FAILURE_THRESHOLD:

            backend.healthy = False

            print(
                f"[UNHEALTHY] Backend {backend.name} "
                f"removed from routing"
            )


        return {
            "error": f"Backend {backend.name} unavailable"
        }


    finally:

        backend.active_requests -= 1