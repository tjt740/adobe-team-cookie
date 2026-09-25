"""Limited, authenticated administration of the private Mihomo sidecar.

Only the subscription URL and selected node are editable. The browser never
receives the subscription, node credentials, controller secret or config file.
"""
from contextlib import contextmanager
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote, urlsplit
import uuid

import requests


class ClashError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class ClashManager:
    def __init__(self):
        self.path = Path(os.environ.get("MIHOMO_CONFIG_PATH", "/nonexistent/mihomo/config.yaml"))
        self.controller = os.environ.get("MIHOMO_CONTROL_URL", "").rstrip("/")
        self.reload_path = os.environ.get("MIHOMO_RELOAD_PATH", "/config/config.yaml")

    @property
    def available(self):
        return bool(self.controller and self.path.is_file())

    def config(self):
        if not self.available:
            raise ClashError("当前环境尚未接入 Clash 订阅服务", 503)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ClashError("无法读取代理配置，请检查代理服务") from None

    def proxy_url(self):
        """Build the application's endpoint from this environment's private config."""
        config = self.config()
        try:
            host = urlsplit(self.controller).hostname
            port = int(config["mixed-port"])
            username, password = config["authentication"][0].split(":", 1)
            if not host or not 0 < port < 65536 or not username or not password:
                raise ValueError()
            if ":" in host:
                host = "[" + host + "]"
            return f"http://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}"
        except (KeyError, IndexError, TypeError, ValueError):
            raise ClashError("项目代理地址配置不完整，请检查代理服务", 503) from None

    def snapshot(self):
        # Keep the off switch accessible even when the controller is unavailable.
        try:
            return self.status()
        except ClashError:
            return {"available": self.available, "connected": False,
                    "message": "代理服务暂不可用，仍可关闭代理恢复本机网络"}

    def call(self, path, method="GET", body=None):
        config = self.config()
        try:
            # Never send the controller through the application's upstream proxy.
            with requests.Session() as session:
                session.trust_env = False
                response = session.request(
                    method, self.controller + path, json=body,
                    headers={"Authorization": "Bearer " + config["secret"]},
                    timeout=(5, 50),
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except (requests.RequestException, ValueError, KeyError):
            # Upstream error messages can contain the private subscription URL.
            raise ClashError("代理服务请求失败，请检查订阅是否有效或稍后重试") from None

    @contextmanager
    def lock(self):
        self.config()
        with (self.path.parent / ".management.lock").open("a") as lock:
            os.fchmod(lock.fileno(), 0o600)
            if os.geteuid() == 0:
                owner = self.path.stat()
                os.fchown(lock.fileno(), owner.st_uid, owner.st_gid)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ClashError("另一项代理操作正在进行，请稍后重试", 409) from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def write(self, path, content):
        """Atomic private writes readable by the non-root Mihomo container."""
        owner = self.path.stat()
        fd, temporary = tempfile.mkstemp(prefix=".clash-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
                if os.geteuid() == 0:
                    os.fchown(stream.fileno(), owner.st_uid, owner.st_gid)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def reload(self):
        self.call("/configs?force=true", "PUT", {"path": self.reload_path})

    def status(self):
        if not self.available:
            return {"available": False}
        group = self.call("/proxies/ADOBE")
        provider = self.call("/providers/proxies/subscription")
        quota = provider.get("subscriptionInfo") or {}
        return {
            "available": True,
            "connected": True,
            "selected": group.get("now", ""),
            "nodes": group.get("all", []),
            "updated_at": provider.get("updatedAt"),
            "used_bytes": quota.get("Upload", 0) + quota.get("Download", 0),
            "total_bytes": quota.get("Total", 0),
            "expires_at": quota.get("Expire", 0),
        }

    def select(self, node, ensure_idle):
        with self.lock():
            ensure_idle()
            if node not in self.call("/proxies/ADOBE").get("all", []):
                raise ClashError("节点已不存在，请更新节点列表后重新选择", 400)
            self.call("/proxies/ADOBE", "PUT", {"name": node})
            return self.status()

    def refresh(self, ensure_idle):
        with self.lock():
            ensure_idle()
            self.call("/providers/proxies/subscription", "PUT")
            return self.status()

    def update(self, url, ensure_idle):
        url = url.strip()
        try:
            parsed = urlsplit(url)
            valid = (len(url) <= 8192 and parsed.scheme == "https" and parsed.hostname
                     and not parsed.username and not parsed.password and not parsed.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise ClashError("请填写完整的 HTTPS Clash 订阅链接", 400)
        with self.lock():
            ensure_idle()
            old = self.config()
            previous = self.call("/proxies/ADOBE").get("now")
            old_bytes = self.path.read_bytes()
            provider_path = self.path.parent / "providers/subscription.yaml"
            cache = provider_path.read_bytes() if provider_path.exists() else None
            backups = self.path.parent / "backups"
            backups.mkdir(mode=0o700, exist_ok=True)
            if os.geteuid() == 0:
                owner = self.path.stat()
                os.chown(backups, owner.st_uid, owner.st_gid)
            self.write(backups / ("web-" + uuid.uuid4().hex + ".json"), old_bytes)
            candidate = copy.deepcopy(old)
            candidate["proxy-providers"]["subscription"]["url"] = url
            self.write(self.path, json.dumps(candidate, ensure_ascii=False, indent=2).encode())
            try:
                self.reload()
                # Force a fetch: a cached provider must not mask an invalid URL.
                self.call("/providers/proxies/subscription", "PUT")
                names = self.call("/proxies/ADOBE").get("all", [])
                if not names:
                    raise ClashError("新订阅没有可用节点")
                if previous in names:
                    self.call("/proxies/ADOBE", "PUT", {"name": previous})
                result = self.status()
                result["message"] = ("订阅已更新，继续使用原节点" if previous in names else
                                     "订阅已更新，原节点已不存在，请选择并验证新的节点")
                return result
            except Exception:
                self.write(self.path, old_bytes)
                if cache is not None:
                    self.write(provider_path, cache)
                try:
                    self.reload()
                    if previous:
                        self.call("/proxies/ADOBE", "PUT", {"name": previous})
                except Exception:
                    raise ClashError("更新失败，旧配置已恢复，但代理服务暂不可用，请检查服务") from None
                raise ClashError("订阅更新失败，已恢复原订阅和节点，请检查链接") from None
