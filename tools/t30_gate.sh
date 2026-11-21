#!/bin/sh
# Run the unmodified shared gate with this worker's stricter rosserver cap.
set -eu
R=$HOME/herald/projects/blast-radius
W=$R/work/wt/t30
mkdir -p "$W/work/capbin"
cat > "$W/work/capbin/docker" <<'PY'
#!/usr/bin/env python3
import os
import sys
args = sys.argv[1:]
if args and args[0] in ('run', 'build'):
    limits = {'--cpus':'1','--memory':'1024m','--memory-swap':'1024m','--cpu-quota':'100000'}
    for i,a in enumerate(args):
        if a in limits and i+1<len(args): args[i+1]=limits[a]
    if args[0]=='run': args[1:1]=['--cpuset-cpus','0']
os.execv('/usr/bin/docker',['docker',*args])
PY
chmod +x "$W/work/capbin/docker"
if pgrep -f '^sh [^ ]*gate_blast.sh ' >/dev/null; then
    echo 'Another gate is running; retry after it finishes.' >&2
    exit 1
fi
# t31 checks for gate_blast.sh before starting its next container. Its current
# container is allowed to finish; do not overlap a gate container with it.
while /usr/bin/docker ps --format '{{.Image}}' | rg -q '^br-t31'; do
    sleep 2
done
cd "$R"
export PATH="$W/work/capbin:$PATH"
exec taskset -c 0 sh ../buildathon/bin/gate_blast.sh "$@"
