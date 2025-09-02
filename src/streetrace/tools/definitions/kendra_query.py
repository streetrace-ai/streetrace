"""Amazon Kendra retrieve tool implementation."""

import json

import boto3
from boto3.exceptions import Boto3Error
from botocore.exceptions import ClientError

from streetrace.tools.definitions.result import OpResult, op_error, op_success


def kendra_query(
    query: str,
    index_id: str,
    max_results: int = 10,
    region: str = "us-east-1",
    profile: str = "default",
) -> OpResult:
    """Retrieve relevant passages from Amazon Kendra search index.

    Args:
        query (str): The search query to retrieve passages for.
        index_id (str): The Kendra index ID to retrieve from.
        max_results (int): Maximum number of results to return. Defaults to 10.
        region (str): AWS region for Kendra service. Defaults to us-east-1.
        profile (str): AWS profile name to use. Defaults to None.

    Returns:
        OpResult: Dictionary containing:
            "tool_name": "kendra_query"
            "result": "success" or "failure"
            "error": error message if the retrieve failed
            "output": JSON string with retrieve results if successful

    """
    try:
        # Initialize Kendra client
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        kendra_client = session.client("kendra", region_name=region)

        # Execute the retrieve
        response = kendra_client.retrieve(
            IndexId=index_id,
            QueryText=query,
            PageSize=max_results,
        )

        # Format results
        results = []
        for item in response.get("ResultItems", []):
            result_item = {
                "content": item.get("Content", ""),
                "title": item.get("DocumentTitle", ""),
                "uri": item.get("DocumentURI", ""),
                "score": item.get("ScoreAttributes", {}).get("ScoreConfidence", ""),
            }

            # Add document attributes if present
            if "DocumentAttributes" in item:
                result_item["attributes"] = item["DocumentAttributes"]

            results.append(result_item)

        output_data = {
            "query": query,
            "total_results": len(results),
            "results": results,
        }

        return op_success(
            tool_name="kendra_query",
            output=json.dumps(output_data, indent=2),
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        return op_error(
            tool_name="kendra_query",
            error=f"AWS {error_code}: {error_message}",
        )
    except Boto3Error as e:
        return op_error(
            tool_name="kendra_query",
            error=f"AWS error: {e!s}",
        )
    except (ValueError, TypeError, KeyError) as e:
        return op_error(
            tool_name="kendra_query",
            error=f"Data processing error: {e!s}",
        )
