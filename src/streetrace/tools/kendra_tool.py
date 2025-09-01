"""Amazon Kendra integration tools for AI agents.

This module provides tools for AI agents to query Amazon Kendra search indexes
to retrieve relevant documents and information from enterprise knowledge bases.
"""
import os
from typing import Any

import streetrace.tools.definitions.kendra_query as kq

AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

def _clean_input(input_str: str) -> str:
    """Clean input string by removing surrounding whitespace and quotes.

    Args:
        input_str (str): The string to clean.

    Returns:
        str: A cleaned string without surrounding whitespace or quotes.

    """
    # Strip surrounding whitespace first, then strip surrounding quotes
    return input_str.strip().strip('"').strip("'")


def kendra_query(
    query: str,
    index_id: str,
    max_results: int = 10,
    region: str = AWS_REGION,
    profile: str = AWS_PROFILE,
) -> dict[str, Any]:
    """Execute a query against Amazon Kendra search index.

    Args:
        query (str): The search query to execute.
        index_id (str): The Kendra index ID to search against.
        max_results (int): Maximum number of results to return. Defaults to 10.
        region (str): AWS region for Kendra service. Defaults to us-east-1.
        profile (str): AWS profile name to use. Defaults to None.

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
            _clean_input(profile),
        ),
    )
