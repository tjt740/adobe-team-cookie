"""Large batch histories must remain cheap to poll and compact to transfer."""
import json

from app.models.external_member import ExternalMember
from app.services.job_manager import JOBS, Job


def test_large_batch_history_is_ranked_before_decoding_summaries(client, db, engine):
    members = [ExternalMember(email=f'cost{i}@example.test') for i in range(240)]
    db.add_all(members)
    db.commit()
    ids = [member.id for member in members]
    for jid in range(1, 25):
        job = Job(jid, 'external_login', {'member_ids': ids, 'operator': 'tester'})
        job.extra = {'batch': {'index': 1, 'total': 1, 'size': len(ids)},
                     'items': [{'id': mid, 'status': 'done', 'message': f'account {mid}',
                                'private': 'never-return-this'} for mid in ids]}
        job.logs = ['private log ' + 'x' * 100 for _ in range(100)]
        job.status = 'done'
        JOBS._persist_job(job)
    # Bound VM work instead of using a machine-dependent wall clock. The old
    # per-account scan through every historical batch exceeds this 2M budget.
    calls = [0]
    def budget():
        calls[0] += 1
        return int(calls[0] > 2000)
    with engine.connect() as conn:
        raw = conn.connection.driver_connection
        raw.set_progress_handler(budget, 1000)
        try:
            result = JOBS.external_member_jobs(ids)
        finally:
            raw.set_progress_handler(None, 0)
    assert len(result) == len(ids)
    for mid, jobs in result.items():
        assert len(jobs) == 1 and jobs[0]['id'] == 24
        assert jobs[0]['item_status'] == 'done'
        assert jobs[0]['item_message'] == f'account {mid}'
        assert jobs[0]['log_total'] == 100 and jobs[0]['logs'] == []
        assert jobs[0]['extra'] == {'batch': {'index': 1, 'total': 1, 'size': len(ids)}}
    assert 'private' not in json.dumps(result)
    assert [job['id'] for job in JOBS.external_member_jobs([ids[0]], limit=3)[ids[0]]] == [24, 23, 22]


def test_large_external_list_supports_gzip_and_identity(client, db):
    db.add_all(ExternalMember(email=f'compress{i}@example.test', note='n' * 200) for i in range(30))
    db.commit()
    compressed = client.get('/api/external/members?size=30', headers={'Accept-Encoding': 'gzip'})
    plain = client.get('/api/external/members?size=30', headers={'Accept-Encoding': 'identity'})
    assert compressed.status_code == plain.status_code == 200
    assert compressed.headers['Content-Encoding'] == 'gzip'
    assert 'accept-encoding' in compressed.headers['Vary'].lower()
    assert 'Content-Encoding' not in plain.headers
    assert compressed.json() == plain.json()
    assert int(compressed.headers['Content-Length']) < len(plain.content) / 4
    assert 'Content-Encoding' not in client.get('/api/health').headers
