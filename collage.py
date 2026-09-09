"""
collage.py — a tiny, declarative library for assembling N images into one picture.

Dependency: Pillow  (pip install pillow)

QUICK START
-----------
    from collage import make_collage

    # ASCII template: each letter is a cell, repeated letters merge into one area.
    # Rows are separated by "/" or newlines. This is the "A B on top, C across the bottom" layout:
    make_collage("AB/CC", {"A": "a.jpg", "B": "b.jpg", "C": "c.jpg"},
                 size=(1920, 1080), gap=12, background="white").save("out.png")

    # Or positionally (letters are assigned A, B, C, ... in order of first appearance):
    make_collage("AB/CC", ["a.jpg", "b.jpg", "c.jpg"]).save("out.png")

    # Optional titles: title_top is drawn in red above, title_bottom below the pictures.
    make_collage("AB/CC", ["a.jpg", "b.jpg", "c.jpg"],
                 title_top="Ouverture mur atelier", title_bottom="Plan RDC").save("out.png")

TEMPLATES (ASCII)
-----------------
    "AB"          two side by side           "A/B"      two stacked
    "AB/CC"       two on top, one below      "AA/BC"    one on top, two below
    "AB/CD"       2x2 grid                   "ABC/DEF"  2x3 grid
    "AAB/AAC"     big left, two small right  "ABB/ACC"  ...any rectangular spans work
    "A.B"         "." (or " ") = empty cell

    Any letter/digit can be used. Every letter must cover a full rectangle.
    Rows are equal height by default; use row_heights=[0.4, 0.6] to change (col_weights for
    columns in non-justified grids).
    By default rows are justified: all rows share the height equally and each row's pictures
    fill the full width, widths proportional to their aspect ratios (justify=False -> rigid grid).

TREE LAYOUTS (for anything a grid can't express)
------------------------------------------------
    from collage import Collage, Row, Col, Img

    layout = Col([                          # top-to-bottom
        Row([Img("a.jpg"), Img("b.jpg")]),  # left-to-right
        Img("c.jpg"),
    ], weights=[1, 1])                      # relative sizes of children (optional)
    Collage(layout, size=(1600, 1200), gap=10).save("out.png")

IMAGE FITTING
-------------
    Img(src, fit="cover")    crop to fill the cell, keep aspect ratio (default)
    Img(src, fit="contain")  letterbox inside the cell, keep aspect ratio
    Img(src, fit="stretch")  distort to fill the cell
    Img(src, align=(0.5, 0.0)) -> anchor point used for cropping/placing (x, y in 0..1)
    src may be a file path or a PIL.Image.Image.

CLI
---
    python collage.py --template "AB/CC" a.jpg b.jpg c.jpg -o out.png --size 1920x1080 --gap 10
"""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

__all__ = [
    "Collage", "Row", "Col", "Img", "Blank", "Grid",
    "make_collage", "parse_template", "load_image", "PRESETS",
]

PathOrImage = Union[str, "os.PathLike", Image.Image]
Box = Tuple[int, int, int, int]  # x, y, w, h

# Handy named templates an AI can reference by name.
PRESETS: Dict[str, str] = {
    "pair": "AB",
    "stack": "A/B",
    "two_top_one_bottom": "AB/CC",
    "one_top_two_bottom": "AA/BC",
    "big_left": "AAB/AAC",
    "big_right": "ABB/CBB",
    "grid_2x2": "AB/CD",
    "grid_2x3": "ABC/DEF",
    "grid_3x3": "ABC/DEF/GHI",
    "triptych": "ABC",
    "feature_top": "AAA/BCD",
}


# --------------------------------------------------------------------------- #
# Image helpers
# --------------------------------------------------------------------------- #
def load_image(src: PathOrImage) -> Image.Image:
    """Open a path (or pass a PIL image through), fix EXIF rotation, return RGBA."""
    im = src if isinstance(src, Image.Image) else Image.open(src)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGBA")


def _color(c, default="white") -> Tuple[int, int, int, int]:
    if c is None:
        c = default
    if isinstance(c, str):
        return ImageColor.getcolor(c, "RGBA")
    return tuple(c) if len(c) == 4 else (*c, 255)


