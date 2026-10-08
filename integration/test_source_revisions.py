"""Authorized revisions are explicit hashes, never an exemption for whole directories."""
import hashlib,json
import pytest
from integration.verify_sources import check_sources


def digest(value): return hashlib.sha256(value).hexdigest()

@pytest.fixture
def fixture(tmp_path):
    (tmp_path/'integration/validation/reliability').mkdir(parents=True)
    (tmp_path/'integration/validation/reliability/source-revisions.xml').write_text('<testsuite tests="1"/>',encoding='utf-8')
    source=tmp_path/'backend/app.py';source.parent.mkdir();source.write_bytes(b'fixed\n')
    historical={'springboot':{'root':'.','files':{'backend/app.py':digest(b'original\n')},'normalized_files':{'backend/app.py':digest(b'original\n')}}}
    baseline=json.dumps(historical).encode()
    (tmp_path/'integration/source-snapshots.json').write_bytes(baseline)
    revisions={'formatVersion':1,'baselineSha256':digest(baseline),'baseCommit':'a'*40,'revisions':[{'studio':'springboot','path':'backend/app.py','beforeSha256':digest(b'original\n'),'afterSha256':digest(b'fixed\n'),'afterNormalizedSha256':digest(b'fixed\n'),'tasks':['T058'],'evidence':['integration/validation/reliability/source-revisions.xml']}]}
    return tmp_path,source,revisions


def write(root,revisions): (root/'integration/source-revisions.json').write_text(json.dumps(revisions),encoding='utf-8')


def test_unlisted_change_is_rejected(fixture):
    root,source,revisions=fixture
    assert check_sources(root)


def test_exact_authorized_revision_is_accepted(fixture):
    root,source,revisions=fixture;write(root,revisions)
    assert check_sources(root)==[]
    source.write_bytes(b'fixed\r\n')
    assert check_sources(root)==[]


def test_subsequent_unlisted_mutation_is_rejected(fixture):
    root,source,revisions=fixture;write(root,revisions);source.write_bytes(b'other\n')
    assert check_sources(root)


@pytest.mark.parametrize('corruption',['baseline','before','path','tasks','duplicate'])
def test_revision_manifest_tampering_is_rejected(fixture,corruption):
    root,source,revisions=fixture
    if corruption=='baseline': revisions['baselineSha256']='0'*64
    elif corruption=='before': revisions['revisions'][0]['beforeSha256']='0'*64
    elif corruption=='path': revisions['revisions'][0]['path']='../backend/app.py'
    elif corruption=='tasks': revisions['revisions'][0]['tasks']=[]
    else: revisions['revisions'].append(dict(revisions['revisions'][0]))
    write(root,revisions)
    assert check_sources(root)
