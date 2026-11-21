#!/bin/sh
# One t56 container on CPUs 8,9, 2 GiB; stop it if host memory falls below 5 GiB.
docker rm -f br-label-t56 >/dev/null 2>&1
docker run -d --name br-label-t56 --cpuset-cpus 8,9 --memory 2g --memory-swap 2g \
  -v ~/br/t56:/kit -v ~/br/t56/src:/src python:3.13-slim sh /kit/mutants/t56/run.sh > ~/br/t56/started.txt 2>&1
sleep 5
while [ "$(docker inspect br-label-t56 --format "{{.State.Status}}" 2>/dev/null)" = running ]; do
  a=$(free -g | awk "/^Mem:/ {print \$7}")
  if [ -n "$a" ] && [ "$a" -lt 5 ]; then date > ~/br/t56/memory-stop.txt; docker stop -t 3 br-label-t56 >> ~/br/t56/memory-stop.txt; exit 1; fi
  sleep 15
done
date > ~/br/t56/finished.txt
