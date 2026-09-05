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

    def price(self):
    """
    Congestion price for this backend, inspired by Rajomon's
    per-API pricing: cost rises with both observed latency and
    how many requests are currently in flight. This is just the
    inverse of performance_score, expressed as a "cost" so it
    composes naturally with the rate limiter's token cost.
    """
        if self.ewma_latency is None:
            latency_ms = 1.0
        else:
            latency_ms = max(self.ewma_latency * 1000, 1.0)

        return latency_ms * (1 + self.active_requests)