#!/usr/bin/env python3
"""
Simple test script to verify the --prompt parameter functionality
"""

import sys
import os

# Create a temporary backup of the original input function
original_input = input

# Mock the input function to simulate user input of "exit"
def mock_input(prompt):
    return "exit"

# Replace the built-in input function with our mock
input = mock_input

# Set environment variable for testing
os.environ['ANTHROPIC_API_KEY'] = 'mock_key'

# Run the main script with the --prompt argument
sys.argv = ['main.py', '--prompt', 'Test prompt']

# Import main after setting up mocks
try:
    import main
    
    # Call main function (should use the --prompt parameter and skip interactive mode)
    main.main()
    
    print("Test passed - The script ran with the --prompt parameter")
    
except Exception as e:
    print(f"Test failed: {e}")
    
finally:
    # Restore the original input function
    input = original_input