"""Make `from engine.engine import ...` resolve when running pytest from api/.

Adds the api/ directory (parent of tests/) to sys.path so the vendored `engine`
package is importable regardless of how pytest is invoked.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
