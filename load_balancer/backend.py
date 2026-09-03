class Backend:
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.latency = None
        self.requests = 0
        self.failures = 0
        self.healthy = True