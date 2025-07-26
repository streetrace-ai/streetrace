#!/usr/bin/env python3
"""SARIF generator for per-file code reviews.

This module generates SARIF (Static Analysis Results Interchange Format) files
from aggregated per-file review data for GitHub integration.
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


def map_severity_to_sarif_level(severity: str) -> str:
    """Map our severity levels to SARIF-compliant levels."""
    mapping = {
        'error': 'error',
        'warning': 'warning', 
        'notice': 'note',  # SARIF uses 'note' instead of 'notice'
        'info': 'note',
        'note': 'note'
    }
    return mapping.get(severity, 'note')  # Default to 'note' for unknown severities


def generate_sarif_from_per_file_review(review_data: Dict) -> Dict:
    """Generate SARIF format from per-file aggregated review data."""
    
    # Extract metadata
    statistics = review_data.get('statistics', {})
    issues = review_data.get('issues', [])
    summary = review_data.get('summary', 'AI Code Review completed')
    
    # Create unique rules for each issue type
    rules = {}
    results = []
    
    for issue in issues:
        severity = issue.get('severity', 'notice')
        category = issue.get('category', 'quality')
        title = issue.get('title', 'Code Issue')
        message = issue.get('message', '')
        file_path = issue.get('file', '')
        line = issue.get('line', 1)
        
        # Create rule ID
        rule_id = f"ai-code-review/{category}"
        
        # Add rule if not already present
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": title,
                "shortDescription": {
                    "text": title
                },
                "fullDescription": {
                    "text": message
                },
                "helpUri": "https://github.com/your-org/street-race/blob/main/docs/CODE_REVIEW_RULES.md",
                "properties": {
                    "category": category,
                    "severity": severity
                }
            }
        
        # Create result entry
        result = {
            "ruleId": rule_id,
            "level": map_severity_to_sarif_level(severity),
            "message": {
                "text": message
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": file_path
                    },
                    "region": {
                        "startLine": line,
                        "endLine": line
                    }
                }
            }],
            "partialFingerprints": {
                "primaryLocationLineHash": _generate_fingerprint(file_path, line, message)
            }
        }
        
        results.append(result)
    
    # Build SARIF document
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "StreetRace AI Code Review (Per-File)",
                    "version": "2.0.0",
                    "informationUri": "https://github.com/your-org/street-race",
                    "rules": list(rules.values())
                }
            },
            "results": results,
            "properties": {
                "review_summary": summary,
                "statistics": statistics,
                "timestamp": datetime.now().isoformat(),
                "review_type": "per-file",
                "total_issues": len(issues)
            }
        }]
    }
    
    return sarif


def _generate_fingerprint(file_path: str, line: int, message: str) -> str:
    """Generate a fingerprint for issue deduplication."""
    content = f"{file_path}:{line}:{message}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def main():
    """Main entry point for SARIF generation."""
    if len(sys.argv) != 3:
        print("Usage: python per_file_sarif_generator.py <review_json_file> <output_sarif_file>")
        sys.exit(1)
    
    review_json_file = Path(sys.argv[1])
    output_sarif_file = Path(sys.argv[2])
    
    if not review_json_file.exists():
        print(f"Error: Review JSON file not found: {review_json_file}")
        sys.exit(1)
    
    try:
        # Load review data
        with review_json_file.open() as f:
            review_data = json.load(f)
        
        # Generate SARIF
        sarif_data = generate_sarif_from_per_file_review(review_data)
        
        # Save SARIF file
        with output_sarif_file.open('w') as f:
            json.dump(sarif_data, f, indent=2)
        
        print(f"SARIF file generated successfully: {output_sarif_file}")
        
        # Print summary
        statistics = review_data.get('statistics', {})
        print(f"Files reviewed: {statistics.get('files_changed', 0)}")
        print(f"Total issues: {statistics.get('total_issues', 0)}")
        print(f"Errors: {statistics.get('errors', 0)}")
        print(f"Warnings: {statistics.get('warnings', 0)}")
        print(f"Notices: {statistics.get('notices', 0)}")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in review file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating SARIF: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()