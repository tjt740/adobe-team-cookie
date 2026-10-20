#!/usr/bin/env python3
"""One-command incremental release; standard library only, no application credentials."""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPERS = ('incremental_remote.py', 'profile-invitation-release.py')
HOST = 'root@173.234.15.150'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def source_path(name):
    """Use the same small allowlist on both sides of the SSH connection."""
    path = PurePosixPath(name)
    if not re.fullmatch(r'[A-Za-z0-9_./@-]+', name) or path.as_posix() != name or path.is_absolute() or any(p.startswith('.') for p in path.parts):
        raise ValueError('Invalid source path: ' + name)
    if name.startswith('frontend-v2/') and path.suffix in ('.js', '.css', '.html') and '/tests/' not in name:
        return 'frontend'
    if name.startswith('backend/app/') and path.suffix == '.py' and not name.startswith(('backend/app/db/', 'backend/app/models/')):
        return 'backend'
    raise ValueError('Requires the dedicated dependency/configuration/migration release: ' + name)


def blob(ref, path):
    result = subprocess.run(['git', 'cat-file', '-e', ref + ':' + path], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        return None
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)


def collect(base, target):
    base, target = git('rev-parse', base + '^{commit}'), git('rev-parse', target + '^{commit}')
    changes = git('diff', '--name-status', '--no-renames', base, target).splitlines()
    files, contents, ignored = {}, {}, []
    for line in changes:
        status, path = line.split('\t', 1)
        if path.startswith(('payload/backend/tests/', 'payload/frontend-v2/tests/')):
            ignored.append(path)
            continue
        if not path.startswith('payload/'):
            if path == 'Dockerfile' or path.startswith('compose.'):
                raise ValueError('Container/dependency changes require a dedicated release: ' + path)
            ignored.append(path)
            continue
        name = path.removeprefix('payload/')
        source_path(name)
        if status not in ('A', 'M'):
            raise ValueError('File deletion/type change requires a dedicated release: ' + path)
        old, new = blob(base, path), blob(target, path)
        if git('ls-tree', target, '--', path).split()[0] not in ('100644', '100755'):
            raise ValueError('Release source must be a regular file: ' + path)
        assert new is not None
        files[name] = {'before': hashlib.sha256(old).hexdigest() if old is not None else None,
                       'after': hashlib.sha256(new).hexdigest()}
        contents['payload/' + name] = new
    return {'base': base, 'commit': target, 'files': files, 'ignored': ignored}, contents


