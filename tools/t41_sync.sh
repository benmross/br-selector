#!/bin/sh
# Pull t41 labels from the Legion, refresh the matrix, print a short status.
cd "$(dirname "$0")/.." || exit 1
for i in 1 2 3; do
    rsync -a --timeout=40 legion:br/t41/mutants/t41/answers.json legion:br/t41/mutants/t41/answers.json.baseline mutants/t41/ \
        && rsync -a --timeout=40 legion:br/t41/mutants/t41/answers.json.logs/ work/t41-label-logs/ && break
    echo "rsync failed, retry $i"; sleep 20
done
timeout 30 ssh legion 'docker ps --format "{{.Names}} {{.Status}}" | grep t41; docker logs --tail 2 br-label-t41 2>&1 | grep -v notice; free -g | awk "/^Mem:/{print \"avail\", \$7}"; cat ~/br/t41/watch.log'
python3 tools/t41_report.py | tail -9
grep MISS reviews/t41-matrix.md | cut -c1-260
