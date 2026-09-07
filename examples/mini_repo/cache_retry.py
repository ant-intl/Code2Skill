"""Small source fixture used by the offline pipeline demo."""


def fetch_with_retry(fetch, attempts):
    """Return the first successful result or fail after a bounded retry loop."""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for _ in range(attempts):
        try:
            return fetch()
        except OSError:
            continue
    raise RuntimeError("retry budget exhausted")
