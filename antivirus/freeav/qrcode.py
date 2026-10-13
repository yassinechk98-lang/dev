# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Petit generateur de QR code (norme ISO/IEC 18004), sans dependance.

Il ne sert qu'a afficher l'adresse otpauth:// de la connexion a FreeAV, pour l'ajouter dans
Google Authenticator ou Microsoft Authenticator : mode octet, niveau de correction M, versions
1 a 10 (jusqu'a 213 octets). make() renvoie une matrice de booleens (True = module noir), sans
la marge blanche de 4 modules que l'affichage doit ajouter autour.
"""

MAX_VERSION = 10
# Niveau M : octets de correction par bloc et nombre de blocs, pour les versions 1 a 10
ECC_PER_BLOCK = (None, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
BLOCKS = (None, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
FORMAT_LEVEL_M = 0b00


def _raw_modules(version: int) -> int:
    """Nombre de modules disponibles pour les donnees et la correction."""
    result = (16 * version + 128) * version + 64
    if version >= 2:
        aligns = version // 7 + 2
        result -= (25 * aligns - 10) * aligns - 55
        if version >= 7:
            result -= 36
    return result


def capacity(version: int) -> int:
    """Octets de donnees utiles en mode octet."""
    data_codewords = _raw_modules(version) // 8 - ECC_PER_BLOCK[version] * BLOCKS[version]
    count_bits = 8 if version < 10 else 16
    return (data_codewords * 8 - 4 - count_bits) // 8


def _alignment_positions(version: int, size: int) -> list[int]:
    if version == 1:
        return []
    aligns = version // 7 + 2
    step = (version * 4 + aligns * 2 + 1) // (aligns * 2 - 2) * 2
    return [6] + sorted(size - 7 - i * step for i in range(aligns - 1))


def _gf_mul(x: int, y: int) -> int:
    """Multiplication dans GF(256), polynome 0x11D."""
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _codewords(data: bytes, version: int) -> list[int]:
    """Donnees (en-tete, octets, bourrage), puis correction d'erreurs entrelacee."""
    raw = _raw_modules(version) // 8
    ecc_len, blocks = ECC_PER_BLOCK[version], BLOCKS[version]
    data_len = raw - ecc_len * blocks
    bits = [0, 1, 0, 0]  # mode octet
    count_bits = 8 if version < 10 else 16
    bits += [(len(data) >> i) & 1 for i in reversed(range(count_bits))]
    for byte in data:
        bits += [(byte >> i) & 1 for i in reversed(range(8))]
    bits += [0] * min(4, data_len * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    words += [pad[i % 2] for i in range(data_len - len(words))]

    short_blocks = blocks - raw % blocks
    short_len = raw // blocks
    divisor = _rs_divisor(ecc_len)
    split, k = [], 0
    for i in range(blocks):
        size = short_len - ecc_len + (0 if i < short_blocks else 1)
        part = words[k:k + size]
        k += size
        ecc = _rs_remainder(part, divisor)
        if i < short_blocks:
            part = part + [0]  # place vide, sautee a l'entrelacement
        split.append(part + ecc)
    out = []
    for i in range(len(split[0])):
        for j, block in enumerate(split):
            if i != short_len - ecc_len or j >= short_blocks:
                out.append(block[i])
    return out


MASKS = (
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


class _Matrix:
    def __init__(self, version: int):
        self.version = version
        self.size = version * 4 + 17
        self.dark = [[False] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]

    def set(self, x: int, y: int, dark: bool) -> None:
        self.dark[y][x] = dark
        self.function[y][x] = True

    def draw_patterns(self) -> None:
        size = self.size
        for i in range(size):  # lignes de synchronisation
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):  # reperes des coins
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        self.set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        positions = _alignment_positions(self.version, size)
        last = len(positions) - 1
        for i, cx in enumerate(positions):  # motifs d'alignement
            for j, cy in enumerate(positions):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0)
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                bit = (bits >> i) & 1 == 1
                a, b = size - 11 + i % 3, i // 3
                self.set(a, b, bit)
                self.set(b, a, bit)

    def draw_format(self, mask: int) -> None:
        data = FORMAT_LEVEL_M << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: (bits >> i) & 1 == 1
        size = self.size
        for i in range(6):
            self.set(8, i, bit(i))
        self.set(8, 7, bit(6))
        self.set(8, 8, bit(7))
        self.set(7, 8, bit(8))
        for i in range(9, 15):
            self.set(14 - i, 8, bit(i))
        for i in range(8):
            self.set(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set(8, size - 15 + i, bit(i))
        self.set(8, size - 8, True)  # module toujours noir

    def draw_codewords(self, words: list[int]) -> None:
        i, size = 0, self.size
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(size):
                for j in range(2):
                    x = right - j
                    upward = (right + 1) & 2 == 0
                    y = size - 1 - vert if upward else vert
                    if not self.function[y][x] and i < len(words) * 8:
                        self.dark[y][x] = (words[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        test = MASKS[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.function[y][x] and test(x, y):
                    self.dark[y][x] = not self.dark[y][x]


def _penalty(grid: list[list[bool]]) -> int:
    """Score de lisibilite de la norme (plus il est bas, mieux le QR se lit)."""
    size = len(grid)
    score = 0
    lines = grid + [list(col) for col in zip(*grid)]
    finder_a = [True, False, True, True, True, False, True, False, False, False, False]
    finder_b = finder_a[::-1]
    for line in lines:
        run, prev = 0, None
        for cell in line:
            if cell == prev:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run, prev = 1, cell
        if run >= 5:
            score += run - 2
        for i in range(size - 10):
            if line[i:i + 11] in (finder_a, finder_b):
                score += 40
    for y in range(size - 1):
        for x in range(size - 1):
            if grid[y][x] == grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1]:
                score += 3
    dark = sum(map(sum, grid))
    total = size * size
    score += (abs(dark * 20 - total * 10) + total - 1) // total * 10 - 10
    return score


def make(text: str, mask: int | None = None) -> list[list[bool]]:
    """QR code du texte (UTF-8). Leve ValueError s'il est trop long."""
    data = text.encode("utf-8")
    version = next((v for v in range(1, MAX_VERSION + 1) if len(data) <= capacity(v)), None)
    if version is None:
        raise ValueError(f"texte trop long pour le QR code ({len(data)} octets)")
    words = _codewords(data, version)
    best = None
    for candidate in range(8) if mask is None else (mask,):
        matrix = _Matrix(version)
        matrix.draw_patterns()
        matrix.draw_codewords(words)
        matrix.apply_mask(candidate)
        matrix.draw_format(candidate)
        score = _penalty(matrix.dark)
        if best is None or score < best[0]:
            best = (score, matrix.dark)
    return best[1]
