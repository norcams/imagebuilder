"""Reading credentials from the environment."""
import pytest
from conftest import FULL_OPENRC

from image_builder import imagebuilder


def test_openrc_without_the_legacy_variables_is_accepted(clean_env):
    """OS_IDENTITY_API_VERSION and OS_NO_CACHE were required but never used."""
    for key, value in FULL_OPENRC.items():
        clean_env.setenv(key, value)
    rc = imagebuilder.get_openstack_rc()
    assert rc['username'] == 'user'
    assert rc['region_name'] == 'bgo'


def test_unused_keys_are_not_carried_around(clean_env):
    for key, value in FULL_OPENRC.items():
        clean_env.setenv(key, value)
    rc = imagebuilder.get_openstack_rc()
    assert 'api_version' not in rc
    assert 'no_cache' not in rc


def test_cacert_is_optional(clean_env):
    for key, value in FULL_OPENRC.items():
        clean_env.setenv(key, value)
    assert imagebuilder.get_openstack_rc()['cacert'] is None
    clean_env.setenv('OS_CACERT', '/etc/ssl/ca.pem')
    assert imagebuilder.get_openstack_rc()['cacert'] == '/etc/ssl/ca.pem'


@pytest.mark.parametrize('missing', sorted(FULL_OPENRC))
def test_each_required_variable_is_reported_by_name(clean_env, missing):
    for key, value in FULL_OPENRC.items():
        if key != missing:
            clean_env.setenv(key, value)
    with pytest.raises(KeyError) as excinfo:
        imagebuilder.get_openstack_rc()
    assert missing in excinfo.value.args[0]


def test_all_missing_variables_are_reported_not_just_the_first(clean_env):
    for key, value in FULL_OPENRC.items():
        if key not in ('OS_PASSWORD', 'OS_REGION_NAME'):
            clean_env.setenv(key, value)
    with pytest.raises(KeyError) as excinfo:
        imagebuilder.get_openstack_rc()
    message = excinfo.value.args[0]
    assert 'OS_PASSWORD' in message
    assert 'OS_REGION_NAME' in message
