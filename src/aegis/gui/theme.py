"""Visual language for the mission console.

A console that an operator stares at for an hour needs low luminance, a small
number of semantic colours, and one accent that only ever means "attention".
Everything here is a flat constant so the whole look can be retuned in one file.
"""

from __future__ import annotations

import tkinter.font as tkfont


class C:
    # surfaces
    BG = "#17191c"
    PANEL = "#202326"
    PANEL_HI = "#292d31"
    CARD = "#24282c"
    LINE = "#30353a"
    LINE_HI = "#3c4349"

    # type
    TEXT = "#e3e5e6"
    TEXT_DIM = "#a1a7aa"
    TEXT_FAINT = "#70787d"

    # semantics
    ACCENT = "#d9b36c"     # matte brass - active step and branding
    OK = "#80c697"
    INFO = "#8db7c9"
    WARN = "#d6a66b"
    CRIT = "#d97970"
    IDLE = "#596167"

    STATE = {
        "pending": TEXT_FAINT,
        "active": ACCENT,
        "done": OK,
        "skipped": WARN,
        "blocked": CRIT,
        "failed": CRIT,
    }

    SEVERITY = {
        "info": INFO,
        "success": OK,
        "warning": WARN,
        "critical": CRIT,
    }


def font(size: int = 10, weight: str = "normal", family: str | None = None) -> tuple:
    if family is None:
        family = "Segoe UI"
    return (family, size, weight)


def mono(size: int = 9, weight: str = "normal") -> tuple:
    return ("Consolas", size, weight)


def pick_fonts(root) -> None:
    """Fall back gracefully if Segoe UI / Consolas are missing (non-Windows)."""
    available = set(tkfont.families(root))
    ui = "Segoe UI" if "Segoe UI" in available else (
        "Helvetica Neue" if "Helvetica Neue" in available else "DejaVu Sans"
    )
    code = "Consolas" if "Consolas" in available else (
        "Menlo" if "Menlo" in available else "DejaVu Sans Mono"
    )
    globals()["_UI_FAMILY"] = ui
    globals()["_MONO_FAMILY"] = code

    def _font(size=10, weight="normal", family=None):
        return (family or ui, size, weight)

    def _mono(size=9, weight="normal"):
        return (code, size, weight)

    globals()["font"] = _font
    globals()["mono"] = _mono
