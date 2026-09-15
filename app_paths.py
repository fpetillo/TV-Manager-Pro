"""Stable installation paths for source and packaged Windows launches."""
from pathlib import Path
import sys


def application_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
