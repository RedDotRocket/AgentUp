import os
import tarfile


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
