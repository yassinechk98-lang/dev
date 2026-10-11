"""Ressource de version Windows de FreeAV.exe."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "make_version_info", Path(__file__).parent.parent / "packaging" / "make_version_info.py")
make_version_info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_version_info)


def test_version_resource_names_the_product():
    text = make_version_info.render(18, "0.1.0")
    assert "filevers=(0, 1, 0, 18)" in text and "prodvers=(0, 1, 0, 18)" in text
    for value in ("'FreeAV (projet open source)'", "'FreeAV - antivirus gratuit'", "'0.1.0.18'",
                  "'FreeAV.exe'", "'Copyright (C) 2026 Yassine - Licence GPL-3.0-or-later'"):
        assert value in text


def test_out_of_range_build_is_refused():
    with pytest.raises(ValueError):
        make_version_info.render(70000, "0.1.0")


def test_pyinstaller_reads_the_resource(tmp_path):
    versioninfo = pytest.importorskip("PyInstaller.utils.win32.versioninfo", exc_type=ImportError)
    path = tmp_path / "version_info.txt"
    path.write_text(make_version_info.render(18, "0.1.0"), encoding="utf-8")
    info = versioninfo.load_version_info_from_text_file(str(path))
    assert info.ffi.fileVersionMS == 0x00000001 and info.ffi.fileVersionLS == 0x00000012
    assert "FreeAV - antivirus gratuit" in str(info)


def test_license_text_ships_with_freeav():
    text = (Path(__file__).parent.parent / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text
