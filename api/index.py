import sys
import os

# Ensure the parent directory is in the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase3_backend_api import app
