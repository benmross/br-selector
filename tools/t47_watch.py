"""Keep the mandatory handoff current while long full-suite labels run."""
import subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; answer=ROOT/'mutants/t47/answers.json'; seen=None
while not (ROOT/'work/t47-watch.stop').exists():
 stamp=answer.stat().st_mtime_ns if answer.exists() else None
 if stamp!=seen:
  subprocess.run(['python3',str(ROOT/'tools/t47_progress.py')],cwd=ROOT,check=True)
  seen=stamp
 time.sleep(5)