class SSHSession:
    """Detach the master explicitly so captured stdout cannot keep it alive."""
    def __init__(self, identity, host=HOST):
        self.host = host
        self.temp = tempfile.TemporaryDirectory(prefix='okad-ssh-', dir='/tmp')
        self.socket = str(Path(self.temp.name) / 's')
        self.base = ['ssh', '-T', '-i', str(Path(identity).expanduser()), '-o', 'IdentitiesOnly=yes',
                     '-o', 'BatchMode=yes', '-o', 'IdentityAgent=none', '-o', 'ConnectTimeout=15',
                     '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=3',
                     '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'Ciphers=aes128-gcm@openssh.com',
                     '-o', 'IPQoS=none', '-o', 'ControlPath=' + self.socket]

    def __enter__(self):
        try:
            with tempfile.TemporaryFile() as error:
                for attempt in range(2):
                    error.seek(0); error.truncate()
                    try:
                        subprocess.run(self.base + ['-M', '-N', '-f', '-o', 'ControlPersist=120', self.host],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=error, check=True, timeout=25)
                        return self
                    except (subprocess.SubprocessError, OSError):
                        # A fork may have finished just as the parent timed out.
                        check = subprocess.run(self.base + ['-O', 'check', self.host],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                        if check.returncode == 0:
                            return self
                        if attempt:
                            error.seek(0)
                            raise RuntimeError('SSH connection failed: ' + error.read().decode(errors='replace')[-800:])
        except BaseException:
            self.close()
            raise

    def command(self, code):
        return self.base + ['-o', 'ControlMaster=no', self.host, 'python3 -c ' + shlex.quote(code)]

    def query(self, code, data):
        return json.loads(subprocess.check_output(self.command(code), input=json.dumps(data).encode(), timeout=45))

    def upload_run(self, bundle, log):
        # One SSH channel replaces mkdir + scp + extraction + deploy + result download.
        with tempfile.TemporaryFile() as incoming, log.open('w') as output:
            incoming.write(bundle); incoming.seek(0)
            proc = subprocess.Popen(self.command(BOOTSTRAP), stdin=incoming, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            lines = []
            def relay():
                for line in proc.stdout:
                    lines.append(line)
                    print(line, end='', flush=True)
                    output.write(line); output.flush()
            reader = threading.Thread(target=relay, daemon=True)
            reader.start()
            try:
                status = proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                proc.terminate(); proc.wait(timeout=10)
                raise RuntimeError('Release connection timed out; inspect the remote audit before retrying')
            finally:
                reader.join(timeout=10)
            results = [json.loads(s.removeprefix('RELEASE_RESULT ')) for s in lines if s.startswith('RELEASE_RESULT ')]
            if status or not results:
                raise RuntimeError('Release failed; inspect deploy.log and remote audit before retrying')
            return results[-1]

    def close(self):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(self.base + ['-O', 'exit', self.host], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5)
        self.temp.cleanup()

    def __exit__(self, *_):
        self.close()


# Query mode loads the helper in memory and performs no remote filesystem writes.
QUERY = """import json,sys,types
p=json.load(sys.stdin)
m=types.ModuleType('incremental_remote');m.__file__='/opt/adobe-team-cookie/.local/query/incremental_remote.py'
exec(compile(p['helper'],m.__file__,'exec'),m.__dict__)
core=types.ModuleType('guarded_core');core.__file__=m.__file__
exec(compile(p['core'],core.__file__,'exec'),core.__dict__)
print(json.dumps(m.probe(core,p.get('manifest')),ensure_ascii=False))
"""

BOOTSTRAP = """import io,json,os,pathlib,re,runpy,sys,tarfile,time,traceback
os.umask(0o077)
data=sys.stdin.buffer.read(16*1024*1024+1)
assert len(data)<=16*1024*1024,'Bundle too large for source-only release'
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
 members=[];total=0
 for m in tar:
  total+=m.size
  assert m.isfile() and m.size<=16*1024*1024 and total<=64*1024*1024 and len(members)<2000
  members.append(m)
 names=[m.name for m in members]
 assert len(names)==len(set(names))
 manifest=json.load(tar.extractfile('manifest.json'))
 assert re.fullmatch(r'[a-z0-9-]{1,100}',manifest['release'])
 expected={'manifest.json','incremental_remote.py','profile-invitation-release.py'}|{'payload/'+n for n in manifest['files']}
 assert set(names)==expected
 for name in names:
  p=pathlib.PurePosixPath(name)
  assert not p.is_absolute() and p.as_posix()==name and all(not part.startswith('.') for part in p.parts)
 stage=pathlib.Path('/opt/adobe-team-cookie/.local/releases')/manifest['release']
 stage.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 stage.mkdir(mode=0o700)
 for member in members:
  path=stage/member.name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  path.write_bytes(tar.extractfile(member).read())
 (stage/'.dockerignore').write_text('*\\n!payload/\\n!payload/**\\n!Dockerfile\\n')
# Keep the release alive if the SSH transport disappears during a switch.
pid=os.fork()
if pid==0:
 os.setsid()
 (stage/'worker.pid').write_text(str(os.getpid()))
 fd=os.open(stage/'deploy.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
 sys.stdout.reconfigure(line_buffering=True);sys.stderr.reconfigure(line_buffering=True)
 status=0
 try:
  sys.argv=[str(stage/'incremental_remote.py'),'deploy']
  runpy.run_path(sys.argv[0],run_name='__main__')
 except BaseException:
  traceback.print_exc();status=1
 finally:
  sys.stdout.flush();sys.stderr.flush()
  (stage/'exit-code.tmp').write_text(str(status));os.replace(stage/'exit-code.tmp',stage/'exit-code')
 os._exit(status)
position=0
while True:
 if (stage/'deploy.log').exists():
  with (stage/'deploy.log').open('rb') as log:
   log.seek(position);chunk=log.read();position=log.tell()
  if chunk:
   try:sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
   except BrokenPipeError:os._exit(1)
 if (stage/'exit-code').exists():
  # Read the final bytes written before the exit marker.
  if (stage/'deploy.log').stat().st_size>position:continue
  sys.exit(int((stage/'exit-code').read_text()))
 time.sleep(.1)
"""


def package(manifest, contents, helpers):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w:gz') as tar:
        for name, data in {**contents, **helpers, 'manifest.json': json.dumps(manifest).encode()}.items():
            item = tarfile.TarInfo(name); item.size = len(data); item.mode = 0o600
            tar.addfile(item, io.BytesIO(data))
    return archive.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('probe', 'plan', 'deploy'))
    parser.add_argument('--base', help='Exact source commit from the last release; required for plan/deploy')
    parser.add_argument('--target', default='HEAD')
    parser.add_argument('--identity', default=os.environ.get('OKAD_SSH_IDENTITY', '~/.ssh/adobe_primary_ci'))
    parser.add_argument('--samples', type=int, choices=range(1, 6), default=1, help='Read-only probe samples on one connection')
    args = parser.parse_args()
    os.umask(0o077)
    started = time.monotonic()
    helpers = {name: (HERE / name).read_bytes() for name in HELPERS}
    manifest, contents = None, {}
    if args.action != 'probe':
        if not args.base:
            parser.error('--base must identify the last deployed source commit')
        manifest, contents = collect(args.base, args.target)
        if not manifest['files']:
            print(json.dumps({'status': 'no_application_changes', 'ignored': manifest['ignored']}))
            return
    if args.action == 'deploy':
        if git('status', '--porcelain'):
            parser.error('Commit changes or use a clean worktree before deployment')
        branch = git('branch', '--show-current')
        remote = git('ls-remote', '--heads', 'origin', 'refs/heads/' + branch).split() if branch else []
        if not remote or remote[0] != manifest['commit']:
            parser.error('Push this exact commit before deployment')
        for name, data in helpers.items():
            if data != blob(manifest['commit'], 'deploy/primary/' + name):
                parser.error('Release helpers must match the deployed commit')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S').lower()
        manifest['release'] = 'source-' + stamp + '-' + manifest['commit'][:12]
    prepared = time.monotonic()
    with SSHSession(args.identity) as ssh:
        connected = time.monotonic()
        query = {'helper': helpers['incremental_remote.py'].decode(), 'core': helpers['profile-invitation-release.py'].decode(), 'manifest': manifest}
        if args.action in ('probe', 'plan'):
            reports = []
            for _ in range(args.samples):
                begin = time.monotonic(); report = ssh.query(QUERY, query)
                report['round_trip_seconds'] = round(time.monotonic() - begin, 3); reports.append(report)
            print(json.dumps({'local_prepare_seconds': round(prepared-started, 3),
                              'connect_seconds': round(connected-prepared, 3), 'samples': reports,
                              'total_seconds': round(time.monotonic()-started, 3)}, ensure_ascii=False, indent=2))
            return
        audit = ROOT / '.local' / 'releases' / manifest['release']
        audit.mkdir(parents=True, mode=0o700)
        bundle = package(manifest, contents, helpers)
        print(json.dumps({'files': len(manifest['files']), 'bundle_bytes': len(bundle),
                          'release': manifest['release'], 'local_audit': str(audit),
                          'connect_seconds': round(connected-prepared, 3)}), flush=True)
        (audit/'manifest.json').write_text(json.dumps(manifest, indent=2))
        transferring = time.monotonic()
        result = ssh.upload_run(bundle, audit/'deploy.log')
        result.update(total_seconds=round(time.monotonic()-started, 3), bundle_bytes=len(bundle),
                      local_prepare_seconds=round(prepared-started, 3),
                      connect_seconds=round(connected-prepared, 3),
                      transfer_and_release_seconds=round(time.monotonic()-transferring, 3))
        (audit/'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
