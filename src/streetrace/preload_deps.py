"""Preload dependencies in background threads."""

import asyncio
import importlib
from concurrent.futures import ThreadPoolExecutor

from streetrace.log import get_logger

logger = get_logger(__name__)

_PRELOADABLE_MODULES = [
    "google.genai",
    "google.adk",
    "litellm",
]


def _safe_import(name: str) -> object | None:
    try:
        module = importlib.import_module(name)
    except Exception:
        logger.exception("Failed to import %s", name)
        return None
    else:
        logger.debug("Successfully imported %s", name)
        return module


async def preload_dependencies(
    max_workers: int = 4,
) -> dict[str, object]:
    """Preload the specified module names in background threads.

    Args:
        module_names: List of module names to import.
        max_workers: Number of threads to use.

    Returns:
        A dict of module_name -> module for successfully imported modules.

    """
    loop = asyncio.get_running_loop()

    def worker() -> dict[str, object]:
        local_result = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_safe_import, name): name
                for name in _PRELOADABLE_MODULES
            }
            for future, name in futures.items():
                module = future.result()
                if module is not None:
                    local_result[name] = module
        return local_result

    return await loop.run_in_executor(None, worker)
