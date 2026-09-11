"""Small, editable ANSI color palette for CLI output."""

import sys
from typing import TextIO

TITLE = "\033[96m"
LABEL = "\033[36m"
VALUE = "\033[0m"
INFO = "\033[36m"
WARNING = "\033[33m"
SUCCESS = "\033[32m"
ERROR = "\033[31m"
PROGRESS = "\033[36m"
RESET = "\033[0m"


def paint(text: str, color: str, stream: TextIO = sys.stdout) -> str:
    return f"{color}{text}{RESET}" if stream.isatty() else text
