"""Point d'entree de FreeAV.exe : ouvre l'interface graphique, ou la ligne de commande
si des arguments sont donnes (par exemple : FreeAV.exe scan C:\\Users\\moi\\Downloads)."""

import sys

from freeav.cli import main
from freeav.gui import run

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(main())
    run()
