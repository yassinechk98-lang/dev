"""Deuxieme avis par Microsoft Defender, deja present sur tous les Windows 10 et 11.

FreeAV lance l'analyseur en ligne de commande de Defender (MpCmdRun.exe) avec
-DisableRemediation : Defender signale, mais c'est FreeAV qui decide (quarantaine FreeAV,
restaurable). Rien n'est envoye sur Internet par FreeAV ; Defender suit ses propres reglages
(protection dans le cloud) comme il le fait deja en permanence sur le PC.
"""

import os
import re
import subprocess
from pathlib import Path

THREAT_LINE = re.compile(r"^\s*Threat\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
FILE_LINE = re.compile(r"^\s*file\s*:\s*(?P<path>.+?)(?:->.*)?\s*$", re.IGNORECASE)
FOUND = 2  # code de sortie de MpCmdRun quand une menace est trouvee


class DefenderError(Exception):
    pass


def find_mpcmdrun(environ: dict | None = None) -> Path | None:
    """Version la plus recente de MpCmdRun.exe (la plateforme se met a jour hors de Program Files)."""
    env = os.environ if environ is None else environ
    candidates = []
    platform = Path(env.get("ProgramData", r"C:\ProgramData"), "Microsoft", "Windows Defender",
                    "Platform")
    if platform.is_dir():
        versions = sorted((p for p in platform.iterdir() if (p / "MpCmdRun.exe").is_file()),
                          key=lambda p: [int(x) if x.isdigit() else 0 for x in
                                         re.split(r"[.-]", p.name)], reverse=True)
        candidates += [v / "MpCmdRun.exe" for v in versions]
    candidates.append(Path(env.get("ProgramFiles", r"C:\Program Files"), "Windows Defender",
                           "MpCmdRun.exe"))
    return next((c for c in candidates if c.is_file()), None)


def parse_report(output: str) -> dict[Path, str]:
    """Lit la liste des menaces affichee par MpCmdRun : {fichier: nom de la menace}."""
    found: dict[Path, str] = {}
    threat = None
    for line in output.splitlines():
        if m := THREAT_LINE.match(line):
            threat = m.group("name")
        elif threat and (m := FILE_LINE.match(line)):
            found[Path(m.group("path").strip())] = threat
    return found


class DefenderEngine:
    name = "defender"
    by_target = True  # Defender parcourt lui-meme les dossiers, bien plus vite fichier par fichier

    def __init__(self, exe: Path | None = None, runner=None, timeout: float = 3600):
        self.exe = exe or find_mpcmdrun()
        if not self.exe:
            raise DefenderError("Microsoft Defender est introuvable sur ce PC")
        self.runner = runner or _run
        self.timeout = timeout

    def scan_paths(self, paths: list[Path]) -> dict[Path, str]:
        found: dict[Path, str] = {}
        for path in paths:
            result = self.runner([str(self.exe), "-Scan", "-ScanType", "3", "-File",
                                  str(path), "-DisableRemediation"], self.timeout)
            if result.returncode == FOUND:
                report = parse_report(result.stdout or "")
                if not report and Path(path).is_file():
                    report = {Path(path): "menace signalee par Microsoft Defender"}
                if not report:
                    raise DefenderError(f"Defender signale une menace dans {path} sans "
                                        "indiquer le fichier")
                found.update(report)
            elif result.returncode != 0:
                raise DefenderError((result.stdout or result.stderr or
                                     f"code {result.returncode}").strip()[-300:])
        return found


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
