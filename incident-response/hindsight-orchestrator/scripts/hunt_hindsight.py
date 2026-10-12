import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'kape_analysis'))
from investigation_core.workflow import run
if __name__ == '__main__':
    raise SystemExit(run('hindsight'))
