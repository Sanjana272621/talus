from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
import httpx
import random
import time

from load_balancer.backend import Backend


ALPHA = 0.2
TIMEOUT = 2.0
FAILURE_THRESHOLD = 3
COOLDOWN = 5.0


client = httpx.AsyncClient(timeout=TIMEOUT)

BACKENDS = [
    Backend("A", "http://127.0.0.1:9001"),
    Backend("B", "http://127.0.0.1:9002"),
    Backend("C", "http://127.0.0.1:9003"),
]


async def recovery_loop():
    while True:
        for backend in BACKENDS:
            if backend.state == "OPEN":
                if time.monotonic() - backend.opened_at >= COOLDOWN:
                    backend.state = "HALF_OPEN"

                    print(
                        f"[RECOVERY] {backend.name} -> HALF_OPEN"
                    )

        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(recovery_loop())

    yield

    task.cancel()

    await client.aclose()


app = FastAPI(lifespan=lifespan)


def choose_backend(exclude=None):
    available = [
        backend
        for backend in BACKENDS
        if backend != exclude
        and backend.state == "CLOSED"
    ]

    half_open = [
        backend
        for backend in BACKENDS
        if backend != exclude
        and backend.state == "HALF_OPEN"
    ]

    if half_open:
        return half_open[0]

    if not available:
        return None

    scores = [
        backend.performance_score()
        for backend in available
    ]

    return random.choices(
        available,
        weights=scores,
        k=1
    )[0]


def record_success(backend, latency):
    backend.latency = latency
    backend.requests += 1
    backend.consecutive_failures = 0
    backend.state = "CLOSED"
    backend.opened_at = None

    if backend.ewma_latency is None:
        backend.ewma_latency = latency
    else:
        backend.ewma_latency = (
            ALPHA * latency
            + (1 - ALPHA) * backend.ewma_latency
        )


def record_failure(backend):
    backend.failures += 1
    backend.consecutive_failures += 1

    if (
        backend.state == "HALF_OPEN"
        or backend.consecutive_failures >= FAILURE_THRESHOLD
    ):
        backend.state = "OPEN"
        backend.opened_at = time.monotonic()

        print(
            f"[CIRCUIT] {backend.name} -> OPEN"
        )


async def forward_request(backend):
    backend.active_requests += 1

    start = time.perf_counter()

    try:
        response = await client.get(
            f"{backend.url}/"
        )

        latency = time.perf_counter() - start

        record_success(backend, latency)

        print(
            f"[REQUEST] {backend.name} "
            f"{latency * 1000:.2f}ms "
            f"EWMA={backend.ewma_latency * 1000:.2f}ms "
            f"active={backend.active_requests}"
        )

        return response

    except (httpx.TimeoutException, httpx.RequestError):
        record_failure(backend)

        return None

    finally:
        backend.active_requests -= 1


@app.get("/")
async def proxy(request: Request):

    attempted = set()

    for _ in range(len(BACKENDS)):

        backend = choose_backend()

        if backend is None:
            break

        if backend.name in attempted:
            break

        attempted.add(backend.name)

        response = await forward_request(backend)

        if response is not None:
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )

    return JSONResponse(
        status_code=503,
        content={
            "error": "No backend available"
        }
    )


@app.get("/stats")
async def stats():

    result = {}

    for backend in BACKENDS:
        result[backend.name] = {
            "state": backend.state,
            "latency_ms": (
                round(backend.latency * 1000, 2)
                if backend.latency is not None
                else None
            ),
            "ewma_ms": (
                round(backend.ewma_latency * 1000, 2)
                if backend.ewma_latency is not None
                else None
            ),
            "requests": backend.requests,
            "active_requests": backend.active_requests,
            "failures": backend.failures,
            "consecutive_failures": backend.consecutive_failures,
            "score": round(
                backend.performance_score(),
                6
            )
        }

    return result