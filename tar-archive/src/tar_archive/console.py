import os
import sys

COLORS = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "magenta": "\033[35m",
    "yellow": "\033[33m",
}
RESET = "\033[0m"
_windows_ansi_checked = False
_windows_ansi_enabled = False


def print_message(label: str, message: str, color: str) -> None:
    prefix = f"[{label}]"
    if _supports_color():
        prefix = f"{COLORS[color]}{prefix}{RESET}"
    print(f"{prefix} {message}")


def _supports_color() -> bool:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return False
    if os.name != "nt":
        return True
    return _enable_windows_ansi()


def _enable_windows_ansi() -> bool:
    global _windows_ansi_checked, _windows_ansi_enabled
    if _windows_ansi_checked:
        return _windows_ansi_enabled

    _windows_ansi_checked = True
    try:
        import ctypes

        standard_output_handle = -11
        enable_virtual_terminal_processing = 0x0004
        handle = ctypes.windll.kernel32.GetStdHandle(standard_output_handle)
        mode = ctypes.c_uint()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            _windows_ansi_enabled = bool(
                ctypes.windll.kernel32.SetConsoleMode(
                    handle,
                    mode.value | enable_virtual_terminal_processing,
                )
            )
    except (AttributeError, OSError):
        _windows_ansi_enabled = False

    return _windows_ansi_enabled
