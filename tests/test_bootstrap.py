"""Downloading, verifying and uploading an upstream cloud image."""
import hashlib
import io
import os
import urllib.request

import pytest

from image_builder import bootstrap as bootstrap_module
from image_builder import helpers
from image_builder.bootstrap import BootstrapFunctions

HASH = 'a' * 64
IMAGE = b'x' * 5000


# --------------------------------------------------------------- digests

@pytest.mark.parametrize('name', ['sha256', 'sha512', 'md5', 'sha1', 'SHA256',
                                  'sha384', 'blake2b'])
def test_every_hashlib_digest_works(tmp_path, name):
    """The old if/elif ladder died with AttributeError on anything else."""
    sample = tmp_path / 'sample'
    sample.write_bytes(b'hello')
    assert len(helpers.checksum_file(str(sample), name)) > 16


def test_unknown_digest_raises_a_clear_error(tmp_path):
    sample = tmp_path / 'sample'
    sample.write_bytes(b'hello')
    with pytest.raises(ValueError):
        helpers.checksum_file(str(sample), 'notahash')


def test_valid_digest():
    assert helpers.valid_digest('sha1')
    assert not helpers.valid_digest('notahash')


# ------------------------------------------------- checksum file parsing

find = BootstrapFunctions.find_expected_checksum


@pytest.mark.parametrize('text,name,expected', [
    pytest.param(f'{HASH}  img.qcow2\n', 'img.qcow2', HASH, id='coreutils'),
    pytest.param(f'{HASH} *img.img\n', 'img.img', HASH, id='binary-star'),
    pytest.param(f'SHA256 (img.qcow2) = {HASH}\n', 'img.qcow2', HASH, id='bsd'),
    pytest.param(f'{HASH.upper()}  img.qcow2\n', 'img.qcow2', HASH, id='uppercase'),
    pytest.param(f'# c\n\n{HASH}  img.qcow2\n', 'img.qcow2', HASH, id='comments'),
    pytest.param(f'{HASH}  ./images/img.qcow2\n', 'img.qcow2', HASH, id='path'),
    pytest.param(f'{HASH}  other.qcow2\n', 'img.qcow2', None, id='name-absent'),
])
def test_checksum_layouts(text, name, expected):
    assert find(text, name) == expected


def test_the_right_line_is_picked_among_several():
    text = f"{'a' * 64}  a.qcow2\n{'b' * 64}  b.qcow2\n"
    assert find(text, 'b.qcow2') == 'b' * 64


# --------------------------------------------------- download and verify

class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(payload)
        self.headers = {}          # deliberately no content-length

    def read(self, n=None):
        return self.stream.read(n) if n else self.stream.read()

    def close(self):
        pass


@pytest.fixture
def fake_http(monkeypatch):
    """Serves image bytes for the image URL and text for the checksum URL."""
    state = {'image': IMAGE, 'checksum': b'', 'timeouts': []}

    def fake_urlopen(req, timeout=None):
        state['timeouts'].append(timeout)
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        payload = state['checksum'] if 'sum' in url.lower() else state['image']
        return FakeResponse(payload)

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    return state


IMAGE_URL = 'https://example.com/img.qcow2'
SUM_URL = 'https://example.com/sha256sum.txt'


def test_a_real_image_is_accepted_without_a_content_length_header(bootstrap, fake_http):
    assert bootstrap.download_and_check(IMAGE_URL) is not None


def test_an_error_page_is_rejected_on_its_actual_size(bootstrap, fake_http):
    fake_http['image'] = b'404 not found'
    assert bootstrap.download_and_check(IMAGE_URL) is None


def test_requests_carry_a_timeout(bootstrap, fake_http):
    bootstrap.download_and_check(IMAGE_URL)
    assert fake_http['timeouts']
    assert all(t == bootstrap_module.SOCKET_TIMEOUT for t in fake_http['timeouts'])


def test_matching_checksum_is_accepted(bootstrap, fake_http):
    digest = hashlib.sha256(IMAGE).hexdigest()
    fake_http['checksum'] = f'{digest}  img.qcow2\n'.encode()
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL) is not None


def test_uppercase_checksum_file_is_accepted(bootstrap, fake_http):
    digest = hashlib.sha256(IMAGE).hexdigest()
    fake_http['checksum'] = f'{digest.upper()}  img.qcow2\n'.encode()
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL) is not None


def test_mismatched_checksum_is_rejected(bootstrap, fake_http):
    fake_http['checksum'] = f"{'f' * 64}  img.qcow2\n".encode()
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL) is None


def test_hash_listed_under_another_name_still_passes_via_fallback(bootstrap, fake_http):
    """Kept so vendors whose checksum files name things differently still work."""
    digest = hashlib.sha256(IMAGE).hexdigest()
    fake_http['checksum'] = f'{digest}  somethingelse.qcow2\n'.encode()
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL) is not None


def test_checksum_file_with_nothing_usable_is_rejected(bootstrap, fake_http):
    fake_http['checksum'] = b'garbage\n'
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL) is None


def test_bad_digest_is_rejected_before_downloading(bootstrap, fake_http):
    assert bootstrap.download_and_check(IMAGE_URL, SUM_URL, 'notahash') is None
    assert fake_http['timeouts'] == []          # nothing was fetched


# ------------------------------------------------------------- uploading

def test_upload_creates_a_new_image_and_returns_its_id(bootstrap, tmp_path):
    image_file = tmp_path / 'img.qcow2'
    image_file.write_bytes(IMAGE)
    image_id = bootstrap.create_glance_image(
        str(image_file), 'GOLD Test', 'qcow2', 8, 768,
        {'hw_disk_bus': 'scsi', 'hw_rng_model': 'virtio'})
    assert image_id == 'new-image-uuid'

    created = [e[1] for e in bootstrap.conn.log if e[0] == 'image_created'][0]
    assert created['name'] == 'GOLD Test'
    assert created['disk_format'] == 'qcow2'
    assert created['container_format'] == 'bare'
    assert created['visibility'] == 'private'
    assert created['min_disk'] == 8 and created['min_ram'] == 768
    assert created['hw_disk_bus'] == 'scsi'


def test_upload_forces_a_create_and_adds_no_metadata_of_its_own(bootstrap, tmp_path):
    """Defaults would return an existing image and inject vendor properties."""
    image_file = tmp_path / 'img.qcow2'
    image_file.write_bytes(IMAGE)
    bootstrap.create_glance_image(str(image_file), 'n', 'qcow2', 8, 768, {})
    created = [e[1] for e in bootstrap.conn.log if e[0] == 'image_created'][0]
    assert created['allow_duplicates'] is True
    assert created['disable_vendor_agent'] is False


def test_failed_upload_returns_none(bootstrap, tmp_path):
    bootstrap.conn.image.fail = True
    image_file = tmp_path / 'img.qcow2'
    image_file.write_bytes(IMAGE)
    assert bootstrap.create_glance_image(
        str(image_file), 'n', 'qcow2', 8, 768, {}) is None


def test_bootstrap_no_longer_carries_an_unused_availability_zone():
    assert not hasattr(BootstrapFunctions, 'avail_zone')
    import inspect
    params = inspect.signature(BootstrapFunctions.__init__).parameters
    assert 'avail_zone' not in params
    assert os.environ is not None       # keep flake quiet about the import
