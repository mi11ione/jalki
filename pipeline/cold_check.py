"""Run the shipped cold start in its check mode: python3 stages/pj-v5a/cold_start.py --check (temporary port, fetch every asset, exit)."""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
r = subprocess.run([sys.executable, str(HERE / 'cold_start.py'), '--check'], capture_output=True, text=True, timeout=120)
print(r.stdout.strip(), r.stderr.strip()[-800:])
print('cold_start --check exit', r.returncode)
sys.exit(r.returncode)
