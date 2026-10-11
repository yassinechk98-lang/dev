"""Ecrit la ressource de version Windows de FreeAV.exe (format VSVersionInfo de PyInstaller),
pour que les proprietes du fichier et les antivirus voient quel produit c'est.

Utilisation : python packaging/make_version_info.py <numero de build> <fichier de sortie>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from freeav import __version__  # noqa: E402

COMPANY = "FreeAV (projet open source)"
DESCRIPTION = "FreeAV - antivirus gratuit"
COPYRIGHT = "Copyright (c) 2026 Yassine - licence GNU GPL v3 (GPL-3.0-only)"

TEMPLATE = """# Genere par packaging/make_version_info.py
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vers},
    prodvers={vers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040C04B0',
        [StringStruct('CompanyName', {company!r}),
         StringStruct('FileDescription', {description!r}),
         StringStruct('FileVersion', {text!r}),
         StringStruct('InternalName', 'FreeAV'),
         StringStruct('LegalCopyright', {copyright!r}),
         StringStruct('OriginalFilename', 'FreeAV.exe'),
         StringStruct('ProductName', 'FreeAV'),
         StringStruct('ProductVersion', {text!r})])
    ]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
"""


def version_tuple(version: str, build: int) -> tuple[int, int, int, int]:
    parts = [int(p) for p in version.split(".")[:3]]
    parts += [0] * (3 - len(parts))
    if not 0 <= build <= 0xFFFF or any(not 0 <= p <= 0xFFFF for p in parts):
        raise ValueError(f"version hors limites pour Windows : {version}.{build}")
    return (*parts, build)


def render(build: int, version: str = __version__) -> str:
    vers = version_tuple(version, build)
    return TEMPLATE.format(vers=vers, text=".".join(map(str, vers)), company=COMPANY,
                           description=DESCRIPTION, copyright=COPYRIGHT)


if __name__ == "__main__":
    build, out = int(sys.argv[1]), Path(sys.argv[2])
    out.write_text(render(build), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
