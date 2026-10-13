"""Reperage des pieges courants qui arrivent par Internet, sans signature.

Les detections sont "suspectes" (comme YARA) : signalees, jamais mises en quarantaine
automatiquement. Pour eviter les fausses alertes, chaque regle vise un cas precis :
  - double extension qui cache un programme : "facture.pdf.exe", "photo.jpg.scr" ;
  - raccourci (.lnk) qui lance PowerShell cache ou encode, mshta ou un script distant ;
  - script Windows (.js, .vbs, .hta, .wsf...) telecharge depuis Internet (marque
    "Mark of the Web" de Windows) et qui telecharge ou execute autre chose ;
  - document Office avec macros, telecharge depuis Internet, dont la macro se lance seule
    a l'ouverture.
Un script ou un document cree sur le PC (sans marque Internet) n'est jamais signale.
"""

import os
import re
import zipfile
from pathlib import Path

MAX_READ = 2 * 1024 * 1024  # on ne lit que le debut des gros fichiers

PROGRAM_EXTS = {".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".vbs", ".js", ".jse", ".vbe",
                ".wsf", ".hta", ".msi", ".ps1", ".lnk", ".cpl"}
DECOY_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf",
              ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".mp3", ".mp4", ".avi", ".mov",
              ".zip", ".rar", ".odt", ".csv", ".html", ".htm"}
SCRIPT_EXTS = {".js", ".jse", ".vbs", ".vbe", ".wsf", ".wsh", ".hta", ".ps1"}
MACRO_EXTS = {".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".xlsb", ".doc", ".xls", ".ppt"}

# Un script qui telecharge ET execute (les deux), ou qui se cache
SCRIPT_FETCH = re.compile(rb"(msxml2\.xmlhttp|winhttp\.winhttprequest|downloadstring|"
                          rb"downloadfile|invoke-webrequest|bitsadmin|urldownloadtofile|"
                          rb"net\.webclient|https?://)", re.I)
SCRIPT_RUN = re.compile(rb"(wscript\.shell|shell\.application|\.run\s*\(|\.shellexecute|"
                        rb"invoke-expression|\biex\b|start-process|frombase64string|"
                        rb"powershell(\.exe)?\s+-[a-z]*\s*(-?e(nc(odedcommand)?)?\b|-w(indowstyle)?\s+hidden))",
                        re.I)
LNK_BAD = [re.compile(p, re.I) for p in (
    r"powershell(\.exe)?.{0,200}?(-e(nc|ncodedcommand)?\s|-w(indowstyle)?\s+h(idden)?\b|"
    r"downloadstring|invoke-webrequest|iex\b|frombase64string)",
    r"mshta(\.exe)?\s+\S*(https?:|javascript:|vbscript:)",
    r"(cmd(\.exe)?\s+/c|wscript|cscript).{0,200}?(https?://|\\\\[^\\]+\\[^\\]+\\.*\.(vbs|js|bat|exe))",
)]
AUTO_MACRO = re.compile(rb"(autoopen|auto_open|document_open|workbook_open|autoexec|"
                        rb"auto_close|document_close)", re.I)


def from_internet(path: Path) -> bool:
    """Marque "Mark of the Web" de Windows (flux Zone.Identifier, ZoneId 3 ou 4)."""
    if os.name != "nt":
        return False
    try:
        with open(f"{path}:Zone.Identifier", "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(4096)
    except OSError:
        return False
    match = re.search(r"ZoneId\s*=\s*(\d)", text)
    return bool(match) and int(match.group(1)) >= 3


def _head(path: Path) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(MAX_READ)


def _double_extension(path: Path) -> str | None:
    suffixes = [s.lower() for s in path.suffixes]
    if len(suffixes) >= 2 and suffixes[-1] in PROGRAM_EXTS and suffixes[-2] in DECOY_EXTS:
        return f"Heuristique.DoubleExtension ({suffixes[-2]}{suffixes[-1]})"
    # Espaces avant l'extension pour la cacher : "facture.pdf          .exe"
    if suffixes and suffixes[-1] in PROGRAM_EXTS and re.search(r"\s{5,}\.[a-z0-9]+$", path.name, re.I):
        return "Heuristique.ExtensionCachee"
    return None


def _shortcut(path: Path, data: bytes) -> str | None:
    if not data.startswith(b"L\x00\x00\x00"):
        return None
    text = data.decode("utf-16-le", errors="ignore") + " " + data.decode("latin-1")
    text = " ".join(text.split())
    if any(p.search(text) for p in LNK_BAD):
        return "Heuristique.RaccourciPiege"
    return None


WSH = re.compile(rb"activexobject|wscript|getobject\s*\(", re.I)


def _script(ext: str, data: bytes) -> str | None:
    # Un .js de site web ne parle jamais a Windows Script Host : seuls ceux-la sont vises
    if ext in (".js", ".jse") and not WSH.search(data):
        return None
    if SCRIPT_FETCH.search(data) and SCRIPT_RUN.search(data):
        return "Heuristique.ScriptTelechargeur"
    return None


def _macro(path: Path, data: bytes) -> str | None:
    if data.startswith(b"PK"):  # Office 2007+ : la macro est dans vbaProject.bin
        try:
            with zipfile.ZipFile(path) as archive:
                vba = [n for n in archive.namelist() if n.lower().endswith("vbaproject.bin")]
                if not vba:
                    return None
                with archive.open(vba[0]) as fh:
                    data = fh.read(MAX_READ)
        except (zipfile.BadZipFile, OSError, RuntimeError, KeyError):
            return None
    elif not data.startswith(b"\xd0\xcf\x11\xe0") or (b"V\x00B\x00A" not in data
                                                           and b"VBA" not in data):
        return None
    if AUTO_MACRO.search(data):
        return "Heuristique.MacroAutomatique"
    return None


def check(path: Path, internet: bool | None = None) -> str | None:
    """Nom du piege reconnu dans ce fichier, ou None."""
    path = Path(path)
    if threat := _double_extension(path):
        return threat
    ext = path.suffix.lower()
    if ext not in SCRIPT_EXTS | MACRO_EXTS | {".lnk"}:
        return None
    data = _head(path)
    if ext == ".lnk":
        return _shortcut(path, data)
    if internet is None:
        internet = from_internet(path)
    if not internet:
        return None
    if ext in SCRIPT_EXTS:
        return _script(ext, data)
    return _macro(path, data)
