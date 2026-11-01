import sys
import os

# Allow running `pytest` directly from the project root without the Makefile.
# The Makefile sets PYTHONPATH=src; this does the same for bare pytest invocations.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
