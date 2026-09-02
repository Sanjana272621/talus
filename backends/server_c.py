from fastapi import FastAPI
import time

app = FastAPI()


@app.get("/")
def home():
    time.sleep(0.2) #fake latency of 200 milliseconds
    return {
        "server": "C",
        "message": "Hello from Server C"
    }


@app.get("/health")
def health():
    return {
        "server": "C",
        "status": "healthy"
    }