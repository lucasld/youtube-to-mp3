"""Rate limiting utilities to avoid YouTube bot detection."""

import time
import random


class RateLimiter:
    """Manages request rate limiting to avoid bot detection."""

    def __init__(
        self, min_delay: float = 1.0, max_delay: float = 3.0, jitter: bool = True
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.last_request_time = 0.0

    def wait_if_needed(self) -> None:
        """Wait until the minimum delay has passed since the last request."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            if self.jitter:
                # Add some randomness to avoid detection patterns
                sleep_time += random.uniform(0, self.max_delay - self.min_delay)
            time.sleep(min(sleep_time, self.max_delay))

        self.last_request_time = time.time()

    def reset(self) -> None:
        """Reset the rate limiter state."""
        self.last_request_time = 0.0


class ExponentialBackoff:
    """Implements exponential backoff for failed requests."""

    def __init__(
        self, base_delay: float = 1.0, max_delay: float = 60.0, multiplier: float = 2.0
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.attempt_count = 0

    def get_delay(self) -> float:
        """Get the delay for the current attempt."""
        if self.attempt_count == 0:
            return 0.0

        delay = self.base_delay * (self.multiplier ** (self.attempt_count - 1))
        return min(delay, self.max_delay)

    def record_attempt(self) -> None:
        """Record that an attempt was made."""
        self.attempt_count += 1

    def record_success(self) -> None:
        """Record that the last attempt succeeded."""
        self.attempt_count = 0

    def should_retry(self, max_attempts: int = 5) -> bool:
        """Check if another attempt should be made."""
        return self.attempt_count < max_attempts


class RequestThrottler:
    """Combines rate limiting and backoff strategies."""

    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=1.5, max_delay=4.0)
        self.backoff = ExponentialBackoff(base_delay=2.0, max_delay=30.0)

    def pre_request(self) -> None:
        """Called before making a request."""
        self.rate_limiter.wait_if_needed()

    def post_request(self, success: bool) -> None:
        """Called after a request completes."""
        if success:
            self.backoff.record_success()
        else:
            self.backoff.record_attempt()

    def get_backoff_delay(self) -> float:
        """Get the current backoff delay."""
        return self.backoff.get_delay()

    def should_retry(self) -> bool:
        """Check if request should be retried."""
        return self.backoff.should_retry()
