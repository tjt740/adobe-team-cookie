import json
import time
from concurrent.futures import ThreadPoolExecutor
from app.models.adobe_member import AdobeMember
from app.services import pool_login
from app.services.job_manager import JOBS, Job
from app.services.job_provenance import request_context


def finish(job):
    job.bump(success=job.target)


def wait(job):
    end = time.monotonic() + 2
    while not job.finished_at and time.monotonic() < end:
        time.sleep(.01)
    assert job.finished_at


def test_filter_origin_operator_accounts_and_retry_survive_restart(client, db, monkeypatch):
    member = AdobeMember(admin_id=0, email='snapshot@example.com', is_imported=True,
                         registered=True, credits=4000, refresh_token='never-expose', cookie='private-cookie')
    db.add(member); db.commit()
    monkeypatch.setattr(pool_login, 'pool_login_batch_worker', finish)
    response = client.post('/api/pool/batch-login-filter', json={
        'pool_type': 'all', 'has_token': None, 'keyword': 'snapshot', 'credit_value': 4000,
        'export_status': 'unexported', 'operator': 'forged-user', 'admin_token': 'private-key'})
    assert response.status_code == 200, response.text
    job_id = response.json()['id']; job = JOBS.get(job_id); wait(job)
    t = client.get(f'/api/adobe-accounts/jobs/{job_id}').json()['trace']
    assert t['operator'] == 'tester'
    assert t['source'] == {'label':'号池管理','path':'/pool','action':'登录筛选结果','recorded':True}
    assert t['accounts'] == [{'id':member.id,'email':'snapshot@example.com','kind':'pool'}]
    assert t['filters']['export_status'] == 'unexported' and t['filters']['has_token'] is None
    assert all(secret not in json.dumps(t) for secret in ('never-expose','private-cookie','private-key','forged-user'))
    member.email='changed@example.com';db.commit();JOBS._jobs.clear()
    assert client.get(f'/api/adobe-accounts/jobs/{job_id}').json()['trace'] == t
    retry=client.post(f'/api/pool/batch-login-retry/{job_id}').json()
    wait(JOBS.get(retry['id']))
    assert retry['trace']['retry_from_job'] == job_id
    assert retry['trace']['source']['label'] == '任务列表'
    assert request_context.get() is None
    listed=client.get('/api/adobe-accounts/jobs').json()
    assert all('trace' in row and not row['logs'] for row in listed)


def test_old_job_does_not_invent_an_operator_or_resolve_reused_account_id():
    job=Job(5,'pool_login',{'member_ids':[3], 'target':1})
    t=job.to_dict()['trace']
    assert t['accounts']==[{'id':3,'email':'','kind':'pool'}]
    assert t['operator']=='' and t['source']['recorded'] is False
    assert t['source']['label']=='号池管理'


def test_old_push_job_uses_recorded_result_email_and_destination():
    job=Job(9,'pool_cookie_sub2',{'member_ids':[2], 'sub2_url':'http://sub2.test/api/v1','group_ids':[7]})
    job.set_extra('items',[{'id':2,'email':'original@example.com','status':'existing'}])
    t=job.to_dict()['trace']
    assert t['accounts'][0]['email']=='original@example.com'
    assert t['destination']['group_ids']==[7]
    assert t['source']['recorded'] is False


def test_concurrent_account_results_do_not_overwrite_each_other():
    job=Job(1,'external_login',{'member_ids':list(range(1,51))})
    def update(i):
        job.record_item(i,status='running',email=f'a{i}@example.com')
        job.record_item(i,status='done',message='登录成功')
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update,range(1,51)))
    assert len(job.extra['items'])==50
    assert all(row['status']=='done' for row in job.extra['items'])
