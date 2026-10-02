"""Bounded, read-only Windows installation discovery; standard library only."""
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

SEARCH_SECONDS = 2.0
IS_WINDOWS = sys.platform == 'win32'
UNINSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
GAME_NAMES = ('World_of_Tanks_CN', 'World_of_Tanks', 'World_of_Tanks_EU',
              'World_of_Tanks_NA', 'World_of_Tanks_ASIA')


def registry_candidates():
    """Read per-user and machine installation locations in both registry views."""
    if winreg is None:
        return
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | view) as root:
                    for index in range(4096):
                        try:
                            name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(root, name) as entry:
                                display = winreg.QueryValueEx(entry, 'DisplayName')[0]
                                if not isinstance(display, str):
                                    continue
                                normalized = display.casefold().replace(' ', '').replace('_', '')
                                if 'worldoftanks' not in normalized and '坦克世界' not in display:
                                    continue
                                location = winreg.QueryValueEx(entry, 'InstallLocation')[0]
                                if isinstance(location, str) and location.strip():
                                    yield Path(os.path.expandvars(location.strip().strip('"')))
                        except OSError:
                            continue
            except OSError:
                continue


def fixed_drives():
    """Exclude removable/network drives from common-folder probes."""
    if not IS_WINDOWS:
        return
    kernel = ctypes.windll.kernel32
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel.GetDriveTypeW.restype = ctypes.c_uint
    mask = kernel.GetLogicalDrives()
    for index in range(26):
        root = f'{chr(65 + index)}:\\'
        if mask & (1 << index) and kernel.GetDriveTypeW(root) == 3:  # DRIVE_FIXED
            yield Path(root)


def common_candidates():
    for drive in fixed_drives():
        for folder in ('', 'Games', 'Game', 'Program Files', 'Program Files (x86)'):
            for name in GAME_NAMES:
                yield drive / folder / name


def valid_game_folder(path):
    # Resolve only existing installations, not every speculative common folder.
    # Replays may not exist until the player enables recording and plays a battle.
    return ((path / 'res/packages/scripts.pkg').is_file()
            and (path / 'WorldOfTanks.exe').is_file())


def emit_matches():
    """Stream each match so a later slow filesystem probe cannot hide it."""
    seen = set()
    for candidates in (registry_candidates(), common_candidates()):
        for path in candidates:
            try:
                if not path.is_absolute() or not valid_game_folder(path):
                    continue
                path = path.resolve()
                key = str(path).casefold()
                if key not in seen:
                    seen.add(key)
                    print(json.dumps(str(path)), flush=True)
            except (OSError, ValueError):
                continue


def detect_game_folders(timeout=SEARCH_SECONDS):
    """A disposable worker enforces the time limit even on stalled filesystem I/O."""
    if not IS_WINDOWS:
        return []
    try:
        result = subprocess.run(
            [sys.executable, '-S', str(Path(__file__).resolve())],
            capture_output=True, text=True, encoding='utf-8', timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        output = result.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b''
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')
    except (OSError, ValueError):
        return []
    matches = []
    seen = set()
    for line in output.splitlines():
        try:
            value = json.loads(line)
            if not isinstance(value, str):
                continue
            path = Path(value)
            key = str(path).casefold()
            if path.is_absolute() and key not in seen:
                seen.add(key)
                matches.append(path)
        except (ValueError, TypeError):
            continue
    return matches


if __name__ == '__main__':
    # The console's Windows code page must not corrupt non-ASCII game paths.
    sys.stdout.reconfigure(encoding='utf-8')
    emit_matches()