_FONT_CANDIDATES = [
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arial.ttf",
]


def _font(size: int, path: Optional[str] = None) -> ImageFont.ImageFont:
    """Best-effort TrueType font; falls back to Pillow's built-in font."""
    for cand in ([path] if path else []) + _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:            # old Pillow: no size argument
        return ImageFont.load_default()


def fit_image(im: Image.Image, size: Tuple[int, int], fit: str = "cover",
              align: Tuple[float, float] = (0.5, 0.5), background=None) -> Image.Image:
    """Return a new image of exactly `size` built from `im` using the chosen fit mode."""
    w, h = max(1, size[0]), max(1, size[1])
    if fit == "cover":
        return ImageOps.fit(im, (w, h), method=Image.LANCZOS, centering=align)
    if fit == "stretch":
        return im.resize((w, h), Image.LANCZOS)
    if fit == "contain":
        scale = min(w / im.width, h / im.height)
        nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
        resized = im.resize((nw, nh), Image.LANCZOS)
        out = Image.new("RGBA", (w, h), _color(background, (0, 0, 0, 0)))
        out.paste(resized, (round((w - nw) * align[0]), round((h - nh) * align[1])), resized)
        return out
    raise ValueError(f"unknown fit mode {fit!r} (use cover | contain | stretch)")


def _split(length: int, weights: Sequence[float], gap: int) -> List[Tuple[int, int]]:
    """Split `length` into segments proportional to weights, with `gap` between them.
    Returns [(offset, size), ...] with exact integer coverage."""
    n = len(weights)
    total_w = float(sum(weights))
    usable = length - gap * (n - 1)
    edges, acc = [0], 0.0
    for wgt in weights:
        acc += usable * wgt / total_w
        edges.append(round(acc))
    segs = []
    for i in range(n):
        start = edges[i] + gap * i
        segs.append((start, max(0, edges[i + 1] - edges[i])))
    return segs


# --------------------------------------------------------------------------- #
# Layout nodes
# --------------------------------------------------------------------------- #
class Node:
    """Base layout node. `weight` is the node's relative size inside its parent."""
    weight: float = 1.0

    def render(self, canvas: Image.Image, box: Box, ctx: "Collage") -> None:
        raise NotImplementedError


@dataclass
class Blank(Node):
    """An empty cell (shows the background)."""
    weight: float = 1.0

    def render(self, canvas, box, ctx):
        pass


@dataclass
class Img(Node):
    """A single image cell."""
    src: PathOrImage
    fit: str = "cover"                       # cover | contain | stretch
    align: Tuple[float, float] = (0.5, 0.5)  # crop/placement anchor, (0,0)=top-left, (1,1)=bottom-right
    weight: float = 1.0
    background: Optional[str] = None         # fill for 'contain' mode; defaults to collage background
    radius: int = 0                          # rounded-corner radius in px (0 = square)
    border: int = 0                          # border width in px
    border_color: str = "black"

    def render(self, canvas, box, ctx):
        x, y, w, h = box
        if w <= 0 or h <= 0:
            return
        im = load_image(self.src)
        tile = fit_image(im, (w, h), self.fit, self.align,
                         self.background or ctx.background)
        if self.border:
            from PIL import ImageDraw
            d = ImageDraw.Draw(tile)
            for i in range(self.border):
                d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=_color(self.border_color))
        if self.radius:
            from PIL import ImageDraw
            mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], self.radius, fill=255)
            canvas.paste(tile, (x, y), mask)
        else:
            canvas.paste(tile, (x, y), tile)


@dataclass
class _Split(Node):
    children: List[Node]
    weights: Optional[Sequence[float]] = None
    weight: float = 1.0
    gap: Optional[int] = None      # override collage gap inside this container
    axis: str = field(default="x", init=False)

    def _weights(self):
        if self.weights is not None:
            if len(self.weights) != len(self.children):
                raise ValueError("weights length must match number of children")
            return list(self.weights)
        return [getattr(c, "weight", 1.0) for c in self.children]

    def render(self, canvas, box, ctx):
        x, y, w, h = box
        gap = ctx.gap if self.gap is None else self.gap
        if not self.children:
            return
        if self.axis == "x":
            for child, (off, size) in zip(self.children, _split(w, self._weights(), gap)):
                child.render(canvas, (x + off, y, size, h), ctx)
        else:
            for child, (off, size) in zip(self.children, _split(h, self._weights(), gap)):
                child.render(canvas, (x, y + off, w, size), ctx)


