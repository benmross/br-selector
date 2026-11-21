#!/bin/sh
# Host-side guard: stop the label container when Legion has <5 GiB available.
while [ "$(docker inspect br-label-t30 --format '{{.State.Status}}' 2>/dev/null)" = running ]; do
    available=$(free -g | awk '/^Mem:/ {print $7}')
    if [ -n "$available" ] && [ "$available" -lt 5 ]; then
        date -u > "$HOME/br/t30/memory-stop.txt"
        free -g >> "$HOME/br/t30/memory-stop.txt"
        docker stop -t 3 br-label-t30 >> "$HOME/br/t30/memory-stop.txt"
        exit 1
    fi
    sleep 15
done
