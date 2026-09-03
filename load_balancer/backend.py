import random

class Backend:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        # self.latency = None
        self.requests = 0
        self.failures = 0
        self.healthy = True
        self.ewma_latency = None
        self.active_requests = 0
        self.consecutiveFailures = 0

    def performance_score(self):
        if self.ewma_latency is None:
            return 1.0

        latency_ms = self.ewma_latency * 1000

        return 1 / (
            latency_ms * (1 + self.active_requests)
        )
