"""Compatibility entry point for the selected-skill verifier."""
import runpy
import sys
from pathlib import Path
scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts))
if __name__ == '__main__':
    runpy.run_path(str(scripts / 'verify_install.py'), run_name='__main__')
