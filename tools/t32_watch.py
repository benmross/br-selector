"""Legion-only label container watchdog and cumulative CPU recorder."""
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

class Docker(http.client.HTTPConnection):
    def __init__(self):
        super().__init__('localhost', timeout=20)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')

def query(path):
    c = Docker()
    c.request('GET', path)
    r = c.getresponse()
    data = json.loads(r.read())
    c.close()
    return data

root = Path.home() / 'br/t32'
name = sys.argv[1] if len(sys.argv) > 1 else 'br-label-t32'
with open(root / f'container-stats-{name}.jsonl', 'a', buffering=1) as out:
    while True:
        state = query(f'/containers/{name}/json')['State']
        if state.get('Status') in {'created', 'restarting'}:
            time.sleep(1)
            continue
        if not state['Running']:
            print(json.dumps({'time': time.time(), 'state': state}), file=out)
            break
        stats = query(f'/containers/{name}/stats?stream=false&one-shot=true')
        available = int(dict(line.split(':', 1) for line in open('/proc/meminfo'))['MemAvailable'].split()[0])
        print(json.dumps({'time': time.time(), 'started_at': state.get('StartedAt'),
                          'cpu_ns': stats['cpu_stats']['cpu_usage']['total_usage'],
                          'available_kib': available}), file=out)
        if available < 5 * 1024 * 1024:
            subprocess.run(['docker', 'stop', '--time', '5', name], check=True)
            print('Stopped: less than 5 GiB available', flush=True)
            break
        time.sleep(10)
