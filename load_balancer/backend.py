import time


class Backend:
    def __init__(self, name, url):
        self.name = name
        self.url = url

        self.latency = None
        self.ewma_latency = None

        self.requests = 0
        self.active_requests = 0
        self.failures = 0
        self.consecutive_failures = 0

        self.state = "CLOSED"
        self.opened_at = None

    def performance_score(self):
        if self.ewma_latency is None:
            return 1.0

        latency_ms = max(self.ewma_latency * 1000, 1)

        return 1 / (
            latency_ms * (1 + self.active_requests)
        )