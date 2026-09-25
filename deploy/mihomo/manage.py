#!/usr/bin/env python3
"""Manage the private Mihomo sidecar on the deployment host (Python 3.6+)."""
import argparse
import datetime
import fcntl
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.local' / 'mihomo'
CONFIG = PRIVATE / 'config.yaml'
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'deploy/mihomo/compose.yml')]
CONTROL = r'''
import json,sys,urllib.request,urllib.error
from pathlib import Path
cfg=json.loads(Path('/config/config.yaml').read_text(encoding='utf-8'))
req=json.load(sys.stdin)
body=json.dumps(req['body']).encode() if req.get('body') is not None else None
request=urllib.request.Request('http://127.0.0.1:9090'+req['path'],data=body,method=req['method'],headers={'Authorization':'Bearer '+cfg['secret'],'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(request,timeout=50) as response:
  raw=response.read()
  print(json.dumps(json.loads(raw) if raw else {}))
except urllib.error.HTTPError as e:
 print(json.dumps({'control_error':e.code}));sys.exit(1)
except Exception:
 print(json.dumps({'control_error':'unavailable'}));sys.exit(1)
'''


def call(path, method='GET', body=None):
    result = subprocess.run(COMPOSE + ['exec', '-T', 'mihomo', 'python', '-c', CONTROL],
                            input=json.dumps({'path':path,'method':method,'body':body}),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if result.returncode:
        raise RuntimeError('Mihomo control request failed; check sidecar status or subscription availability')
    return json.loads(result.stdout)


def write_config(config):
    os.umask(0o077)
    pending = CONFIG.with_suffix('.pending')
    pending.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.chmod(0o600)
    os.replace(str(pending), str(CONFIG))


def restart():
    subprocess.run(COMPOSE + ['restart', 'mihomo'], check=True, stdout=subprocess.DEVNULL)
    for _ in range(20):
        try:
            call('/version')
            return
        except RuntimeError:
            time.sleep(1)
    raise RuntimeError('Mihomo did not become ready')


def status():
    group = call('/proxies/ADOBE')
    provider = call('/providers/proxies/subscription')
    print('Selected node: ' + str(group.get('now', '')))
    print('Nodes: ' + str(len(provider.get('proxies', []))))
    print('Provider updated: ' + str(provider.get('updatedAt', '')))
    quota = provider.get('subscriptionInfo') or {}
    if quota:
        used = quota.get('Upload', 0) + quota.get('Download', 0)
        total = quota.get('Total', 0)
        print('Traffic: {:.2f} / {:.2f} GiB used'.format(used / 2**30, total / 2**30))
        if quota.get('Expire'):
            expires = datetime.datetime.utcfromtimestamp(quota['Expire']).isoformat() + 'Z'
            print('Expires (UTC): ' + expires)


def update_subscription():
    url = getpass.getpass('New Clash subscription URL (hidden): ').strip()
    if urlsplit(url).scheme != 'https' or not urlsplit(url).hostname:
        raise RuntimeError('An HTTPS subscription URL is required')
    old = json.loads(CONFIG.read_text(encoding='utf-8'))
    candidate = json.loads(json.dumps(old))
    candidate['proxy-providers']['subscription']['url'] = url
    previous_node = call('/proxies/ADOBE').get('now')
    backups = PRIVATE / 'backups'
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backups / ('config-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    backup.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8'); backup.chmod(0o600)
    write_config(candidate)
    try:
        # Parse the new configuration before restarting. Capture output to avoid leaking URLs.
        result = subprocess.run(COMPOSE + ['exec','-T','mihomo','/usr/local/bin/mihomo','-t','-d','/config'],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Configuration validation failed')
        restart()
        call('/providers/proxies/subscription', 'PUT')
        names = call('/proxies/ADOBE').get('all', [])
        if not names:
            raise RuntimeError('The new subscription returned no usable nodes')
        if previous_node in names:
            call('/proxies/ADOBE', 'PUT', {'name':previous_node})
        else:
            print('Previous node is absent. Select and verify a replacement before starting new login jobs.')
        print('Subscription updated; application proxy address is unchanged.')
        status()
    except Exception:
        write_config(old)
        restart()
        call('/providers/proxies/subscription', 'PUT')
        if previous_node:
            call('/proxies/ADOBE', 'PUT', {'name':previous_node})
        raise RuntimeError('Update failed; previous subscription configuration restored')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status','nodes','select','refresh','update-subscription'])
    parser.add_argument('node', nargs='?')
    args = parser.parse_args()
    if args.command == 'status':
        status()
    elif args.command == 'nodes':
        for name in call('/proxies/ADOBE').get('all', []):
            print(name)
    elif args.command == 'select':
        if not args.node or args.node not in call('/proxies/ADOBE').get('all', []):
            raise RuntimeError('Choose an exact node name from the nodes command')
        call('/proxies/ADOBE', 'PUT', {'name':args.node}); status()
    elif args.command == 'refresh':
        call('/providers/proxies/subscription', 'PUT'); status()
    else:
        update_subscription()

if __name__ == '__main__':
    try:
        # Serialize terminal operations with settings-page changes.
        with (PRIVATE / '.management.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Another proxy operation is in progress; retry later')
            main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        sys.exit(1)
