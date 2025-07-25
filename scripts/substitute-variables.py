#!/usr/bin/env python3
"""
Script to substitute variables in the GitHub review prompt template.
Used by the GitHub Actions workflow.
"""

import os
import sys

def main():
    if len(sys.argv) != 4:
        print("Usage: substitute-variables.py <template_file> <diff_file> <output_file>")
        sys.exit(1)
    
    template_file = sys.argv[1]
    diff_file = sys.argv[2]
    output_file = sys.argv[3]
    
    # Read template
    try:
        with open(template_file, 'r') as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Error: Template file {template_file} not found")
        sys.exit(1)
    
    # Read diff content
    try:
        with open(diff_file, 'r') as f:
            pr_diff = f.read()
    except FileNotFoundError:
        print(f"Error: Diff file {diff_file} not found")
        sys.exit(1)
    
    # Substitute variables
    template = template.replace('${PR_NUMBER}', os.environ.get('PR_NUMBER', ''))
    template = template.replace('${PR_TITLE}', os.environ.get('PR_TITLE', ''))
    template = template.replace('${PR_AUTHOR}', os.environ.get('PR_AUTHOR', ''))
    template = template.replace('${BASE_BRANCH}', os.environ.get('BASE_BRANCH', ''))
    template = template.replace('${HEAD_BRANCH}', os.environ.get('HEAD_BRANCH', ''))
    template = template.replace('${PR_DIFF}', pr_diff)
    
    # Write output
    try:
        with open(output_file, 'w') as f:
            f.write(template)
        print(f"Successfully created review prompt: {output_file}")
    except Exception as e:
        print(f"Error writing output file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()