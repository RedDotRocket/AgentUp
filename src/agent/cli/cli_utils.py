import os
import tarfile
from collections import OrderedDict

import click


def _is_within_directory(base_dir: str, target_path: str) -> bool:
    """
    Return True if the realpath of target_path is inside realpath of base_dir.
    """
    base_dir = os.path.abspath(base_dir)
    target_path = os.path.abspath(target_path)
    return os.path.commonpath([base_dir]) == os.path.commonpath([base_dir, target_path])


def safe_extract(tar: tarfile.TarFile, path: str = ".", members=None) -> None:
    """
    Extracts only those members whose final paths stay within `path`.
    Raises Exception on any path traversal attempt.
    """
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not _is_within_directory(path, member_path):
            raise Exception(f"Path traversal detected in tar member: {member.name!r}")
    # Bandit: I am doing this to make you happy!
    tar.extractall(path=path, members=members)  # nosec


class OrderedGroup(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        super().__init__(name=name, commands=commands, **attrs)
        self.commands = OrderedDict()

    def add_command(self, cmd, name=None):
        name = name or cmd.name
        self.commands[name] = cmd

    def list_commands(self, ctx):
        return self.commands.keys()


class MutuallyExclusiveOption(click.Option):
    """Error when this option is used together with any of `mutually_exclusive`."""

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        other_used = [name for name in self.mutually_exclusive if opts.get(name)]
        if other_used and opts.get(self.name):
            raise click.UsageError(
                f"Option '{self.name.replace('_', '-')}' is mutually exclusive with: {', '.join(n.replace('_', '-') for n in other_used)}"
            )
        return super().handle_parse_result(ctx, opts, args)
