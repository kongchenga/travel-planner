"""Retry decorators for external HTTP calls."""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

RETRYABLE = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectTimeout,
    ConnectionError,
    TimeoutError,
)

retry_http = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRYABLE),
    reraise=True,
)
