"""Base de signatures : empreintes de fichiers malveillants connus.

Formats acceptes (une signature par ligne, '#' pour les commentaires) :
  - format FreeAV :   sha256:<empreinte>:<nom>   ou   md5:<empreinte>:<nom>
  - format ClamAV .hdb : <md5>:<taille>:<nom>
  - format ClamAV .hsb : <sha256>:<taille>:<nom>
Cela permet de charger directement des bases de hachage ClamAV.
"""

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "data" / "signatures.txt"


@dataclass
class SignatureDB:
    sha256: dict[str, str] = field(default_factory=dict)
    md5: dict[str, str] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.sha256) + len(self.md5)

    def add(self, digest: str, name: str) -> None:
        digest = digest.strip().lower()
        if len(digest) == 64:
            self.sha256[digest] = name
        elif len(digest) == 32:
            self.md5[digest] = name
        else:
            raise ValueError(f"Empreinte invalide : {digest!r}")

    def load_file(self, path: Path) -> int:
        """Charge un fichier de signatures et retourne le nombre ajoute."""
        count = 0
        for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 3:
                raise ValueError(f"{path}:{lineno} : ligne mal formee")
            if parts[0].lower() in ("sha256", "md5"):
                digest, name = parts[1], ":".join(parts[2:])
            else:  # format ClamAV : empreinte:taille:nom
                digest, name = parts[0], parts[2]
            self.add(digest, name)
            count += 1
        return count

    def lookup(self, sha256: str, md5: str) -> str | None:
        return self.sha256.get(sha256) or self.md5.get(md5)


def load_default(extra: list[Path] | None = None) -> SignatureDB:
    db = SignatureDB()
    db.load_file(DEFAULT_DB)
    for path in extra or []:
        db.load_file(path)
    return db
