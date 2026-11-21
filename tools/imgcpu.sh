#!/bin/sh
# usage: imgcpu.sh IMAGE DATASET OUT [ENV=VAL ...]
# Runs the built image under the scorer's flags, prints the CPU every process
# in the container used (selector and its children) and the score.
cd "$(dirname "$0")/.."
I=$1; D=$(readlink -f "$2"); O=$3; shift 3
ENVS=""; for e in "$@"; do ENVS="$ENVS --env $e"; done
docker run --rm --platform linux/amd64 --network none --cpus 2 --memory 4096m --memory-swap 4096m --pids-limit 256 \
  --read-only --tmpfs /tmp:rw,size=64m,mode=1777 --cap-drop ALL --security-opt no-new-privileges --user 65534:65534 \
  --env HOME=/tmp $ENVS -v "$D/commits":/data/commits:ro -v "$D/tests.json":/data/tests.json:ro "$I" \
  python -c "
import resource, subprocess, sys, time
t = time.time()
subprocess.run([sys.executable, '-X', 'frozen_modules=on', '/app/selector.py'], stderr=open('/tmp/why.log', 'w'))
r = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f'cpu {r.ru_utime + r.ru_stime:.2f} s wall {time.time() - t:.1f} s', file=sys.stderr)
" > "$O"
python3 score.py "$D" "$D/answers.json" "$O" | head -2 | tr '\n' ' '; echo
