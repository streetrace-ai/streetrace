#!/usr/bin/env python3
"""Convert AI code review JSON to GitHub SARIF format.

This script converts the structured JSON review format into SARIF 2.1.0
which integrates natively with GitHub's code scanning system for accurate
line-by-line annotations.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class SarifGenerator:
    """Generate SARIF 2.1.0 format from AI code review JSON."""

    def __init__(self) -> None:
        """Initialize SARIF generator."""
        self.sarif_version = "2.1.0"
        self.tool_name = "StreetRace AI Code Review"
        self.tool_version = "1.0.0"

    def generate_fingerprint(self, issue: Dict[str, Any]) -> str:
        """Generate a stable fingerprint for the issue.
        
        This helps GitHub track issues across commits and prevents duplicates.
        """
        # Create a stable hash from file path, line number, and rule
        content = f"{issue.get('file', '')}{issue.get('line', 0)}{issue.get('title', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def map_severity_to_level(self, severity: str) -> str:
        """Map our severity levels to SARIF levels."""
        mapping = {
            "error": "error",
            "warning": "warning", 
            "notice": "note"
        }
        return mapping.get(severity, "note")

    def create_rule(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Create a SARIF rule definition for an issue."""
        category = issue.get("category", "quality")
        severity = issue.get("severity", "notice")
        
        return {
            "id": f"ai-code-review/{category}",
            "name": issue.get("title", "Code Review Issue"),
            "shortDescription": {
                "text": issue.get("title", "Code Review Issue")
            },
            "fullDescription": {
                "text": issue.get("message", "No description provided")
            },
            "helpUri": "https://github.com/your-org/street-race/blob/main/docs/CODE_REVIEW_RULES.md",
            "properties": {
                "category": category,
                "severity": severity
            }
        }

    def create_result(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Create a SARIF result from an issue."""
        file_path = issue.get("file", "")
        line = issue.get("line", 1)
        end_line = issue.get("end_line", line)
        message = issue.get("message", "")
        code_snippet = issue.get("code_snippet", "")
        
        # Include code snippet in message for debugging if available
        if code_snippet:
            message = f"Code: `{code_snippet}`\n\n{message}"

        result = {
            "ruleId": f"ai-code-review/{issue.get('category', 'quality')}",
            "level": self.map_severity_to_level(issue.get("severity", "notice")),
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
                        "endLine": end_line
                    }
                }
            }],
            "partialFingerprints": {
                "primaryLocationLineHash": self.generate_fingerprint(issue)
            }
        }

        return result

    def extract_rules(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique rules from all issues."""
        rules_map = {}
        
        for issue in issues:
            category = issue.get("category", "quality")
            rule_id = f"ai-code-review/{category}"
            
            if rule_id not in rules_map:
                rules_map[rule_id] = self.create_rule(issue)
        
        return list(rules_map.values())

    def convert_to_sarif(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert AI code review JSON to SARIF format."""
        issues = review_data.get("issues", [])
        statistics = review_data.get("statistics", {})
        
        # Extract unique rules
        rules = self.extract_rules(issues)
        
        # Convert issues to SARIF results
        results = [self.create_result(issue) for issue in issues]
        
        # Create SARIF document
        sarif_doc = {
            "version": self.sarif_version,
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": self.tool_name,
                        "version": self.tool_version,
                        "informationUri": "https://github.com/your-org/street-race",
                        "rules": rules
                    }
                },
                "results": results,
                "properties": {
                    "review_summary": review_data.get("summary", ""),
                    "statistics": statistics,
                    "timestamp": datetime.now().isoformat(),
                    "total_issues": len(issues)
                }
            }]
        }
        
        return sarif_doc

    def generate_sarif_file(self, review_file: str, output_file: str) -> None:
        """Generate SARIF file from review JSON."""
        try:
            # Load review data
            with open(review_file) as f:
                review_data = json.load(f)
            
            # Convert to SARIF
            sarif_doc = self.convert_to_sarif(review_data)
            
            # Write SARIF file
            with open(output_file, 'w') as f:
                json.dump(sarif_doc, f, indent=2)
            
            print(f"✅ SARIF file generated: {output_file}")
            print(f"📊 Converted {len(review_data.get('issues', []))} issues")
            
        except FileNotFoundError:
            print(f"❌ Error: Review file not found: {review_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in review file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error generating SARIF file: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert AI code review JSON to GitHub SARIF format"
    )
    parser.add_argument("review_file", help="Path to the structured review JSON file")
    parser.add_argument("output_file", help="Path for the output SARIF file")
    parser.add_argument(
        "--validate", 
        action="store_true", 
        help="Validate the generated SARIF against schema"
    )
    
    args = parser.parse_args()
    
    generator = SarifGenerator()
    generator.generate_sarif_file(args.review_file, args.output_file)
    
    if args.validate:
        print("📋 SARIF validation not yet implemented")
        print("💡 Use online validators or sarif-sdk for validation")


if __name__ == "__main__":
    main()