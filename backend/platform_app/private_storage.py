"""Keep the local credential handoff private before writing any secrets."""
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path


def _protect(path, directory=False):
    path = Path(path)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if path.is_symlink() or path.is_junction() or not expected(path.stat().st_mode):
        raise OSError('Credential storage has an invalid type.')
    if os.name == 'nt':
        system_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
        powershell = system_root / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
        environment = {**os.environ, 'PSModulePath': str(powershell.parent / 'Modules')}
        subprocess.run(
            [str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(Path(__file__).with_name('private_file_acl.ps1')), '-LiteralPath', str(path.absolute()),
             *(['-Directory'] if directory else [])],
            check=True, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW, env=environment,
        )
    else:
        mode = 0o700 if directory else 0o600
        path.chmod(mode)
        if stat.S_IMODE(path.stat().st_mode) != mode:
            raise OSError('Unable to restrict credential permissions.')


def protect_private_file(path):
    _protect(path)


def protect_private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, exist_ok=True)
    _protect(path, directory=True)


def credential_path(data_dir):
    folder = Path(data_dir) / 'private-access'
    protect_private_directory(folder)
    return folder / 'access-credentials.json'


def write_private_json(path, value):
    # Protect and verify the parent first, so even the initial empty file inherits
    # a private Windows DACL. Existing reader handles must not predate protection.
    protect_private_directory(Path(path).parent)
    fd, temporary = tempfile.mkstemp(prefix='.access-', suffix='.tmp', dir=Path(path).parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            protect_private_file(temporary)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomically publish only a complete private file; never replace an
        # existing handoff from a concurrent initializer.
        if os.name == 'nt':
            os.rename(temporary, path)  # Windows rename fails if the destination exists.
        else:
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
