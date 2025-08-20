"""Amazon Kendra integration tools for AI agents.

This module provides tools for AI agents to query Amazon Kendra search indexes
to retrieve relevant documents and information from enterprise knowledge bases.
"""
from typing import Any
import streetrace.tools.definitions.kendra_query as kq


def _clean_input(input_str: str) -> str:
    """Clean input strings from surrounding whitespace and quotes."""
    return input_str.strip("\"'\\r\\n\\t ")


def kendra_query(
    query: str,
    index_id: str,
    max_results: int = 10,
    region: str = "us-east-1",
) -> dict[str, Any]:
    """Execute a query against Amazon Kendra search index.

    Args:
        query (str): The search query to execute.
        index_id (str): The Kendra index ID to search against.
        work_dir (Path): Working directory (unused but required for consistency).
        max_results (int): Maximum number of results to return. Defaults to 10.
        region (str): AWS region for Kendra service. Defaults to us-east-1.

    Returns:
        dict[str, Any]:
            "tool_name": "kendra_query"
            "result": "success" or "failure"
            "error": error message if the query failed
            "output": JSON string with query results if successful
    """
    return dict(
        kq.kendra_query(
            _clean_input(query),
            _clean_input(index_id),
            max_results,
            _clean_input(region),
        )
    )