@dataclass
class Row(_Split):
    """Children laid out left-to-right."""
    def __post_init__(self):
        self.axis = "x"


@dataclass
class Col(_Split):
    """Children laid out top-to-bottom."""
    def __post_init__(self):
        self.axis = "y"


# --------------------------------------------------------------------------- #
# ASCII grid templates
# --------------------------------------------------------------------------- #
def parse_template(spec: str) -> Tuple[List[str], Dict[str, Tuple[int, int, int, int]]]:
    """Parse an ASCII template into (rows, {label: (col, row, colspan, rowspan)}).

    Rows are separated by '/' or newlines; blanks are '.' or ' ' (spaces inside a row are
    only treated as blanks if the row contains no other separators). Every label must
    occupy a solid rectangle."""
    spec = PRESETS.get(spec, spec)
    rows = [r for r in re.split(r"[/\n]", spec)]
    rows = [r.strip() if "/" in spec or "\n" in spec else r for r in rows]
    rows = [r for r in rows if r != ""]
    if not rows:
        raise ValueError("empty template")
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, ".") for r in rows]
    cells: Dict[str, List[Tuple[int, int]]] = {}
    for ry, row in enumerate(rows):
        for cx, ch in enumerate(row):
            if ch in ". ":
                continue
            cells.setdefault(ch, []).append((cx, ry))
    areas = {}
    for label, pts in cells.items():
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        c0, c1, r0, r1 = min(xs), max(xs), min(ys), max(ys)
        if len(pts) != (c1 - c0 + 1) * (r1 - r0 + 1):
            raise ValueError(f"template label {label!r} does not form a rectangle")
        areas[label] = (c0, r0, c1 - c0 + 1, r1 - r0 + 1)
    return rows, areas


@dataclass
class Grid(Node):
    """A grid node driven by an ASCII template.

    template : e.g. "AB/CC"  (or a PRESETS key such as "two_top_one_bottom")
    cells    : {label: Node | path | PIL image}  or  a list/tuple assigned in label order
    justify  : True (default) -> every row has the same height and the pictures of a row
               share the full width in proportion to their aspect ratios, so each row is
               filled edge to edge (pictures are lightly reshaped by the cell's fit mode).
               False -> classic fixed grid with equal columns (or col_weights / row_weights).
               Justify is only possible when no cell spans several rows; otherwise the
               classic grid is used.
    """
    template: str
    cells: Union[Dict[str, Union[Node, PathOrImage]], Sequence[Union[Node, PathOrImage]]]
    col_weights: Optional[Sequence[float]] = None
    row_weights: Optional[Sequence[float]] = None
    weight: float = 1.0
    gap: Optional[int] = None
    justify: bool = True
    row_heights: Optional[Sequence[float]] = None   # e.g. [0.4, 0.6]; alias of row_weights

    def _row_w(self, nrows):
        rw = self.row_heights if self.row_heights is not None else self.row_weights
        if rw is None:
            return [1] * nrows
        if len(rw) != nrows:
            raise ValueError(f"row_heights has {len(rw)} values but template has {nrows} rows")
        return list(rw)

    def _mapping(self, labels):
        if isinstance(self.cells, dict):
            return dict(self.cells)
        if len(self.cells) > len(labels):
            raise ValueError(f"template {self.template!r} has {len(labels)} cells "
                             f"but {len(self.cells)} images were given")
        return dict(zip(labels, self.cells))

    @staticmethod
    def _node(item):
        return item if isinstance(item, Node) else Img(item)

    def render(self, canvas, box, ctx):
        rows, areas = parse_template(self.template)
        ncols, nrows = len(rows[0]), len(rows)
        mapping = self._mapping(list(areas.keys()))
        gap = ctx.gap if self.gap is None else self.gap
        x, y, w, h = box

        can_justify = self.justify and self.col_weights is None and \
                      all(rs == 1 for (_, _, _, rs) in areas.values())

        if can_justify:
            rws = _split(h, self._row_w(nrows), gap)
            for r in range(nrows):
                in_row = sorted((a for a in areas.items() if a[1][1] == r),
                                key=lambda a: a[1][0])
                items = [(lab, self._node(mapping[lab])) for lab, _ in in_row
                         if mapping.get(lab) is not None]
                if not items:
                    continue
                ratios = []
                for lab, node in items:
                    if isinstance(node, Img):
                        im = load_image(node.src)
                        ratios.append(im.width / im.height)
                    else:
                        ratios.append(1.0)
                y0, rh = rws[r]
                for (lab, node), (off, cw) in zip(items, _split(w, ratios, gap)):
                    node.render(canvas, (x + off, y + y0, cw, rh), ctx)
            return

        cols = _split(w, self.col_weights or [1] * ncols, gap)
        rws = _split(h, self._row_w(nrows), gap)
        for label, (c0, r0, cs, rs) in areas.items():
            item = mapping.get(label)
            if item is None:
                continue
            x0 = x + cols[c0][0]
            y0 = y + rws[r0][0]
            x1 = x + cols[c0 + cs - 1][0] + cols[c0 + cs - 1][1]
            y1 = y + rws[r0 + rs - 1][0] + rws[r0 + rs - 1][1]
            self._node(item).render(canvas, (x0, y0, x1 - x0, y1 - y0), ctx)


