"""Small shared helpers.

Module-level functions rather than static methods on a class: a module is
already the namespace a class was being used for here.
"""
import hashlib
import logging
import shutil
import tempfile

log = logging.getLogger(__name__)


def clean_tmp_files(tmp_dir):
    # Also called from a finally block, so failing to remove a scratch
    # directory must not be what the user ends up seeing
    log.info('Removing temporary directory with content...')
    shutil.rmtree(tmp_dir, ignore_errors=True)


def make_tmp_dir():
    log.info('Creating a directory for temporary files...')
    return tempfile.mkdtemp(prefix='imagebuilder-')


def log_subprocess_output(pipe):
    # Decoded, not repr'd: this is the build log the user watches, and every
    # line of it used to arrive looking like b'...\n'
    for line in iter(pipe.readline, b''):
        log.info(line.decode('utf-8', errors='replace').rstrip())


def valid_digest(digest):
    """Whether hashlib knows this digest name

    Used to reject a bad -t before spending a download on it.
    """
    try:
        hashlib.new(digest.lower())
    except (ValueError, TypeError):
        return False
    return True


def checksum_file(file_path, digest='sha256', chunk_size=65536):
    """Read the file in small pieces, so as to prevent failures to read
    particularly large files.  Also ensures memory usage is kept to a
    minimum. Testing shows default is a pretty good size."""
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        # Raised rather than asserted: assertions disappear under python -O
        raise ValueError(f"chunk_size must be a positive integer, got {chunk_size!r}")
    # hashlib.new() takes any algorithm it supports and raises a clear
    # ValueError naming a bad one. The hand-written if/elif ladder this
    # replaces silently left unknown names as a string and then died with
    # AttributeError on the first update()
    hasher = hashlib.new(digest.lower())
    with open(file_path, 'rb') as handle:
        for block in iter(lambda: handle.read(chunk_size), b''):
            hasher.update(block)
    checksum = hasher.hexdigest()
    log.debug("hexdigest of %s is %s", file_path, checksum)
    return checksum
