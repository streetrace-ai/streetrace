"""test retry"""

from datetime import datetime

from tenacity import (
    TryAgain,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)


@retry(retry=retry_if_exception_type(ValueError), stop=stop_after_attempt(4), wait=wait_incrementing(start=2, increment=2, max=5), reraise=True)
def _call_with_retry(
) -> None:
    print(f"Calling at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")  # noqa: DTZ005, T201
    msg = "test"
    raise TryAgain


try:
    _call_with_retry()
except Exception:
    pass

print(_call_with_retry.statistics)  # noqa: T201

try:
    _call_with_retry()
except Exception:
    pass

print(_call_with_retry.statistics)  # noqa: T201