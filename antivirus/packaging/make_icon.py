# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Yassine

"""Genere l'icone de FreeAV (bouclier vert avec une coche) en .ico multi-tailles."""

import sys

from PIL import Image, ImageDraw

SIZE = 256


def draw() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shield = [(128, 14), (226, 50), (218, 140), (186, 196), (128, 242), (70, 196), (38, 140), (30, 50)]
    d.polygon(shield, fill=(22, 128, 82, 255))
    inner = [(128, 34), (206, 63), (199, 138), (172, 184), (128, 220), (84, 184), (57, 138), (50, 63)]
    d.polygon(inner, fill=(36, 176, 112, 255))
    d.line([(84, 128), (116, 162), (176, 92)], fill=(255, 255, 255, 255), width=24, joint="curve")
    return img


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "freeav.ico"
    draw().save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icone ecrite : {out}")
