"""
TaxGuard AI - Streamlit Cloud Entry Point
=========================================
This file serves as the entry point for Streamlit Cloud deployment.

For Streamlit Cloud deployment:
- Repository: your-username/taxguard-ai
- Branch: main  
- Main file path: streamlit_app.py
"""

import sys
import os

# Get absolute paths
_this_file = os.path.abspath(__file__)
_this_dir = os.path.dirname(_this_file)
_backend_path = os.path.join(_this_dir, "backend")

# Add backend directory to Python path
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

# Import and run the app (executes all streamlit code)
import app