# --------------------------------------------------------------------------- #
# Collage (the canvas)
# --------------------------------------------------------------------------- #
class Collage:
    """Renders a layout tree onto a canvas.

    size       : (width, height) of the output in pixels
    gap        : spacing between cells in px
    margin     : padding around the whole collage in px
    background : any Pillow color string / tuple, e.g. "white", "#222", (0,0,0,0) for transparent
    title_top / title_bottom : optional text centered above / below the pictures.
                 The top title is red, the bottom one dark grey (title_color_top/_bottom).
    title_size : font size in px (default ~4% of the height); title_font : path to a .ttf
    """

    def __init__(self, layout: Node, size: Tuple[int, int] = (1920, 1080), gap: int = 10,
                 margin: int = 0, background="white",
                 title_top: Optional[str] = None, title_bottom: Optional[str] = None,
                 title_size: Optional[int] = None, title_font: Optional[str] = None,
                 title_color_top="red", title_color_bottom="#222222"):
        self.layout = layout
        self.size = size
        self.gap = gap
        self.margin = margin
        self.background = background
        self.title_top = title_top
        self.title_bottom = title_bottom
        self.title_size = title_size
        self.title_font = title_font
        self.title_color_top = title_color_top
        self.title_color_bottom = title_color_bottom

    def _draw_title(self, canvas, text, y_center, color, font):
        draw = ImageDraw.Draw(canvas)
        W = canvas.width
        l, t, r, b = draw.textbbox((0, 0), text, font=font, align="center")
        tw, th = r - l, b - t
        draw.text(((W - tw) / 2 - l, y_center - th / 2 - t), text,
                  font=font, fill=_color(color), align="center")

    def render(self) -> Image.Image:
        W, H = self.size
        canvas = Image.new("RGBA", (W, H), _color(self.background))
        m = self.margin
        top, bottom = m, H - m
        if self.title_top or self.title_bottom:
            fs = self.title_size or max(12, round(H * 0.04))
            font = _font(fs, self.title_font)
            band = round(fs * 1.6)
            if self.title_top:
                nlines = self.title_top.count("\n") + 1
                bh = band + (nlines - 1) * round(fs * 1.2)
                self._draw_title(canvas, self.title_top, top + bh / 2,
                                 self.title_color_top, font)
                top += bh
            if self.title_bottom:
                nlines = self.title_bottom.count("\n") + 1
                bh = band + (nlines - 1) * round(fs * 1.2)
                self._draw_title(canvas, self.title_bottom, bottom - bh / 2,
                                 self.title_color_bottom, font)
                bottom -= bh
        self.layout.render(canvas, (m, top, W - 2 * m, bottom - top), self)
        return canvas

    def save(self, path, **kwargs) -> str:
        path = str(path)
        im = self.render()
        if path.lower().endswith((".jpg", ".jpeg")):
            bg = Image.new("RGB", im.size, _color(self.background)[:3])
            bg.paste(im, mask=im)
            bg.save(path, quality=kwargs.pop("quality", 92), **kwargs)
        else:
            im.save(path, **kwargs)
        return path


