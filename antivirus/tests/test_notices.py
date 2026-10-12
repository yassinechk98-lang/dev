"""Mentions des licences tierces de FreeAV.exe."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("check_notices", ROOT / "packaging" / "check_notices.py")
check_notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_notices)
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")

TYPICAL_EXE = ["python312.dll", "VCRUNTIME140.dll", "api-ms-win-crt-runtime-l1-1-0.dll",
               "libcrypto-3.dll", "libssl-3.dll", "libffi-8.dll", "tcl86t.dll", "tk86t.dll",
               "_ssl.pyd", "_ctypes.pyd", "_tkinter.pyd", "yara.cp312-win_amd64.pyd",
               "_tcl_data/init.tcl", "_tk_data/license.terms", "LICENSE",
               "THIRD_PARTY_NOTICES.txt", "PYZ.pyz"]


def test_every_section_the_check_expects_is_in_the_notices():
    have = check_notices.sections(NOTICES)
    wanted = {s for _, rule in check_notices.BINARIES + check_notices.DATA for s in rule
              if not s.startswith("(")}
    assert all(check_notices.has_section(have, s) for s in wanted)
    assert len(have) == 10 and "Licence : Python-2.0" in NOTICES


def test_a_typical_freeav_exe_is_fully_covered():
    assert check_notices.problems(TYPICAL_EXE, ["freeav.gui", "tkinter", "yara", "json"],
                                  NOTICES) == []


def test_an_unknown_library_or_package_fails_the_build():
    found = check_notices.problems(TYPICAL_EXE + ["libinconnue.dll", "_bz2.pyd"],
                                   ["PIL.Image"], NOTICES)
    assert any("libinconnue.dll" in p for p in found)
    assert any("_bz2.pyd" in p for p in found)
    assert any("PIL.Image" in p for p in found)
    assert check_notices.problems(["python312.dll"], [], NOTICES) == [
        "LICENSE absent de FreeAV.exe", "THIRD_PARTY_NOTICES.txt absent de FreeAV.exe"]
