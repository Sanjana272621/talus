from fastapi import FastAPI, Request
import httpx

app = FastAPI()

BACKENDS = [
    "http://127.0.0.1:9001",
    "http://127.0.0.1:9002",
    "http://127.0.0.1:9003",
]

current_backend = 0


@app.get("/")
async def proxy(request: Request):
    global current_backend

    backend = BACKENDS[current_backend]

    #cycle through each backend
    current_backend = (current_backend + 1) % len(BACKENDS)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{backend}/")

    return response.json()