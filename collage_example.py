"""
Example generated from the sketched template:

    +--------+--------+
    |   A    |   B    |
    +--------+--------+
    |        C        |
    +-----------------+

Only main() contains template-specific code. Edit the file paths at the top of main().
Requires collage.py in the same folder (or on PYTHONPATH) and Pillow.
"""
import os
from pathlib import Path

from collage import make_collage

folder = Path("~/Pictures").expanduser()

def main():
    # ---- input files (edit these) ----
    A = folder / "ouverture1.png"
    B = folder / "ouverture2.png"
    C = folder / "SS.jpeg"
    OUTPUT = folder / "collage_out.png"

    # ---- template derived from the picture ----
    make_collage(
        "AB/CC",
        {"A": A, "B": B, "C": C},
        size=(1220, 1080),
        gap=12,
        margin=20,
        background="#e0e0e0",
        fit="stretch",
        row_heights=[0.5, 0.5],
        title_top="Détails ouvertures",
        title_bottom="Plan Sous-Sol",
    ).save(OUTPUT)
    print("wrote", OUTPUT)


if __name__ == "__main__":
    main()