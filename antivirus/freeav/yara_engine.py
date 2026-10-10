"""Moteur YARA optionnel : applique des regles open source (fichiers .yar / .yara).

Exemples de collections a deposer dans ~/.freeav/yara ou a passer avec --yara :
  - https://github.com/Yara-Rules/rules            (GPL-2.0)
  - https://github.com/Neo23x0/signature-base     (DRL 1.1)
  - https://github.com/elastic/protections-artifacts (Elastic License 2.0)
Necessite le paquet yara-python ; sans lui, ce moteur est simplement desactive.
"""

from pathlib import Path

try:
    import yara
except ImportError:  # moteur optionnel
    yara = None

RULE_SUFFIXES = {".yar", ".yara"}


def available() -> bool:
    return yara is not None


class YaraEngine:
    def __init__(self, sources: list[Path]):
        if yara is None:
            raise RuntimeError("yara-python n'est pas installe (pip install yara-python)")
        valid: dict[str, str] = {}
        self.rejected: list[tuple[Path, str]] = []
        for source in sources:
            source = Path(source)
            files = [source] if source.is_file() else sorted(
                p for p in source.rglob("*") if p.suffix.lower() in RULE_SUFFIXES)
            for rule_file in files:
                # Chaque fichier est d'abord verifie seul : une regle invalide (ou qui
                # demande un module absent) n'empeche pas les autres de fonctionner.
                try:
                    yara.compile(filepath=str(rule_file))
                except yara.Error as exc:
                    self.rejected.append((rule_file, str(exc)))
                    continue
                valid[f"r{len(valid)}_{rule_file.stem}"] = str(rule_file)
        self.count = len(valid)
        # Puis tout est compile ensemble, pour analyser chaque fichier en une seule passe.
        self.rules = yara.compile(filepaths=valid) if valid else None

    def __len__(self) -> int:
        return self.count

    def __bool__(self) -> bool:
        return self.rules is not None

    def match(self, path: Path) -> str | None:
        if self.rules is None:
            return None
        matches = self.rules.match(str(path), timeout=30)
        return f"YARA.{matches[0].rule}" if matches else None
