from fastapi import FastAPI
import time

app = FastAPI()


@app.get("/")
def home():
    return {
        "server": "A",
        "message": "Reply from server A: Hello"
    }


@app.get("/health")
def health():
    return {
        "server": "A",
        "status": "healthy"
    }