"""Record all CPU, including pytest descendants, for a label command."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

t0 = time.monotonic()
status = subprocess.run(sys.argv[2:]).returncode
r = resource.getrusage(resource.RUSAGE_CHILDREN)
Path(sys.argv[1]).write_text(json.dumps(dict(wall=time.monotonic()-t0,
    cpu=r.ru_utime+r.ru_stime, exitstatus=status), indent=2))
sys.exit(status)
