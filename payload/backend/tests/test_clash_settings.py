import json
import stat

import pytest

from app.services.clash import ClashError, ClashManager


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    config = tmp_path / 'config.yaml'
    config.write_text(json.dumps({
        'secret': 'controller-secret', 'authentication': ['user:proxy-password'],
        'external-controller': '0.0.0.0:9090', 'mixed-port': 7890,
        'proxy-providers': {'subscription': {'url': 'https://old.example/private-old'}},
    }))
    config.chmod(0o600)
    (tmp_path / 'providers').mkdir()
    (tmp_path / 'providers/subscription.yaml').write_bytes(b'old private node cache')
    monkeypatch.setenv('MIHOMO_CONFIG_PATH', str(config))
    monkeypatch.setenv('MIHOMO_CONTROL_URL', 'http://mihomo:9090')
    state = {'selected': 'Japan', 'nodes': ['Japan', 'Singapore'], 'fail': False, 'calls': []}

    def call(self, path, method='GET', body=None):
        state['calls'].append((path, method, body))
        if path == '/configs?force=true':
            return {}
        if path == '/proxies/ADOBE':
            if method == 'PUT':
                state['selected'] = body['name']
            return {'now': state['selected'], 'all': state['nodes']}
        if path == '/providers/proxies/subscription':
            if method == 'PUT' and state['fail']:
                (tmp_path / 'providers/subscription.yaml').write_bytes(b'bad new cache')
                raise ClashError('upstream failure')
            return {'subscriptionInfo': {'Upload': 10, 'Download': 20, 'Total': 100, 'Expire': 2000000000},
                    'proxies': [{'name': 'Japan', 'password': 'node-password'}]}
        raise AssertionError(path)

    monkeypatch.setattr(ClashManager, 'call', call)
    return config, state


def test_unconfigured_environment(client, monkeypatch):
    monkeypatch.delenv('MIHOMO_CONTROL_URL', raising=False)
    assert client.get('/api/settings/clash').json()['available'] is False


def test_status_never_returns_credentials(client, sidecar):
    response = client.get('/api/settings/clash')
    assert response.status_code == 200
    assert response.json()['used_bytes'] == 30
    assert response.json()['selected'] == 'Japan'
    for secret in ['private-old', 'controller-secret', 'proxy-password', 'node-password']:
        assert secret not in response.text


def test_update_preserves_node_and_private_config(client, sidecar):
    config, state = sidecar
    response = client.put('/api/settings/clash/subscription', json={'url': 'https://new.example/private-new'})
    assert response.status_code == 200
    saved = json.loads(config.read_text())
    assert saved['proxy-providers']['subscription']['url'] == 'https://new.example/private-new'
    assert saved['secret'] == 'controller-secret'
    assert saved['authentication'] == ['user:proxy-password']
    assert response.json()['selected'] == 'Japan'
    assert 'private-new' not in response.text
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    backups = list((config.parent / 'backups').iterdir())
    assert len(backups) == 1 and 'private-old' in backups[0].read_text()


def test_bad_subscription_rolls_back_config_cache_and_node(client, sidecar):
    config, state = sidecar
    before = config.read_bytes()
    state['fail'] = True
    response = client.put('/api/settings/clash/subscription', json={'url': 'https://bad.example/private-secret'})
    assert response.status_code == 502
    assert '已恢复' in response.json()['detail']
    assert config.read_bytes() == before
    assert (config.parent / 'providers/subscription.yaml').read_bytes() == b'old private node cache'
    assert state['selected'] == 'Japan'
    assert 'private-secret' not in response.text


def test_missing_old_node_is_reported(client, sidecar):
    _, state = sidecar
    state['nodes'] = ['Singapore']
    response = client.put('/api/settings/clash/subscription', json={'url': 'https://new.example/sub'})
    assert response.status_code == 200
    assert '原节点已不存在' in response.json()['message']


def test_active_jobs_block_proxy_changes(client, sidecar):
    from app.services.job_manager import JOBS, Job
    job = Job(1, 'external_login', {}, persist_cb=JOBS._persist_job)
    job.persist()
    for method, path, body in [('put', 'subscription', {'url': 'https://new.example/sub'}),
                               ('put', 'node', {'node': 'Singapore'}), ('post', 'refresh', None),
                               ('put', 'enabled', {'enabled': True}), ('put', 'enabled', {'enabled': False})]:
        response = getattr(client, method)('/api/settings/clash/' + path, json=body)
        assert response.status_code == 409
    assert not sidecar[1]['calls']


def test_select_validates_membership(client, sidecar):
    assert client.put('/api/settings/clash/node', json={'node': 'missing'}).status_code == 400
    assert client.put('/api/settings/clash/node', json={'node': 'Singapore'}).json()['selected'] == 'Singapore'


