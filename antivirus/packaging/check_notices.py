# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Verifie que THIRD_PARTY_NOTICES.txt couvre tout ce que PyInstaller a mis dans FreeAV.exe.

Lit la table des matieres de l'exe : chaque bibliotheque (.dll, .pyd) et chaque paquet Python
doit correspondre a une section du fichier de mentions, et LICENSE et THIRD_PARTY_NOTICES.txt
doivent etre dans l'exe. Un composant inconnu fait echouer la construction : il faut alors
ajouter sa licence avant de le distribuer.

Utilisation : python packaging/check_notices.py dist/FreeAV.exe THIRD_PARTY_NOTICES.txt
"""

import re
import sys
from pathlib import Path

# nom de fichier (minuscules) -> sections du fichier de mentions qui doivent exister
BINARIES = [
    (r"python3\d*\.dll", ["1. Python 3.12"]),
    (r"libffi-\d+\.dll", ["1. Python 3.12"]),
    (r"lib(crypto|ssl)-3(-x64)?\.dll", ["3. OpenSSL 3"]),
    (r"tcl86t\.dll", ["4. Tcl 8.6"]),
    (r"tk86t\.dll", ["5. Tk 8.6"]),
    (r"zlib1\.dll", ["1. Python 3.12"]),
    (r"(vcruntime140(_1)?|msvcp140(_\d)?|ucrtbase|api-ms-win-[a-z0-9-]+)\.dll",
     ["10. Bibliotheques d'execution Microsoft"]),
    (r"yara\.cp3\d+-win_amd64\.pyd",
     ["6. YARA (libyara)", "7. yara-python", "8. authenticode-parser", "3. OpenSSL 3"]),
    # Modules de la bibliotheque standard sans licence a part dans les mentions : refuses
    (r"_(bz2|lzma|sqlite3)\.pyd", ["(bzip2, liblzma ou SQLite : exclure le module ou ajouter sa licence)"]),
    (r"_?[a-z0-9_]+\.pyd", ["1. Python 3.12"]),
]
DATA = [("_tcl_data/", ["4. Tcl 8.6"]), ("_tk_data/", ["5. Tk 8.6"])]
REQUIRED_FILES = ["LICENSE", "THIRD_PARTY_NOTICES.txt"]
OUR_PACKAGES = {"freeav", "freeav_app"}
THIRD_PARTY_PACKAGES = {"yara": ["7. yara-python"]}


def sections(notices: str) -> set[str]:
    """Titres des sections : la ligne qui suit un trait de = et precede "Licence :"."""
    return set(re.findall(r"^={20,}\n(\d+\. .+)\nLicence :", notices, re.M))


def has_section(have: set[str], wanted: str) -> bool:
    return any(title.startswith(wanted) for title in have)


def needed(names: list[str], modules: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Sections exigees par chaque fichier de l'exe, et fichiers inconnus."""
    need, unknown = {}, []
    for name in names:
        base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base.endswith((".dll", ".pyd")):
            rule = next((s for pattern, s in BINARIES if re.fullmatch(pattern, base)), None)
            if rule is None:
                unknown.append(name)
            else:
                need[name] = rule
        for prefix, rule in DATA:
            if name.replace("\\", "/").startswith(prefix):
                need[prefix] = rule
    stdlib = set(sys.stdlib_module_names)
    for module in modules:
        top = module.split(".")[0]
        if top in OUR_PACKAGES or top in stdlib or top.startswith(("pyimod", "_pyi")):
            continue
        if top in THIRD_PARTY_PACKAGES:
            need[top] = THIRD_PARTY_PACKAGES[top]
        else:
            unknown.append(f"module Python {module}")
    return need, sorted(set(unknown))


def problems(names: list[str], modules: list[str], notices: str) -> list[str]:
    have = sections(notices)
    need, unknown = needed(names, modules)
    out = [f"composant sans mention de licence : {u}" for u in unknown]
    for name, wanted in sorted(need.items()):
        out += [f"{name} : section absente de THIRD_PARTY_NOTICES.txt : {w}"
                for w in wanted if not has_section(have, w)]
    out += [f"{f} absent de FreeAV.exe" for f in REQUIRED_FILES
            if not any(n.replace("\\", "/").rsplit("/", 1)[-1] == f for n in names)]
    return out


def read_exe(exe: Path) -> tuple[list[str], list[str]]:
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(exe))
    names = list(archive.toc)
    modules = []
    for name in names:
        if name.endswith(".pyz"):
            modules += list(archive.open_embedded_archive(name).toc)
    return names, modules


if __name__ == "__main__":
    exe, notices = Path(sys.argv[1]), Path(sys.argv[2])
    names, modules = read_exe(exe)
    found = problems(names, modules, notices.read_text(encoding="utf-8"))
    for name in sorted(n for n in names if n.lower().endswith((".dll", ".pyd"))):
        print(name)
    if found:
        for p in found:
            print(f"::error title=Mentions de licence::{p}")
        sys.exit(1)
    print(f"Mentions de licence : {len(names)} fichiers et {len(modules)} modules couverts")
