"""The command line itself, driven as a subprocess."""
import os
import subprocess
import sys

import pytest

from image_builder.parsecommands import Commands


def run(repo_root, *args):
    """Runs the checked-in entry script with no OpenStack credentials."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('OS_') and not k.startswith('IB_')}
    env['PATH'] = os.environ['PATH']
    return subprocess.run([sys.executable, 'imagebuilder', *args],
                          cwd=str(repo_root), env=env,
                          capture_output=True, text=True)


# ------------------------------------------------------------ dispatching

def test_help_lists_both_subcommands(repo_root):
    result = run(repo_root, '--help')
    assert 'build' in result.stdout
    assert 'bootstrap' in result.stdout


def test_no_subcommand_is_an_error(repo_root):
    assert run(repo_root).returncode != 0


@pytest.mark.parametrize('name', ['__init__', 'cleanup', 'nonsense'])
def test_arbitrary_attributes_are_not_dispatchable(repo_root, name):
    """Dispatch used to be getattr(self, argv[1])."""
    result = run(repo_root, name)
    assert result.returncode != 0
    assert 'invalid choice' in (result.stderr + result.stdout)


# ------------------------------------------------------------- parsing

def test_build_args_parse():
    commands = Commands(['build', '-n', 'img', '-a', 'bgo-default-1',
                         '-s', 'src', '-u', 'almalinux'])
    assert commands.build_args.name == 'img'
    assert commands.build_args.flavor == 'm1.small'
    assert commands.build_args.network_name == 'Dualstack'
    assert commands.bootstrap_args is None


def test_bootstrap_args_parse_numbers_as_ints():
    commands = Commands(['bootstrap', '-a', 'bgo-default-1',
                         '-u', 'https://example.com/i.qcow2', '-n', 'n',
                         '-r', '768', '-d', '8', '-f', 'qcow2'])
    assert commands.bootstrap_args.min_ram == 768
    assert commands.bootstrap_args.min_disk == 8
    assert commands.build_args is None


def test_non_numeric_min_ram_is_rejected_at_parse_time(repo_root):
    result = run(repo_root, 'bootstrap', '-a', 'z', '-u', 'https://x/i.qcow2',
                 '-n', 'n', '-r', 'notanumber', '-d', '8', '-f', 'qcow2')
    assert result.returncode != 0
    assert 'invalid int' in result.stderr


# ------------------------------------------------------------- streams

def test_diagnostics_go_to_stderr_leaving_stdout_clean(repo_root):
    """bootstrap pipes its image id out of stdout, so errors must not go there."""
    result = run(repo_root, 'build', '-n', 'x', '-a', 'z', '-s', 'i', '-u', 'u')
    assert result.returncode != 0
    assert result.stdout == ''
    assert 'Missing environment variable' in result.stderr


def test_the_missing_variables_are_named(repo_root):
    result = run(repo_root, 'build', '-n', 'x', '-a', 'z', '-s', 'i', '-u', 'u')
    assert 'OS_USERNAME' in result.stderr


# ------------------------------------------------------------- logging

@pytest.mark.parametrize('flags,expected', [
    pytest.param([], 'WARNING', id='default'),
    pytest.param(['-v'], 'INFO', id='verbose'),
    pytest.param(['--debug'], 'DEBUG', id='debug'),
    pytest.param(['-v', '--debug'], 'DEBUG', id='debug-wins-over-verbose'),
])
def test_log_level_selection(flags, expected):
    import logging

    from image_builder.imagebuilder import configure_logging

    commands = Commands(['build', '-n', 'i', '-a', 'z', '-s', 's', '-u', 'u',
                         *flags])
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, root.handlers[:]
    root.handlers = []                       # basicConfig is a no-op otherwise
    try:
        configure_logging(commands.build_args)
        assert logging.getLevelName(root.level) == expected
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
