"""main() end to end: every exit path must still clean up.

These drive main() with a stand-in BuildFunctions, so they cover the wiring
between the pieces rather than the pieces themselves.
"""
import os
import tempfile

import pytest
from conftest import FULL_OPENRC

import image_builder.imagebuilder as ib
from image_builder.parsecommands import Commands


@pytest.fixture
def run_build(clean_env, monkeypatch):
    """Runs main() for a build, returning (exit code, propagated exception, calls)."""

    def run(packer=lambda: 0, keygen_ok=True, manifest='img-uuid', argv=None):
        scratch = tempfile.mkdtemp(prefix='mainflow-dirs-')
        calls = []

        class FakeBuild:
            def __init__(self, *a, **k):
                self.tmp_dir = tempfile.mkdtemp(prefix='mainflow-')
                self.image_name = 'img'

            def find_template(self):
                return os.path.join(scratch, 'template.pkr.hcl')

            def find_network_id(self, name):
                return 'net-1'

            def run_packer_init(self, template):
                return 0

            def sweep_orphans(self, *a, **k):
                calls.append('swept')
                return 0

            def create_security_group(self):
                calls.append('sg_created')
                return 'sg-name', 'sg-1'

            def create_keypairs(self):
                if not keygen_ok:
                    return None, None
                calls.append('kp_created')
                return 'kp-name', 'kp-1'

            def run_packer(self, *a):
                return packer()

            def parse_manifest(self):
                return manifest

            def download_image(self, artifact_id):
                return 0

            def delete_image(self, image_id):
                return True

            def cleanup(self, secgroup_id, keypair_id):
                calls.append(f'cleanup(sg={secgroup_id} kp={keypair_id})')

        for key, value in FULL_OPENRC.items():
            clean_env.setenv(key, value)
        clean_env.setenv('IB_TEMPLATE_DIR', scratch)
        clean_env.setenv('IB_DOWNLOAD_DIR', scratch)
        monkeypatch.setattr(ib, 'BuildFunctions', FakeBuild)
        monkeypatch.setattr(ib, 'auth', lambda rc: object())
        monkeypatch.setattr('sys.argv', argv or
                            ['imagebuilder', 'build', '-n', 'img',
                             '-a', 'bgo-default-1', '-s', 'src', '-u', 'almalinux'])

        code, raised = None, None
        try:
            ib.main()
        except SystemExit as exc:
            code = exc.code
        except BaseException as exc:            # noqa: BLE001
            raised = exc
        return code, raised, calls

    return run


def cleaned(calls):
    return [c for c in calls if c.startswith('cleanup')]


def test_successful_build_exits_zero_and_cleans_up(run_build):
    code, raised, calls = run_build()
    assert code == 0 and raised is None
    assert cleaned(calls) == ['cleanup(sg=sg-1 kp=kp-1)']


def test_failed_packer_run_exits_one_and_cleans_up(run_build):
    code, raised, calls = run_build(packer=lambda: 1)
    assert code == 1
    assert cleaned(calls)


def test_interrupt_during_build_still_cleans_up(run_build):
    """The case that used to orphan a security group and a keypair."""
    def interrupt():
        raise KeyboardInterrupt()

    code, raised, calls = run_build(packer=interrupt)
    assert cleaned(calls) == ['cleanup(sg=sg-1 kp=kp-1)']
    assert isinstance(raised, KeyboardInterrupt)     # and is not swallowed


def test_unexpected_exception_still_cleans_up(run_build):
    def boom():
        raise RuntimeError('packer blew up')

    code, raised, calls = run_build(packer=boom)
    assert cleaned(calls)
    assert isinstance(raised, RuntimeError)


def test_keygen_failure_exits_before_packer_and_cleans_up(run_build):
    code, raised, calls = run_build(keygen_ok=False)
    assert code == 1
    assert 'kp_created' not in calls
    assert cleaned(calls) == ['cleanup(sg=sg-1 kp=None)']


def test_unusable_manifest_fails_the_build(run_build):
    code, raised, calls = run_build(manifest=None)
    assert code == 1
    assert cleaned(calls)


