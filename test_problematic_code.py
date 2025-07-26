#!/usr/bin/env python3
"""Test file with intentional code quality issues for AI review testing."""

import os
import sys
import subprocess
from typing import List, Dict, Any
import json

# Global variable (bad practice)
GLOBAL_CONFIG = {}

class DatabaseConnector:
    """Database connection handler with security issues."""
    
    def __init__(self, password):
        # Issue: Password stored in plain text
        self.password = password
        self.connection = None
    
    def connect(self, host, user, password):
        # Issue: SQL injection vulnerability
        query = f"SELECT * FROM users WHERE username = '{user}' AND password = '{password}'"
        print(f"Executing: {query}")  # Issue: Logging sensitive data
        
        # Issue: Broad exception handling
        try:
            # Simulated connection
            self.connection = {"host": host, "user": user}
        except:
            pass  # Issue: Silent failure
    
    def execute_command(self, cmd):
        # Issue: Command injection vulnerability
        os.system(cmd)
        
def process_user_data(data):
    # Issue: No type hints
    # Issue: No input validation
    eval(data)  # Issue: Dangerous eval usage
    
def load_config():
    # Issue: Hardcoded credentials
    API_KEY = "sk-1234567890abcdef"
    SECRET = "my-secret-password-123"
    
    # Issue: Using global variable
    global GLOBAL_CONFIG
    GLOBAL_CONFIG = {
        "api_key": API_KEY,
        "secret": SECRET
    }
    
def write_file(filename, content):
    # Issue: No error handling
    # Issue: No path validation
    f = open(filename, 'w')
    f.write(content)
    # Issue: File not closed properly (no context manager)
    
def divide_numbers(a, b):
    # Issue: No zero division check
    return a / b

class UserManager:
    def __init__(self):
        self.users = []
    
    def add_user(self, name, email, age):
        # Issue: No input validation
        # Issue: Age could be negative or non-numeric
        user = {
            "name": name,
            "email": email,  # Issue: No email format validation
            "age": age
        }
        self.users.append(user)
        
    def get_user(self, index):
        # Issue: No bounds checking
        return self.users[index]
        
def parse_json(json_string):
    # Issue: No exception handling for JSON parsing
    data = json.loads(json_string)
    return data
    
def recursive_function(n):
    # Issue: No base case checking, infinite recursion possible
    if n = 10:  # Issue: Assignment instead of comparison
        return n
    return recursive_function(n + 1)
    
# Issue: Inconsistent naming convention
def myFunction(MyParameter):
    # Issue: Unused variable
    unused_var = 42
    
    # Issue: Magic numbers
    if MyParameter > 100:
        return MyParameter * 2.5
    
# Issue: TODO comments without tracking
# TODO: Fix this later
# FIXME: This is broken

# Issue: Dead code
if False:
    print("This will never run")
    
# Issue: Duplicate code
def calculate_area_circle(radius):
    return 3.14159 * radius * radius
    
def calculate_area_circle_duplicate(r):
    return 3.14159 * r * r

# Main execution without proper guard
print("Script loaded")  # This runs on import