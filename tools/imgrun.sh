#!/bin/sh
# usage: imgrun.sh IMAGE DATASET OUT [ENV=VAL ...]
# Runs the built image under the scorer's flags. Writes the selector's stdout to
# OUT, its stderr to OUT.why, and the CPU every process in the container used
# (selector and its children) and the wall time to OUT.cpu.
cd "$(dirname "$0")/.."
I=$1; D=$(readlink -f "$2"); O=$3; shift 3
ENVS=""; for e in "$@"; do ENVS="$ENVS --env $e"; done
docker run --rm --platform linux/amd64 --network none --cpus 2 --memory 4096m --memory-swap 4096m --pids-limit 256 \
  --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --cap-drop ALL --security-opt no-new-privileges --user 65534:65534 \
  --env HOME=/tmp $ENVS -v "$D/commits":/data/commits:ro -v "$D/tests.json":/data/tests.json:ro "$I" \
  python -c "
import resource, subprocess, sys, time
def cg():
    try:
        return int(dict(l.split() for l in open('/sys/fs/cgroup/cpu.stat'))['usage_usec']) / 1e6
    except Exception:
        return float('nan')
c0 = cg()
t = time.time()
r = subprocess.run([sys.executable, '-X', 'frozen_modules=on', '/app/selector.py'], stderr=subprocess.PIPE, text=True)
u = resource.getrusage(resource.RUSAGE_CHILDREN)
sys.stderr.write(r.stderr)
sys.stderr.write(f'CPU {u.ru_utime + u.ru_stime:.2f} s cgroup {cg() - c0:.2f} s wall {time.time() - t:.1f} s exit {r.returncode}\n')
" > "$O" 2> "$O.why"
tail -1 "$O.why" > "$O.cpu"
