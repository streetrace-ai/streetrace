#!/usr/bin/env python3
"""
Example of using Streetrace in non-interactive mode from Python.
This script uses subprocess to call main.py with different prompts.
"""

import subprocess
import os

def run_streetrace(prompt, model="claude"):
    """
    Run Streetrace with a specific prompt and model.
    
    Args:
        prompt: The prompt to send to the AI model
        model: Which model to use (claude or gemini)
    
    Returns:
        subprocess.CompletedProcess: Result of the command
    """
    cmd = ["python", "main.py", "--model", model, "--prompt", prompt]
    print(f"Running: {' '.join(cmd)}")
    
    # Run the command and capture output
    result = subprocess.run(cmd, 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           text=True,
                           check=False)
    
    if result.returncode != 0:
        print(f"Command failed with code {result.returncode}")
        print(f"Error: {result.stderr}")
    
    return result

def main():
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(script_dir))  # Change to parent directory
    
    # Create a simple Python script
    run_streetrace(
        "Create a calculator.py script with add, subtract, multiply, and divide functions.",
        model="claude"
    )
    
    # Create tests for the calculator
    run_streetrace(
        "Create test_calculator.py with unit tests for calculator.py.",
        model="claude"
    )
    
    # Run the tests
    print("\nRunning tests...")
    test_result = subprocess.run(["python", "-m", "unittest", "test_calculator.py"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
    
    print(f"Test output:\n{test_result.stdout}")
    if test_result.stderr:
        print(f"Test errors:\n{test_result.stderr}")

if __name__ == "__main__":
    main()