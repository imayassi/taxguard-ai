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
from pathlib import Path

# Add backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))
os.chdir(backend_path)

# Import the app module which runs everything
import app
