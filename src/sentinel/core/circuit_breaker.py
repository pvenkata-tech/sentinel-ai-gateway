"""Circuit Breaker Pattern - Fault tolerance for guardrail processing.

Implements circuit breaker pattern with configurable fail modes:
- "Fail Open": Allow request through on guardrail failure (availability-first)
- "Fail Closed": Block request on guardrail failure (security-first)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class FailMode(Enum):
    """Failure behavior for circuit breaker."""

    FAIL_OPEN = "fail_open"  # Allow through on timeout/error (availability)
    FAIL_CLOSED = "fail_closed"  # Block on timeout/error (security)


class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        timeout: float = 5.0,
        fail_mode: FailMode = FailMode.FAIL_OPEN,
    ):
        """Initialize circuit breaker config.

        Args:
            failure_threshold: Consecutive failures before opening circuit.
            recovery_timeout: Seconds before attempting half-open state.
            success_threshold: Consecutive successes to close circuit from half-open.
            timeout: Timeout for protected operation (seconds).
            fail_mode: How to fail (open=allow, closed=block).
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.fail_mode = fail_mode


class CircuitBreaker:
    """Circuit breaker for handling failures in guardrail processing.

    Prevents cascading failures when guardrail services (NER, pattern matching)
    are slow or hung. Provides graceful degradation with configurable behavior.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit (e.g., "pii_nER", "injection_detect").
            config: CircuitBreakerConfig instance.
        """
        self.name = name
        self.config = config

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_check_time: Optional[datetime] = None

    async def call(
        self,
        func: Callable[..., Any],
        *args,
        default_value: Optional[Any] = None,
        **kwargs,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call.
            default_value: Return value if circuit opens (depends on fail_mode).
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Result from func or default_value if circuit fails.

        Raises:
            CircuitBreakerOpenError: If circuit is open (only in fail_closed mode).
        """
        # Check if we should attempt recovery
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                # Circuit still open, fail per config
                return self._handle_failure(default_value)

        # Try to execute with timeout
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )

            # Success - reset failure count
            self._on_success()
            return result

        except asyncio.TimeoutError:
            logger.warning(
                f"Circuit breaker '{self.name}' timeout after {self.config.timeout}s"
            )
            self._on_failure()
            return self._handle_failure(default_value)

        except Exception as e:
            logger.error(f"Circuit breaker '{self.name}' caught error: {e}")
            self._on_failure()
            return self._handle_failure(default_value)

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        should_recover = elapsed >= self.config.recovery_timeout

        if should_recover:
            logger.info(
                f"Circuit breaker '{self.name}' attempting recovery "
                f"after {elapsed:.1f}s"
            )

        return should_recover

    def _on_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                logger.info(
                    f"Circuit breaker '{self.name}' recovered, "
                    f"closing circuit after {self.success_count} successes"
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset failure count on success

    def _on_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery, reopen circuit
            logger.warning(
                f"Circuit breaker '{self.name}' failed during recovery, "
                f"reopening circuit"
            )
            self.state = CircuitState.OPEN
            self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                logger.warning(
                    f"Circuit breaker '{self.name}' failure threshold reached "
                    f"({self.failure_count}), opening circuit"
                )
                self.state = CircuitState.OPEN

    def _handle_failure(self, default_value: Any) -> Any:
        """Handle failure according to fail mode.

        Args:
            default_value: Default return value for this failure.

        Returns:
            Default value if fail_open, raises if fail_closed.

        Raises:
            CircuitBreakerOpenError: In fail_closed mode.
        """
        if self.config.fail_mode == FailMode.FAIL_OPEN:
            logger.debug(
                f"Circuit breaker '{self.name}' FAIL_OPEN: returning default value"
            )
            return default_value

        else:  # FAIL_CLOSED
            logger.error(
                f"Circuit breaker '{self.name}' FAIL_CLOSED: rejecting request"
            )
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open, request rejected for safety"
            )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def status(self) -> dict:
        """Get current circuit breaker status.

        Returns:
            Dictionary with state, failure count, last failure time.
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            "fail_mode": self.config.fail_mode.value,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and fail_closed is configured."""

    pass
