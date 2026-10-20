"""Release the HTTP identity correction with the existing primary-host guards.

Keep this beside profile-invitation-release.py, manifest.json and payload/.
The shared release preserves live runtime overlays, configuration and data,
requires idle login work, and retains a guarded code-only rollback.
"""
import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location(
    "guarded_okad_release", Path(__file__).with_name("profile-invitation-release.py")
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
release.FILES = (
    "backend/app/services/adobe_protocol/http_client.py",
    "backend/app/services/firefly.py",
)
original_hashes = release.hashes


def checked_hashes(image=None):
    result = original_hashes(image)
    if image:
        release.run([
            "docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image,
            "-c", "from app.services.adobe_protocol.http_client import HttpClient,IMPERSONATE_TARGET;"
            "c=HttpClient();major=IMPERSONATE_TARGET.removeprefix('chrome');h=c._base_headers();"
            "assert 'Chrome/'+major+'.0.0.0' in h['User-Agent'];"
            "assert '\"Chromium\";v=\"'+major+'\"' in h['sec-ch-ua'];"
            "assert '\"Google Chrome\";v=\"'+major+'\"' in h['sec-ch-ua'];"
            "c.close();from types import SimpleNamespace;from app.services import firefly;"
            "e={};s=SimpleNamespace(get=lambda *a,**kw:SimpleNamespace(status_code=401,json=lambda:{'error_code':'401013'}));"
            "assert firefly.fetch_credits_detail('synthetic','synthetic',session=s,error_out=e) is None;"
            "assert e.get('http_status')==401;"
            "print('CANDIDATE_HTTP_IDENTITY_AND_SESSION_VALIDATION_OK')",
        ])
    return result


release.hashes = checked_hashes

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action not in ("deploy", "check-rollback", "rollback"):
        raise SystemExit("Usage: http-identity-release.py deploy|check-rollback|rollback")
    release.main(action)
