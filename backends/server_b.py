from fastapi import FastAPI
import time

app = FastAPI()


@app.get("/")
def home():
    time.sleep(0.05) #fake latency of 50 milliseconds
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