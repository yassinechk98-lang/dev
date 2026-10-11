# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Point d'entree de FreeAV.exe : ouvre l'interface graphique, ou la ligne de commande
si des arguments sont donnes (par exemple : FreeAV.exe scan C:\\Users\\moi\\Downloads)."""

import os
import sys


def _console_streams() -> None:
    """Un .exe sans console (--windowed) demarre sans sys.stdout ni sys.stderr :
    on recupere ceux de l'invite de commandes ou de la redirection qui l'a lance."""
    if sys.platform != "win32" or (sys.stdout is not None and sys.stderr is not None):
        return
    import ctypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.AttachConsole(-1)  # console du programme parent, s'il y en a une
    for number, name in ((-11, "stdout"), (-12, "stderr")):
        stream = None
        handle = kernel32.GetStdHandle(number)
        if handle and handle != ctypes.c_void_p(-1).value:
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
                stream = open(fd, "w", encoding="utf-8", errors="replace", buffering=1)
            except OSError:
                stream = None
        if stream is None:
            try:
                stream = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
            except OSError:
                stream = open(os.devnull, "w", encoding="utf-8")
        setattr(sys, name, stream)


if __name__ == "__main__":
    from freeav.selfupdate import cleanup_old
    cleanup_old()  # anciennes versions laissees par une mise a jour
    if len(sys.argv) > 1:
        _console_streams()
        from freeav.cli import main
        sys.exit(main())
    from freeav.gui import run
    run()
