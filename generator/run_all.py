"""Regenerate every raw CSV (deterministic, seed 2026). Usage: python generator/run_all.py"""
import subprocess, sys
from pathlib import Path
here = Path(__file__).parent
steps = [["gen_master.py"]] + [["gen_mobility.py", str(y)] for y in range(2020, 2026)] + [["gen_upstream.py"], ["gen_group.py"]]
for s in steps:
    print(">>", " ".join(s))
    subprocess.run([sys.executable, str(here / s[0]), *s[1:]], check=True, cwd=here)
