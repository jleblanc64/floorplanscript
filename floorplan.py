"""
floorplan.py - a tiny, deterministic floor-plan drawing library.

Designed so that an AI (or a human) can turn a hand-drawn sketch into a short,
readable sequence of calls that always renders cleanly and consistently.

CONVENTIONS (read this before generating calls)
------------------------------------------------
* Units are centimeters. y grows UPWARDS (standard math axes, not screen axes).
* Every rectangle-like element (wall, opening, door, window) is anchored at its
  BOTTOM-LEFT corner (x, y) and extends in the +x / +y direction.
    - horizontal=True  -> spans x..x+length  and  y..y+thickness
    - horizontal=False -> spans x..x+thickness and y..y+length
  So a vertical wall "goes up" from (x, y); a horizontal wall "goes right".
* Openings/doors/windows are drawn *over* a wall: give them the same x (or y)
  and the same thickness as the wall they sit in.
* Dimensions are double-headed arrows with end ticks. They measure a length
  starting at (x, y) going right (horizontal) or up (vertical). `offset` shifts
  the arrow sideways so it sits beside the thing it measures.
* Text default: centered, horizontal. Use rotation=90 for vertical labels.
* Walls that touch/overlap are drawn as one continuous shape: outlines are
  only drawn where they're not inside another wall. Overlapping is fine,
  but don't draw the exact same wall twice.
* All text sizes are multiplied by the module global FONT_SIZE_MULTIPLIER
  (default 1). Set it before drawing: `floorplan.FONT_SIZE_MULTIPLIER = 1.5`.

MINIMAL EXAMPLE
---------------
    from floorplan import FloorPlan
    p = FloorPlan()
    p.wall(0, 0, 300, horizontal=True)          # bottom wall
    p.wall(0, 0, 250, horizontal=False)         # left wall
    p.opening(0, 100, 80, horizontal=False)     # 80 cm gap in the left wall
    p.dimension(0, 100, 80, horizontal=False, offset=-40)
    p.room_label(150, 125, "Kitchen")
    p.save("plan.png")
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Arc, Polygon

# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
FONT_SIZE_MULTIPLIER = 2  # scales every text size in the drawing (1 = default)
WALL_THICKNESS = 20      # default wall thickness (cm)
WALL_FILL = "#e9ecf2"    # light fill behind the hatch
WALL_HATCH = "///"       # matplotlib hatch pattern
WALL_EDGE = "#1c2b4a"    # dark blue outline
WALL_EDGE_WIDTH = 1.6
OPENING_FILL = "#ff0000"
FLOOR_FILL = "#f4f5f8"
TEXT_COLOR = "#1c2b4a"
DIM_COLOR = "#1c2b4a"     # arrows and ticks
DIM_TEXT_COLOR = "#ff0000"  # dimension labels (red, readable over hatching)
LABEL_BOX = dict(boxstyle="round,pad=0.25", facecolor="white",
                 edgecolor="none", alpha=0.9)  # backing box behind labels
FONT = "DejaVu Sans"


def _fs(size: float) -> float:
    """Apply the global font multiplier to a base font size."""
    return size * FONT_SIZE_MULTIPLIER


class FloorPlan:
    """A single drawing. Create one, call drawing methods, then save()/show()."""

    def __init__(self, width_cm: float | None = None, height_cm: float | None = None,
                 scale: float = 0.02, title: str | None = None):
        """
        width_cm/height_cm : fixed drawing extents. If omitted, the figure
                             auto-fits everything drawn (with a small margin).
        scale              : inches per cm (0.02 -> a 500 cm room ~ 10 in wide).
        """
        self._scale = scale
        self._fixed = (width_cm, height_cm) if width_cm and height_cm else None
        self._items = []          # (xmin, ymin, xmax, ymax) for auto-fit
        self._walls = []          # wall rectangles, merged at draw time
        self.fig, self.ax = plt.subplots()
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.fig.patch.set_facecolor("white")
        if title:
            self.ax.set_title(title, fontsize=_fs(12), color=TEXT_COLOR,
                              fontname=FONT)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _track(self, x0, y0, x1, y1):
        self._items.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    @staticmethod
    def _rect(x, y, length, horizontal, thickness):
        """Return (x, y, w, h) of an anchored rectangle."""
        if horizontal:
            return x, y, length, thickness
        return x, y, thickness, length

    # ------------------------------------------------------------------ #
    # Structural elements
    # ------------------------------------------------------------------ #
    def wall(self, x: float, y: float, length: float, horizontal: bool = True,
             thickness: float = WALL_THICKNESS):
        """Hatched wall anchored at bottom-left (x, y)."""
        rx, ry, w, h = self._rect(x, y, length, horizontal, thickness)
        self._walls.append((rx, ry, w, h))   # drawn merged in _finalize()
        self._track(rx, ry, rx + w, ry + h)
        return self

    def _draw_walls(self):
        """Draw all walls as one continuous shape without extra dependencies:
        hatched fills first (no outline), then only the outline segments that
        do not lie inside/on another wall, so junctions have no seams."""
        if not self._walls:
            return
        rects = [(rx, ry, rx + w, ry + h) for rx, ry, w, h in self._walls]

        # 1) fills + hatch, no visible edge (edgecolor still drives hatch color)
        for x0, y0, x1, y1 in rects:
            self.ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                                        facecolor=WALL_FILL, edgecolor=WALL_EDGE,
                                        hatch=WALL_HATCH, linewidth=0, zorder=2))

        # 2) outline: a piece of a wall edge is drawn only if exactly one of
        #    its two sides is inside some wall (true boundary of the union)
        d = 1e-3

        def inside(px, py):
            return any(x0 < px < x1 and y0 < py < y1 for x0, y0, x1, y1 in rects)

        def draw(axis, c, a, b):
            cuts = {a, b}
            for x0, y0, x1, y1 in rects:
                for v in ((x0, x1) if axis == "y" else (y0, y1)):
                    if a < v < b:
                        cuts.add(v)
            cuts = sorted(cuts)
            for a2, b2 in zip(cuts, cuts[1:]):
                m = (a2 + b2) / 2
                if axis == "y":
                    one, two = inside(m, c + d), inside(m, c - d)
                    xs, ys = [a2, b2], [c, c]
                else:
                    one, two = inside(c + d, m), inside(c - d, m)
                    xs, ys = [c, c], [a2, b2]
                if one != two:
                    self.ax.plot(xs, ys, color=WALL_EDGE, linewidth=WALL_EDGE_WIDTH,
                                 solid_capstyle="projecting", zorder=2.5)

        for x0, y0, x1, y1 in rects:
            draw("y", y0, x0, x1)
            draw("y", y1, x0, x1)
            draw("x", x0, y0, y1)
            draw("x", x1, y0, y1)

    def opening(self, x: float, y: float, length: float, horizontal: bool = True,
                thickness: float = WALL_THICKNESS):
        """Plain opening (no door) drawn as a dark block over the wall."""
        rx, ry, w, h = self._rect(x, y, length, horizontal, thickness)
        self.ax.add_patch(Rectangle((rx, ry), w, h, facecolor=OPENING_FILL,
                                    edgecolor=OPENING_FILL, linewidth=0, zorder=3))
        self._track(rx, ry, rx + w, ry + h)
        return self

    def door(self, x: float, y: float, length: float, horizontal: bool = True,
             thickness: float = WALL_THICKNESS, swing: str = "left",
             flip: bool = False):
        """
        Door: white gap in the wall + leaf line + quarter-circle swing arc.
        swing : hinge side, "left"/"right" (horizontal wall) or
                "bottom"/"top" (vertical wall). Synonyms accepted.
        flip  : mirror the swing to the other side of the wall.
        """
        rx, ry, w, h = self._rect(x, y, length, horizontal, thickness)
        # cut the wall
        self.ax.add_patch(Rectangle((rx, ry), w, h, facecolor="white",
                                    edgecolor="white", linewidth=0, zorder=3))
        hinge_start = swing in ("left", "bottom", "start")
        side = -1 if flip else 1
        if horizontal:
            hx = x if hinge_start else x + length
            hy = y + thickness if side == 1 else y
            dx = length if hinge_start else -length
            # leaf
            self.ax.plot([hx, hx], [hy, hy + side * length], color=WALL_EDGE,
                         linewidth=WALL_EDGE_WIDTH, zorder=4)
            # arc from leaf tip to wall edge
            if side == 1:
                t1, t2 = (0, 90) if hinge_start else (90, 180)
            else:
                t1, t2 = (270, 360) if hinge_start else (180, 270)
            self.ax.add_patch(Arc((hx, hy), 2 * length, 2 * length, theta1=t1,
                                  theta2=t2, color=WALL_EDGE, linewidth=1,
                                  linestyle="--", zorder=4))
            self._track(min(hx, hx + dx), min(hy, hy + side * length),
                        max(hx, hx + dx), max(hy, hy + side * length))
        else:
            hy = y if hinge_start else y + length
            hx = x + thickness if side == 1 else x
            dy = length if hinge_start else -length
            self.ax.plot([hx, hx + side * length], [hy, hy], color=WALL_EDGE,
                         linewidth=WALL_EDGE_WIDTH, zorder=4)
            if side == 1:
                t1, t2 = (0, 90) if hinge_start else (270, 360)
            else:
                t1, t2 = (90, 180) if hinge_start else (180, 270)
            self.ax.add_patch(Arc((hx, hy), 2 * length, 2 * length, theta1=t1,
                                  theta2=t2, color=WALL_EDGE, linewidth=1,
                                  linestyle="--", zorder=4))
            self._track(min(hx, hx + side * length), min(hy, hy + dy),
                        max(hx, hx + side * length), max(hy, hy + dy))
        return self

    def window(self, x: float, y: float, length: float, horizontal: bool = True,
               thickness: float = WALL_THICKNESS):
        """Window: white gap with a thin double line through it."""
        rx, ry, w, h = self._rect(x, y, length, horizontal, thickness)
        self.ax.add_patch(Rectangle((rx, ry), w, h, facecolor="white",
                                    edgecolor=WALL_EDGE, linewidth=WALL_EDGE_WIDTH,
                                    zorder=3))
        for f in (1 / 3, 2 / 3):
            if horizontal:
                yy = ry + h * f
                self.ax.plot([rx, rx + w], [yy, yy], color=WALL_EDGE,
                             linewidth=0.8, zorder=4)
            else:
                xx = rx + w * f
                self.ax.plot([xx, xx], [ry, ry + h], color=WALL_EDGE,
                             linewidth=0.8, zorder=4)
        self._track(rx, ry, rx + w, ry + h)
        return self

    def floor(self, x: float, y: float, width: float, height: float,
              color: str = FLOOR_FILL):
        """Optional light fill for a room interior (draw before walls/labels)."""
        self.ax.add_patch(Rectangle((x, y), width, height, facecolor=color,
                                    edgecolor="none", zorder=1))
        self._track(x, y, x + width, y + height)
        return self

    # ------------------------------------------------------------------ #
    # Annotation
    # ------------------------------------------------------------------ #
    def text(self, x: float, y: float, text: str, rotation: float = 0,
             size: float = 9, bold: bool = False, ha: str = "center",
             va: str = "center", color: str = TEXT_COLOR, boxed: bool = False):
        """Free text centered at (x, y). rotation=90 for vertical text.
        boxed=True adds a white backing box (use when text sits on a wall).
        `size` is multiplied by FONT_SIZE_MULTIPLIER."""
        self.ax.text(x, y, text, rotation=rotation, fontsize=_fs(size),
                     fontname=FONT, color=color, ha=ha, va=va,
                     fontweight="bold" if bold else "normal",
                     bbox=LABEL_BOX if boxed else None, zorder=6)
        self._track(x, y, x, y)
        return self

    def room_label(self, x: float, y: float, name: str, rotation: float = 0):
        """Larger label for a room name."""
        return self.text(x, y, name, rotation=rotation, size=13)

    def dimension(self, x: float, y: float, length: float, horizontal: bool = True,
                  offset: float = 0, label: str | None = None,
                  unit: str = "cm", size: float = 8, flip_label: bool = False):
        """
        Double-headed measurement arrow with end ticks.
        Starts at (x, y) and spans `length` to the right / upward.
        offset : perpendicular shift (+ = up for horizontal, + = right for vertical).
        label  : text; defaults to f"{length:g} {unit}". Use "" for no label.
        size   : label font size (multiplied by FONT_SIZE_MULTIPLIER).
        flip_label : put the label on the other side of the arrow
                     (below instead of above / right instead of left).
        """
        if label is None:
            label = f"{length:g} {unit}"
        tick = 6
        if horizontal:
            yy = y + offset
            x1, x2 = x, x + length
            self.ax.annotate("", xy=(x2, yy), xytext=(x1, yy),
                             arrowprops=dict(arrowstyle="<->", color=DIM_COLOR,
                                             lw=1, shrinkA=0, shrinkB=0), zorder=5)
            for xx in (x1, x2):
                self.ax.plot([xx, xx], [yy - tick, yy + tick], color=DIM_COLOR,
                             lw=1, zorder=5)
            if label:
                ly, va = ((yy - tick - 2, "top") if flip_label
                          else (yy + tick + 2, "bottom"))
                self.ax.text((x1 + x2) / 2, ly, label, ha="center", va=va,
                             fontsize=_fs(size), fontname=FONT,
                             color=DIM_TEXT_COLOR, bbox=LABEL_BOX, zorder=6)
            self._track(x1, yy - tick, x2, yy + tick + 12)
        else:
            xx = x + offset
            y1, y2 = y, y + length
            self.ax.annotate("", xy=(xx, y2), xytext=(xx, y1),
                             arrowprops=dict(arrowstyle="<->", color=DIM_COLOR,
                                             lw=1, shrinkA=0, shrinkB=0), zorder=5)
            for yy in (y1, y2):
                self.ax.plot([xx - tick, xx + tick], [yy, yy], color=DIM_COLOR,
                             lw=1, zorder=5)
            if label:
                lx, ha = ((xx + tick + 2, "left") if flip_label
                          else (xx - tick - 2, "right"))
                self.ax.text(lx, (y1 + y2) / 2, label, ha=ha, va="center",
                             fontsize=_fs(size), fontname=FONT,
                             color=DIM_TEXT_COLOR, bbox=LABEL_BOX, zorder=6)
            self._track(xx - tick - 40, y1, xx + tick, y2)
        return self

    def line(self, x0: float, y0: float, x1: float, y1: float,
             dashed: bool = False, width: float = 1.0):
        """Generic thin line (e.g. for a break line or guide)."""
        self.ax.plot([x0, x1], [y0, y1], color=WALL_EDGE, linewidth=width,
                     linestyle="--" if dashed else "-", zorder=4)
        self._track(x0, y0, x1, y1)
        return self

    def north_arrow(self, x: float, y: float, size: float = 40):
        """Small north indicator with its tip at (x, y+size)."""
        pts = [(x, y + size), (x - size * 0.3, y), (x, y + size * 0.25),
               (x + size * 0.3, y)]
        self.ax.add_patch(Polygon(pts, closed=True, facecolor=WALL_EDGE,
                                  edgecolor=WALL_EDGE, zorder=6))
        self.text(x, y + size + 10, "N", size=9, bold=True)
        return self

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #
    def _finalize(self, margin: float = 30):
        self._draw_walls()
        self._walls = []
        if self._fixed:
            w, h = self._fixed
            xmin, ymin, xmax, ymax = -margin, -margin, w + margin, h + margin
        elif self._items:
            xmin = min(i[0] for i in self._items) - margin
            ymin = min(i[1] for i in self._items) - margin
            xmax = max(i[2] for i in self._items) + margin
            ymax = max(i[3] for i in self._items) + margin
        else:
            xmin, ymin, xmax, ymax = 0, 0, 100, 100
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.fig.set_size_inches((xmax - xmin) * self._scale,
                                 (ymax - ymin) * self._scale)

    def save(self, path: str = "plan.png", dpi: int = 200):
        """Write the drawing to a PNG/SVG/PDF file (chosen by extension)."""
        self._finalize()
        self.fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
        return path

    def show(self):
        self._finalize()
        plt.show()