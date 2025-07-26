#!/usr/bin/env python3
"""Validate and fix AI-generated review JSON files."""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def validate_and_fix_json(file_path: str) -> bool:
    """Validate and fix review JSON structure."""
    try:
        # Try to load the JSON file
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Check if it has the required structure
        if not isinstance(data, dict):
            print(f"❌ JSON is not a dictionary")
            return False
            
        # Ensure required top-level keys exist
        required_keys = ['summary', 'statistics', 'issues', 'positive_feedback']
        for key in required_keys:
            if key not in data:
                data[key] = [] if key in ['issues', 'positive_feedback'] else {}
                
        # Fix statistics structure
        if not isinstance(data['statistics'], dict):
            data['statistics'] = {}
            
        stats_defaults = {
            'files_changed': 0,
            'total_issues': 0,
            'errors': 0,
            'warnings': 0,
            'notices': 0
        }
        
        for key, default in stats_defaults.items():
            if key not in data['statistics']:
                data['statistics'][key] = default
                
        # Fix issues structure
        if not isinstance(data['issues'], list):
            data['issues'] = []
            
        # Validate and fix each issue
        fixed_issues = []
        for issue in data['issues']:
            if not isinstance(issue, dict):
                continue
                
            # Ensure required fields
            fixed_issue = {
                'severity': issue.get('severity', 'notice'),
                'file': issue.get('file', ''),
                'line': int(issue.get('line', 1)),
                'title': issue.get('title', 'Code Review Issue'),
                'message': issue.get('message', ''),
                'category': issue.get('category', 'quality')
            }
            
            # Add optional fields if present
            if 'end_line' in issue:
                fixed_issue['end_line'] = int(issue['end_line'])
            if 'code_snippet' in issue:
                fixed_issue['code_snippet'] = str(issue['code_snippet'])
                
            # Validate severity
            if fixed_issue['severity'] not in ['error', 'warning', 'notice']:
                fixed_issue['severity'] = 'notice'
                
            # Validate category
            valid_categories = ['security', 'performance', 'quality', 'testing', 'maintainability']
            if fixed_issue['category'] not in valid_categories:
                fixed_issue['category'] = 'quality'
                
            fixed_issues.append(fixed_issue)
            
        data['issues'] = fixed_issues
        
        # Fix positive_feedback structure
        if not isinstance(data['positive_feedback'], list):
            data['positive_feedback'] = []
            
        # Update statistics based on actual issues
        data['statistics']['total_issues'] = len(data['issues'])
        data['statistics']['errors'] = sum(1 for i in data['issues'] if i['severity'] == 'error')
        data['statistics']['warnings'] = sum(1 for i in data['issues'] if i['severity'] == 'warning')
        data['statistics']['notices'] = sum(1 for i in data['issues'] if i['severity'] == 'notice')
        
        # Write the fixed JSON back
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"✅ JSON validated and fixed: {file_path}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON syntax: {e}")
        return False
    except Exception as e:
        print(f"❌ Error processing JSON: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python3 validate_review_json.py <json_file>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
        
    if validate_and_fix_json(file_path):
        print("🎉 JSON validation successful")
    else:
        print("💥 JSON validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()