"""Run the selector and report the CPU it and its children used (stderr)."""
import resource
import subprocess
import sys
import time

t0 = time.time()
with open(sys.argv[1], "w") as out, open(sys.argv[2], "w") as err:
    subprocess.run([sys.executable, "-X", "frozen_modules=on", "/app/selector.py"], stdout=out, stderr=err)
r = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"cpu {r.ru_utime + r.ru_stime:.2f} s (user {r.ru_utime:.2f} sys {r.ru_stime:.2f}) wall {time.time() - t0:.1f} s maxrss {r.ru_maxrss // 1024} MB")
