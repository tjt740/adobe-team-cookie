#!/usr/bin/env python3
"""Start the project-local Mihomo process when launching the local application."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.local/mihomo-local'
CONFIG = PRIVATE / 'config.yaml'


def start():
    os.umask(0o077)
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    controller = 'http://' + config['external-controller']
    opener = build_opener(ProxyHandler({}))

    def ready():
        try:
            request = Request(controller + '/version', headers={'Authorization': 'Bearer ' + config['secret']})
            with opener.open(request, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    if not ready():
        binary = PRIVATE / 'bin/mihomo'
        if not binary.is_file():
            raise RuntimeError('Local Mihomo binary is missing')
        # Do not use or modify the desktop Clash process/configuration.
        with (PRIVATE / 'service.log').open('ab') as log:
            process = subprocess.Popen([str(binary), '-d', str(PRIVATE)], cwd=PRIVATE,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        (PRIVATE / 'service.pid').write_text(str(process.pid))
        for _ in range(40):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError('Local proxy could not start; check its private service log')
            time.sleep(.25)
        else:
            raise RuntimeError('Local proxy startup timed out')
    return {
        'MIHOMO_CONFIG_PATH': str(CONFIG),
        'MIHOMO_RELOAD_PATH': str(CONFIG),
        'MIHOMO_CONTROL_URL': controller,
    }


if __name__ == '__main__':
    try:
        environment = os.environ.copy()
        if CONFIG.is_file():
            environment.update(start())
        if sys.argv[1:] == ['start']:
            print('Local proxy ready')
        else:
            os.chdir(ROOT / 'payload/backend')
            os.execve(sys.executable, [sys.executable, '-m', 'uvicorn', 'run_local:app',
                                      '--host', '127.0.0.1', '--port',
                                      environment.get('ADOBETEAM_PORT', '18080')], environment)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