def make_collage(template: str,
                 images: Union[Dict[str, Union[Node, PathOrImage]], Sequence[Union[Node, PathOrImage]]],
                 size: Tuple[int, int] = (1920, 1080), gap: int = 10, margin: int = 0,
                 background="white", fit: str = "cover",
                 col_weights: Optional[Sequence[float]] = None,
                 row_weights: Optional[Sequence[float]] = None,
                 row_heights: Optional[Sequence[float]] = None,
                 justify: bool = True,
                 title_top: Optional[str] = None, title_bottom: Optional[str] = None,
                 title_size: Optional[int] = None) -> Collage:
    """One-liner: build a Collage from an ASCII template and a dict/list of images.

    title_top / title_bottom : text centered above (red) / below (dark grey) the pictures.
    title_size : title font size in px (default ~4% of the collage height).

    row_heights : fraction of the height per row, e.g. [0.4, 0.6] (same as row_weights).
    justify : True (default) -> rows share the height (per row_heights) and each row is filled
              edge to edge, widths shared in proportion to the pictures' aspect ratios.
              Combine with fit="stretch" to show whole pictures (lightly reshaped),
              fit="cover" to crop slightly instead, fit="contain" to letterbox.
              False -> rigid grid with equal columns.

    >>> make_collage("AB/CC", ["a.jpg", "b.jpg", "c.jpg"], fit="stretch").save("out.png")
    """
    def wrap(v):
        return v if isinstance(v, Node) else Img(v, fit=fit)
    cells = {k: wrap(v) for k, v in images.items()} if isinstance(images, dict) \
        else [wrap(v) for v in images]
    grid = Grid(template, cells, col_weights=col_weights, row_weights=row_weights,
                row_heights=row_heights, justify=justify)
    return Collage(grid, size=size, gap=gap, margin=margin, background=background,
                   title_top=title_top, title_bottom=title_bottom, title_size=title_size)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv=None):
    p = argparse.ArgumentParser(description="Assemble images into a collage from an ASCII template.")
    p.add_argument("images", nargs="+", help="image files, assigned to template labels in order")
    p.add_argument("-t", "--template", default="AB/CC",
                   help='ASCII template, e.g. "AB/CC", or a preset name: ' + ", ".join(PRESETS))
    p.add_argument("-o", "--output", default="collage.png")
    p.add_argument("--size", default="1920x1080", help="WIDTHxHEIGHT")
    p.add_argument("--gap", type=int, default=10)
    p.add_argument("--margin", type=int, default=0)
    p.add_argument("--background", default="white")
    p.add_argument("--fit", default="cover", choices=["cover", "contain", "stretch"])
    p.add_argument("--row-heights", default=None, help="comma list, e.g. 0.4,0.6")
    p.add_argument("--title-top", default=None, help="red title above the pictures")
    p.add_argument("--title-bottom", default=None, help="title below the pictures")
    p.add_argument("--no-justify", action="store_true", help="use a rigid equal-column grid")
    a = p.parse_args(argv)
    w, h = (int(v) for v in a.size.lower().split("x"))
    rh = [float(v) for v in a.row_heights.split(",")] if a.row_heights else None
    out = make_collage(a.template, a.images, size=(w, h), gap=a.gap, margin=a.margin,
                       background=a.background, fit=a.fit,
                       row_heights=rh, justify=not a.no_justify,
                       title_top=a.title_top, title_bottom=a.title_bottom).save(a.output)
    print(f"wrote {out}")


if __name__ == "__main__":
    _main()