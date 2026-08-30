"""Running things: system commands, and the privileged helper.

The one part of Gentstore that starts processes. It is also the only place
outside :mod:`gentstore.ui` that depends on Qt, because streaming a build log
into a window as it happens is what ``QProcess`` is for.
"""

from . import eselect
from .command import Command, CommandSpec
from .privilege import Escalation, detect, helper_command, launcher_command

__all__ = [
    "Command",
    "CommandSpec",
    "Escalation",
    "detect",
    "eselect",
    "helper_command",
    "launcher_command",
]
