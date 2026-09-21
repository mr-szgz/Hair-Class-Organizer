"""Launch the desktop app, capture its main window, and close it cleanly."""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

project_root = Path(__file__).resolve().parent.parent
executable = Path(sys.argv[1]).resolve()
screenshot = Path(sys.argv[2]).resolve()
screenshot.parent.mkdir(parents=True, exist_ok=True)
environment = {
    key: value
    for key, value in os.environ.items()
    if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "TCL_LIBRARY", "TK_LIBRARY"}
}
user32 = ctypes.windll.user32
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
windows = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def find_window(handle, _parameter):
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(handle, title, len(title))
    if title.value.startswith("Hair Class Organizer v"):
        windows.append(handle)
    return True


process = subprocess.Popen([str(executable), "-I", "-m", "app"], cwd=project_root, env=environment)
for _ in range(60):
    user32.EnumWindows(find_window, 0)
    if windows or process.poll() is not None:
        break
    time.sleep(0.25)
assert windows, "Hair Class Organizer did not open its main window"
time.sleep(1)
ImageGrab.grab(window=windows[0]).save(screenshot)
user32.PostMessageW(windows[0], 0x0010, 0, 0)
assert process.wait(timeout=15) == 0
print(f"Verified launch and clean close: {screenshot}")
