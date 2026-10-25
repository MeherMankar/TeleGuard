from teleguard.core.rate_limiter import RateLimiter


def test_allows_operation_below_limit():
    limiter = RateLimiter()

    assert limiter.can_perform("account", "message") == (True, None)


def test_blocks_operation_at_rate_limit():
    limiter = RateLimiter()
    limiter.record_operation("account", "message", count=RateLimiter.LIMITS["message"])

    allowed, reason = limiter.can_perform("account", "message")

    assert not allowed
    assert "Rate limit exceeded" in reason


def test_blocks_request_that_would_exceed_remaining_quota():
    limiter = RateLimiter()
    limiter.record_operation(
        "account", "message", count=RateLimiter.LIMITS["message"] - 1
    )

    allowed, reason = limiter.can_perform("account", "message", count=2)

    assert not allowed
    assert "Rate limit exceeded" in reason


def test_allows_request_that_fits_remaining_quota():
    limiter = RateLimiter()
    limiter.record_operation(
        "account", "message", count=RateLimiter.LIMITS["message"] - 2
    )

    assert limiter.can_perform("account", "message", count=2) == (True, None)


def test_expires_operations_after_one_hour(monkeypatch):
    current_time = [1000.0]
    monkeypatch.setattr(
        "teleguard.core.rate_limiter.time.time", lambda: current_time[0]
    )
    limiter = RateLimiter()
    limiter.record_operation("account", "message", count=RateLimiter.LIMITS["message"])

    current_time[0] += 3601

    assert limiter.can_perform("account", "message") == (True, None)


def test_blocks_bulk_send_during_cooldown(monkeypatch):
    monkeypatch.setattr("teleguard.core.rate_limiter.time.time", lambda: 1000.0)
    limiter = RateLimiter()
    limiter.record_operation("account", "bulk_send")

    allowed, reason = limiter.can_perform("account", "bulk_send")

    assert not allowed
    assert "Cooldown active" in reason