def test_admin_and_auth_required(client, sidecar):
    from app.main import app
    from app.api.deps import get_current_user
    from app.models.user import User
    app.dependency_overrides[get_current_user] = lambda: User(id=2, is_active=True, is_superuser=False)
    assert client.get('/api/settings/clash').status_code == 403
    assert client.post('/api/settings/clash/refresh').status_code == 403
    assert client.put('/api/settings/clash/enabled', json={'enabled': False}).status_code == 403
    del app.dependency_overrides[get_current_user]
    assert client.get('/api/settings/clash').status_code == 401


def test_invalid_urls_and_payloads_do_not_leak_input(client, sidecar):
    for value in ['http://example.com/private-secret', 'https://user:private-secret@example.com/',
                  'https://[invalid/private-secret', {'private-secret': 'nested'}]:
        response = client.put('/api/settings/clash/subscription', json={'url': value})
        assert response.status_code in (400, 422)
        assert 'private-secret' not in response.text


def test_concurrent_operation_is_rejected(sidecar):
    with ClashManager().lock():
        with pytest.raises(ClashError) as error:
            ClashManager().select('Singapore', lambda: None)
    assert error.value.status == 409


def test_local_reload_uses_local_configuration_path(sidecar, monkeypatch):
    config, state = sidecar
    monkeypatch.setenv('MIHOMO_RELOAD_PATH', str(config))
    ClashManager().reload()
    assert state['calls'][-1] == ('/configs?force=true', 'PUT', {'path': str(config)})


def test_environment_proxy_is_reported_without_credentials(client, monkeypatch):
    from app.api.routes import clash
    monkeypatch.delenv('MIHOMO_CONTROL_URL', raising=False)
    monkeypatch.setattr(clash, 'get_environ_proxies', lambda url: {'https': 'http://user:private-secret@127.0.0.1:7890'})
    response = client.get('/api/settings/clash')
    assert response.json()['proxy_source'] == 'environment'
    assert response.json()['proxy_endpoint'] == '127.0.0.1:7890'
    assert 'private-secret' not in response.text


def test_enable_disable_retains_subscription_and_endpoint(client, sidecar):
    config, state = sidecar
    before = config.read_bytes()
    enabled = client.put('/api/settings/clash/enabled', json={'enabled': True})
    assert enabled.status_code == 200
    assert enabled.json()['clash_enabled'] is True
    assert enabled.json()['proxy_endpoint'] == 'mihomo:7890'
    assert 'proxy-password' not in enabled.text
    assert client.get('/api/settings').json()['proxy_url'] == 'http://user:proxy-password@mihomo:7890'
    state['calls'].clear()
    disabled = client.put('/api/settings/clash/enabled', json={'enabled': False})
    assert disabled.status_code == 200
    assert disabled.json()['proxy_enabled'] is False
    assert not state['calls']  # Off works without contacting the sidecar.
    assert client.get('/api/settings').json()['proxy_url'] == 'http://user:proxy-password@mihomo:7890'
    assert config.read_bytes() == before
    assert client.put('/api/settings/clash/enabled', json={'enabled': True}).json()['selected'] == 'Japan'


def test_controller_failure_can_be_disabled_but_not_enabled(client, sidecar, monkeypatch):
    client.put('/api/settings/clash/enabled', json={'enabled': True})
    def fail(*args, **kwargs):
        raise ClashError('offline')
    monkeypatch.setattr(ClashManager, 'call', fail)
    status = client.get('/api/settings/clash')
    assert status.status_code == 200 and status.json()['connected'] is False
    assert status.json()['clash_enabled'] is True
    assert client.put('/api/settings/clash/enabled', json={'enabled': False}).status_code == 200
    assert client.put('/api/settings/clash/enabled', json={'enabled': True}).status_code == 502
    assert client.get('/api/settings').json()['proxy_enabled'] is False


def test_enable_requires_valid_config_and_boolean(client, sidecar):
    config, _ = sidecar
    for value in ['false', 0, None]:
        assert client.put('/api/settings/clash/enabled', json={'enabled': value}).status_code == 422
    config.write_text('{}')
    assert client.put('/api/settings/clash/enabled', json={'enabled': True}).status_code == 503
    assert client.put('/api/settings/clash/enabled', json={'enabled': False}).status_code == 200


def test_enable_uses_local_endpoint_and_escapes_auth(client, sidecar, monkeypatch):
    config, _ = sidecar
    value = json.loads(config.read_text())
    value.update({'mixed-port': 17890, 'authentication': ['user:p@ss:word']})
    config.write_text(json.dumps(value))
    monkeypatch.setenv('MIHOMO_CONTROL_URL', 'http://127.0.0.1:19090')
    assert client.put('/api/settings/clash/enabled', json={'enabled': True}).json()['proxy_endpoint'] == '127.0.0.1:17890'
    assert client.get('/api/settings').json()['proxy_url'] == 'http://user:p%40ss%3Aword@127.0.0.1:17890'
