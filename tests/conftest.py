"""Shared fakes.

Nothing here touches a network or a cloud: the OpenStack calls are replaced by
recorders that assert on what the code asked for.
"""
import os
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def repo_root():
    return REPO_ROOT


class FakeNetwork:
    def __init__(self, log):
        self.log = log
        self.networks_result = []

    def create_security_group(self, **kw):
        self.log.append(('sg_created', kw))
        return type('SG', (), {'id': 'sg-uuid'})()

    def create_security_group_rule(self, **kw):
        self.log.append(('rule_created', kw))

    def delete_security_group(self, sgid):
        self.log.append(('sg_deleted', sgid))

    def networks(self, **kw):
        self.log.append(('networks_listed', kw))
        return iter(self.networks_result)


class FakeCompute:
    def __init__(self, log):
        self.log = log

    def create_keypair(self, **kw):
        self.log.append(('kp_created', kw))
        return type('KP', (), {'id': kw.get('name')})()

    def delete_keypair(self, keypair):
        self.log.append(('kp_deleted', keypair))


class FakeImage:
    def __init__(self, log, fail=False):
        self.log = log
        self.fail = fail
        self.download_kwargs = None

    def create_image(self, **kw):
        self.log.append(('image_created', kw))
        if self.fail:
            raise RuntimeError('glance is unhappy')
        return type('IMG', (), {'id': 'new-image-uuid'})()

    def download_image(self, image, output=None, **kw):
        self.log.append(('image_downloaded', image))
        self.download_kwargs = kw
        if self.fail:
            raise RuntimeError('glance is unhappy')
        output.write(b'qcow2 data')

    def delete_image(self, image, **kw):
        self.log.append(('image_deleted', image))


class FakeConn:
    """Stands in for an openstacksdk Connection."""

    def __init__(self, fail_image=False):
        self.log = []
        self.network = FakeNetwork(self.log)
        self.compute = FakeCompute(self.log)
        self.image = FakeImage(self.log, fail=fail_image)

    def kinds(self):
        return [entry[0] for entry in self.log]


@pytest.fixture
def conn():
    return FakeConn()


@pytest.fixture
def build(conn, tmp_path):
    """A BuildFunctions with the constructor bypassed, so no cloud is needed."""
    from image_builder.build import BuildFunctions

    b = BuildFunctions.__new__(BuildFunctions)
    b.conn = conn
    b.tmp_dir = str(tmp_path / 'tmp')
    os.makedirs(b.tmp_dir, exist_ok=True)
    b.download_dir = str(tmp_path / 'downloads')
    os.makedirs(b.download_dir, exist_ok=True)
    b.template_dir = str(tmp_path / 'templates')
    os.makedirs(b.template_dir, exist_ok=True)
    b.image_name = 'test-image'
    b.avail_zone = 'bgo-default-1'
    b.flavor = 'm1.small'
    b.source_image = 'src-uuid'
    b.ssh_user = 'almalinux'
    b.provision_script = '/bin/true'
    return b


@pytest.fixture
def bootstrap(tmp_path):
    from image_builder.bootstrap import BootstrapFunctions

    b = BootstrapFunctions.__new__(BootstrapFunctions)
    b.conn = FakeConn()
    b.tmp_dir = str(tmp_path / 'boot')
    os.makedirs(b.tmp_dir, exist_ok=True)
    return b


@pytest.fixture
def clean_env(monkeypatch):
    """An environment with every OS_* variable removed."""
    for key in list(os.environ):
        if key.startswith(('OS_', 'IB_')):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


FULL_OPENRC = {
    'OS_USERNAME': 'user',
    'OS_PROJECT_NAME': 'project',
    'OS_PASSWORD': 'secret',
    'OS_AUTH_URL': 'https://api.example.com:5000/v3',
    'OS_USER_DOMAIN_NAME': 'dom',
    'OS_PROJECT_DOMAIN_NAME': 'dom',
    'OS_REGION_NAME': 'bgo',
}
