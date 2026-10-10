"""Interface en ligne de commande : python -m freeav scan <chemin>..."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .clamav import ClamdClient
from .quarantine import DEFAULT_DIR, Quarantine
from .scanner import Scanner
from .signatures import load_default


def build_scanner(args) -> Scanner:
    db = load_default([Path(p) for p in args.db])
    clamd = None
    if args.clamav:
        clamd = ClamdClient(unix_socket=args.clamd_socket, host=args.clamd_host,
                            port=args.clamd_port)
        if not clamd.ping():
            print("Attention : clamd injoignable, analyse par signatures uniquement.",
                  file=sys.stderr)
            clamd = None
    return Scanner(db, clamd)


def cmd_scan(args) -> int:
    scanner = build_scanner(args)
    quarantine = Quarantine(Path(args.quarantine_dir))
    print(f"FreeAV {__version__} : {len(scanner.db)} signatures chargees"
          + (", moteur ClamAV actif" if scanner.clamd else ""))
    report = scanner.scan([Path(p) for p in args.paths], exclude={quarantine.directory})

    for det in report.detections:
        line = f"MENACE  {det.path}  ->  {det.threat} ({det.engine})"
        if args.quarantine:
            quarantine.isolate(det.path, det.threat)
            line += "  [mis en quarantaine]"
        print(line)
    for path, err in report.errors:
        print(f"ERREUR  {path} : {err}", file=sys.stderr)

    print(f"\n{report.scanned} fichiers analyses, {report.skipped} ignores, "
          f"{len(report.detections)} menace(s), {len(report.errors)} erreur(s).")
    return 1 if report.detections else 0


def cmd_quarantine(args) -> int:
    quarantine = Quarantine(Path(args.quarantine_dir))
    if args.restore:
        print(f"Restaure : {quarantine.restore(args.restore)}")
    elif args.delete:
        quarantine.delete(args.delete)
        print("Supprime definitivement.")
    else:
        items = quarantine.list()
        if not items:
            print("La quarantaine est vide.")
        for item in items:
            print(f"{item['id']}  {item['threat']}  {item['original_path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="freeav", description="Antivirus gratuit FreeAV")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--quarantine-dir", default=str(DEFAULT_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="analyser des fichiers ou dossiers")
    scan.add_argument("paths", nargs="+")
    scan.add_argument("--db", action="append", default=[],
                      help="base de signatures supplementaire (.txt, .hdb, .hsb)")
    scan.add_argument("--quarantine", action="store_true",
                      help="mettre les fichiers infectes en quarantaine")
    scan.add_argument("--clamav", action="store_true", help="utiliser aussi le demon clamd")
    scan.add_argument("--clamd-socket", help="socket Unix de clamd")
    scan.add_argument("--clamd-host", default="127.0.0.1")
    scan.add_argument("--clamd-port", type=int, default=3310)
    scan.set_defaults(func=cmd_scan)

    quar = sub.add_parser("quarantine", help="gerer la quarantaine")
    group = quar.add_mutually_exclusive_group()
    group.add_argument("--restore", metavar="ID")
    group.add_argument("--delete", metavar="ID")
    quar.set_defaults(func=cmd_quarantine)

    gui = sub.add_parser("gui", help="ouvrir l'interface graphique")
    gui.set_defaults(func=lambda _args: __import__("freeav.gui", fromlist=["run"]).run())

    args = parser.parse_args(argv)
    return args.func(args) or 0