# The split made these reachable without driving the whole of main()

def test_image_properties_defaults_to_scsi_and_rng():
    args = Commands(['bootstrap', '-a', 'z', '-u', 'https://x/i.qcow2', '-n', 'n',
                     '-r', '768', '-d', '8', '-f', 'qcow2']).bootstrap_args
    props = ib.image_properties(args)
    assert props == {'hw_rng_model': 'virtio', 'hw_disk_bus': 'scsi',
                     'hw_scsi_model': 'virtio-scsi'}


def test_image_properties_without_scsi():
    args = Commands(['bootstrap', '-a', 'z', '-u', 'https://x/i.qcow2', '-n', 'n',
                     '-r', '768', '-d', '8', '-f', 'qcow2', '-s']).bootstrap_args
    props = ib.image_properties(args)
    assert 'hw_disk_bus' not in props
    assert props['hw_rng_model'] == 'virtio'


def test_image_properties_with_efi():
    args = Commands(['bootstrap', '-a', 'z', '-u', 'https://x/i.qcow2', '-n', 'n',
                     '-r', '768', '-d', '8', '-f', 'qcow2', '-e']).bootstrap_args
    props = ib.image_properties(args)
    assert props['hw_firmware_type'] == 'uefi'
    assert props['hw_machine_type'] == 'q35'


class FakeBootstrap:
    """Records what run_bootstrap asked of it."""

    instances = []

    def __init__(self, *a, **k):
        self.tmp_dir = tempfile.mkdtemp(prefix='bootflow-')
        self.downloaded = None
        self.uploaded = None
        FakeBootstrap.instances.append(self)

    def download_and_check(self, url, checksum_url, digest):
        self.downloaded = (url, checksum_url, digest)
        return None if url.endswith('fail') else os.path.join(self.tmp_dir, 'img.qcow2')

    def create_glance_image(self, *a):
        self.uploaded = a
        return None if a[1] == 'upload-fail' else 'new-image-uuid'


@pytest.fixture
def run_bootstrap(clean_env, monkeypatch, capsys):
    def run(name='img', url='https://example.com/i.qcow2'):
        FakeBootstrap.instances = []
        monkeypatch.setattr(ib, 'BootstrapFunctions', FakeBootstrap)
        args = Commands(['bootstrap', '-a', 'z', '-u', url, '-n', name,
                         '-r', '768', '-d', '8', '-f', 'qcow2']).bootstrap_args
        code = ib.run_bootstrap(args, object(), 'bgo')
        return code, capsys.readouterr(), FakeBootstrap.instances[0]

    return run


def test_bootstrap_writes_only_the_image_id_to_stdout(run_bootstrap):
    code, captured, fake = run_bootstrap()
    assert code == 0
    assert captured.out == 'new-image-uuid'
    assert not os.path.exists(fake.tmp_dir)          # cleaned up


def test_bootstrap_download_failure_exits_one_and_cleans_up(run_bootstrap):
    code, captured, fake = run_bootstrap(url='https://example.com/fail')
    assert code == 1
    assert captured.out == ''
    assert not os.path.exists(fake.tmp_dir)


def test_bootstrap_upload_failure_exits_one_and_cleans_up(run_bootstrap):
    code, captured, fake = run_bootstrap(name='upload-fail')
    assert code == 1
    assert captured.out == ''
    assert not os.path.exists(fake.tmp_dir)


def test_orphans_are_swept_before_anything_new_is_created(run_build):
    """A run killed by the OOM killer leaves its security group and keypair."""
    code, raised, calls = run_build()
    assert 'swept' in calls
    assert calls.index('swept') < calls.index('sg_created')


def test_no_sweep_skips_it(run_build):
    code, raised, calls = run_build(argv=[
        'imagebuilder', 'build', '-n', 'img', '-a', 'bgo-default-1',
        '-s', 'src', '-u', 'almalinux', '--no-sweep'])
    assert 'swept' not in calls
    assert code == 0
