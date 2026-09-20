"""The build path: resource lifecycle, manifest handling, image download."""
import io
import json
import os
import subprocess
import types

import pytest

from image_builder import helpers

# --------------------------------------------------------------- keypairs

def test_keygen_failure_reports_rather_than_returning_a_usable_key(build, monkeypatch):
    monkeypatch.setattr(subprocess, 'run',
                        lambda *a, **k: types.SimpleNamespace(returncode=1))
    name, keypair_id = build.create_keypairs()
    assert name is None and keypair_id is None


def test_keygen_runs_without_a_shell_and_off_PATH(build, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen['cmd'] = cmd
        seen['kwargs'] = kwargs
        return types.SimpleNamespace(returncode=1)   # stop before the key is read

    monkeypatch.setattr(subprocess, 'run', fake_run)
    build.create_keypairs()
    assert isinstance(seen['cmd'], list)
    assert seen['cmd'][0] == 'ssh-keygen'
    assert 'shell' not in seen['kwargs']


def test_successful_keygen_registers_the_public_key(build):
    name, keypair_id = build.create_keypairs()
    assert name.startswith('imagebuilder-')
    assert keypair_id == name
    created = [e for e in build.conn.log if e[0] == 'kp_created']
    assert len(created) == 1
    assert created[0][1]['public_key'].startswith('ecdsa-')


# -------------------------------------------------------- security groups

def test_security_group_opens_ssh_on_both_ethertypes(build):
    name, sgid = build.create_security_group()
    assert name.startswith('imagebuilder-')
    rules = [e[1] for e in build.conn.log if e[0] == 'rule_created']
    assert sorted(r['ethertype'] for r in rules) == ['IPv4', 'IPv6']
    for rule in rules:
        assert rule['security_group_id'] == sgid
        assert rule['direction'] == 'ingress'
        assert rule['protocol'] == 'tcp'
        assert rule['port_range_min'] == rule['port_range_max'] == 22


# ---------------------------------------------------------------- cleanup

def test_cleanup_removes_both_resources(build):
    build.cleanup('sg-1', 'kp-1')
    assert ('sg_deleted', 'sg-1') in build.conn.log
    assert ('kp_deleted', 'kp-1') in build.conn.log


def test_cleanup_skips_resources_that_were_never_created(build):
    """Runs from a finally, so it sees half-built states."""
    build.cleanup('sg-1', None)
    assert ('sg_deleted', 'sg-1') in build.conn.log
    assert 'kp_deleted' not in build.conn.kinds()


def test_cleanup_with_nothing_to_do_is_a_noop(build):
    build.cleanup(None, None)
    assert build.conn.log == []


def test_cleanup_never_raises_so_it_cannot_mask_the_real_error(build):
    def explode(_):
        raise RuntimeError('neutron is down')

    build.conn.network.delete_security_group = explode
    build.cleanup('sg-1', 'kp-1')                    # must not raise
    assert ('kp_deleted', 'kp-1') in build.conn.log  # and carries on


def test_clean_tmp_files_tolerates_a_missing_directory():
    helpers.clean_tmp_files('/nonexistent/path/at/all')


# --------------------------------------------------------------- manifest

def write_manifest(build, payload):
    path = os.path.join(build.tmp_dir, 'packer-manifest.json')
    with open(path, 'w') as fh:
        if isinstance(payload, str):
            fh.write(payload)
        else:
            json.dump(payload, fh)


def test_good_manifest_yields_the_artifact_id(build):
    write_manifest(build, {'builds': [{'artifact_id': 'bgo:image-uuid'}]})
    assert build.parse_manifest() == 'bgo:image-uuid'


@pytest.mark.parametrize('payload', [
    pytest.param('{ not json at all', id='malformed'),
    pytest.param({}, id='no-builds-key'),
    pytest.param({'builds': []}, id='empty-builds'),
    pytest.param({'builds': [{}]}, id='no-artifact-id'),
])
def test_unusable_manifest_returns_none_instead_of_raising(build, payload):
    write_manifest(build, payload)
    assert build.parse_manifest() is None


def test_missing_manifest_returns_none(build):
    assert build.parse_manifest() is None


# --------------------------------------------------------------- networks

def test_find_network_returns_the_first_match(build):
    build.conn.network.networks_result = [
        type('Net', (), {'id': 'net-1'})(),
        type('Net', (), {'id': 'net-2'})(),
    ]
    assert build.find_network_id('Dualstack') == 'net-1'


def test_find_network_returns_false_when_absent(build):
    build.conn.network.networks_result = []
    assert build.find_network_id('Nope') is False


# ----------------------------------------------------------------- images

def test_download_writes_the_file_and_then_deletes_from_glance(build):
    assert build.download_image('img-uuid') == 0
    written = os.listdir(build.download_dir)
    assert len(written) == 1
    assert written[0].startswith('test-image-') and written[0].endswith('.qcow2')
    assert ('image_deleted', 'img-uuid') in build.conn.log


def test_failed_download_keeps_the_image_and_removes_the_partial_file(build):
    build.conn.image.fail = True
    assert build.download_image('img-uuid') == 1
    assert os.listdir(build.download_dir) == []
    assert 'image_deleted' not in build.conn.kinds()


def test_delete_image_of_nothing_does_not_call_the_api(build):
    assert build.delete_image(None) is False
    assert build.conn.log == []


def test_delete_image_reports_failure(build):
    def explode(image, **kw):
        raise RuntimeError('nope')

    build.conn.image.delete_image = explode
    assert build.delete_image('img-uuid') is False


# --------------------------------------------------------------- template

def test_hcl_template_is_preferred_over_the_legacy_one(build):
    open(os.path.join(build.template_dir, 'template.pkr.hcl'), 'w').close()
    open(os.path.join(build.template_dir, 'template'), 'w').close()
    assert build.find_template().endswith('template.pkr.hcl')


def test_legacy_template_is_still_accepted(build):
    open(os.path.join(build.template_dir, 'template'), 'w').close()
    assert build.find_template().endswith('template')


def test_missing_template_returns_none(build):
    assert build.find_template() is None


def test_legacy_template_passes_when_the_plugin_is_already_installed(build, monkeypatch):
    """required_plugins is HCL2 only, so init has nothing to install from."""
    monkeypatch.setattr(type(build), 'openstack_plugin_installed',
                        lambda self: True)
    assert build.run_packer_init('/some/path/template') == 0


def test_legacy_template_fails_early_when_the_plugin_is_missing(build, monkeypatch):
    """Better here than after the security group and keypair exist."""
    monkeypatch.setattr(type(build), 'openstack_plugin_installed',
                        lambda self: False)
    assert build.run_packer_init('/some/path/template') == 1


@pytest.mark.parametrize('stdout,expected', [
    pytest.param('', False, id='nothing-installed'),
    pytest.param('/home/u/.config/packer/plugins/github.com/hashicorp/openstack/'
                 'packer-plugin-openstack_v1.1.4_x5.0_linux_amd64\n', True,
                 id='openstack-present'),
    pytest.param('/home/u/.config/packer/plugins/github.com/hashicorp/qemu/'
                 'packer-plugin-qemu_v1.1.0_x5.0_linux_amd64\n', False,
                 id='other-plugin-only'),
])
def test_plugin_detection_reads_the_output_not_the_exit_code(build, monkeypatch,
                                                             stdout, expected):
    monkeypatch.setattr(subprocess, 'run',
                        lambda *a, **k: types.SimpleNamespace(stdout=stdout,
                                                              returncode=0))
    assert build.openstack_plugin_installed() is expected


def test_missing_packer_binary_is_reported_not_raised(build, monkeypatch):
    def no_packer(*a, **k):
        raise FileNotFoundError('packer')

    monkeypatch.setattr(subprocess, 'run', no_packer)
    assert build.openstack_plugin_installed() is False


# ------------------------------------------------------------ packer argv

def test_packer_argv_supplies_every_declared_variable(build, monkeypatch, repo_root):
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured['cmd'] = cmd
            self.stdout = io.BytesIO(b'')

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.stdout.close()
            return False

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, 'Popen', FakePopen)
    build.run_packer(os.path.join(build.template_dir, 'template.pkr.hcl'),
                     'sg-name', 'kp-name', 'net-uuid')

    cmd = captured['cmd']
    assert cmd[:2] == ['packer', 'build']
    assert '--var' not in cmd                      # the old long form
    supplied = {cmd[i + 1].split('=')[0] for i, a in enumerate(cmd) if a == '-var'}

    declared = set()
    with open(repo_root / 'template.pkr.hcl') as fh:
        for line in fh:
            if line.startswith('variable "'):
                declared.add(line.split('"')[1])
    assert supplied == declared


def test_download_streams_rather_than_buffering_the_whole_image(build):
    """Without stream=True openstacksdk reads the entire image into memory.

    A 10 GiB image then needs more than 20 GiB of RAM and the process is
    killed, which is exactly what happened on a builder node.
    """
    build.download_image('img-uuid')
    assert build.conn.image.download_kwargs.get('stream') is True
