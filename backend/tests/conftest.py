import os
import sys
from pathlib import Path

# Ensure we import the in-repo axi package instead of any installed version
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
