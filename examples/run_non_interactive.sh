#!/bin/bash
# Example script demonstrating non-interactive usage of Streetrace

# Ensure the directory exists
mkdir -p examples

# Create example script using Claude
echo "Creating a hello.py script using Claude..."
python main.py --model claude --prompt "Create a hello.py script that prints 'Hello, world!' and includes a main function"

# Run the generated script
echo -e "\nRunning the generated script:"
python hello.py

# Create a test for the hello script
echo -e "\nCreating a test for hello.py using Gemini..."
python main.py --model gemini --prompt "Create a test_hello.py script that tests the hello.py script's functionality"

# Run the test
echo -e "\nRunning the test script:"
python -m unittest test_hello.py