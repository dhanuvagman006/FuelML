import sys
import os

# Ensure the parent directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase3_backend_api import app

# Vercel expects an 'app' variable or a 'handler' at module level.
# FastAPI's ASGI app is auto-detected by @vercel/python runtime.
