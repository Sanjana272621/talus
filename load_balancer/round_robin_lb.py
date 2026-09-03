#baseline load balancer: Round Robin
from fastapi import FastAPI, Request
import httpx
from load_balancer.backend import Backend
import time

app = FastAPI()

client = httpx.AsyncClient()

BACKENDS = [
    Backend("A", "http://127.0.0.1:9001"),
    Backend("B", "http://127.0.0.1:9002"),
    Backend("C", "http://127.0.0.1:9003"),
]

current_backend = 0

@app.get("/")
async def proxy(request: Request):
    global current_backend

    backend = BACKENDS[current_backend]

    # Cycle through each backend
    start = time.perf_counter()
    response = await client.get(f"{backend.url}/")
    end = time.perf_counter()

    latency = end - start
    backend.latency = latency
    backend.requests += 1

    current_backend = (current_backend + 1) % len(BACKENDS)

    return response.json()