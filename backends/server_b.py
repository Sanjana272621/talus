from fastapi import FastAPI
import time

app = FastAPI()


@app.get("/")
def home():
    return {
        "server": "B",
        "message": "Hello from Server B"
    }


@app.get("/health")
def health():
    return {
        "server": "B",
        "status": "healthy"
    }