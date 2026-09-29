"""
Mur de la cuisine - vue en élévation (face au mur, côté cuisine).
Here y = height above the floor (cm), x = position along the wall (cm).

Measured on the sketch:  opening 105 x 110 cm, sill at 90 cm,
                         62 cm between the door frame and the opening.
ASSUMED (not on sketch, adjust to your real values):
    DOOR_W, DOOR_H, CEILING, LEFT_W, RIGHT_W
"""
import os
import floorplan
from floorplan import FloorPlan

floorplan.FONT_SIZE_MULTIPLIER = 1.3

# Measurement style (opt-in; without these lines the library's
# original thin dark-blue style is used)
floorplan.DIM_COLOR = "#0a7d32"      # strong green: visible on the blue hatch, distinct from the red opening
floorplan.DIM_TEXT_COLOR = "#0a7d32"
floorplan.DIM_LINE_WIDTH = 2.2       # thicker arrow line
floorplan.DIM_ARROW_STYLE = "<|-|>"  # filled arrowheads
floorplan.DIM_HEAD = 14
floorplan.DIM_HALO = 4               # white outline so lines read over hatching
floorplan.DIM_TICK = 10              # longer end ticks
floorplan.DIM_EXTENSION = True       # lines from measured points to the arrow
floorplan.DIM_TEXT_BOLD = True

NAME = "~/Pictures/ouverture_cuisine.png"

# ---- values from the sketch -------------------------------------------
GAP = 62        # door frame -> opening
OPEN_W = 105    # opening width
OPEN_H = 110    # opening height
SILL = 90       # floor -> bottom of opening

# ---- assumptions (to verify on site) ----------------------------------
CEILING = 250   # floor-to-ceiling height
DOOR_W = 83     # door width
DOOR_H = 204    # door height
LEFT_W = 80     # wall left of the door
RIGHT_W = 150   # wall right of the opening (towards the terrace)

# ---- derived positions --------------------------------------------------
door_x = LEFT_W
door_r = door_x + DOOR_W          # right edge of the door frame
open_x = door_r + GAP
open_r = open_x + OPEN_W
open_top = SILL + OPEN_H
end_x = open_r + RIGHT_W

p = FloorPlan(title="Mur intérieur cuisine étage: nouvelle ouverture")
p.ax.title.set_color("#d40000")                 # red title

# Wall surface, built around the door and the opening
p.wall(0, 0, CEILING, horizontal=False, thickness=LEFT_W)                # left of door
p.wall(door_x, DOOR_H, DOOR_W, horizontal=True, thickness=CEILING - DOOR_H)  # lintel
p.wall(door_r, 0, CEILING, horizontal=False, thickness=GAP)              # 62 cm pier
p.wall(open_x, 0, OPEN_W, horizontal=True, thickness=SILL)               # below opening
p.wall(open_x, open_top, OPEN_W, horizontal=True,
       thickness=CEILING - open_top)                                     # above opening
p.wall(open_r, 0, CEILING, horizontal=False, thickness=RIGHT_W)          # right part

# New opening (red = to be created)
p.opening(open_x, SILL, OPEN_W, horizontal=True, thickness=OPEN_H)
p.text(open_x + OPEN_W / 2, SILL + OPEN_H / 2, "Ouverture\nsur salon",
       size=9, bold=True, color="white")

# Existing door
p.text(door_x + DOOR_W / 2, DOOR_H / 2, "PORTE\nvers salon", size=10, bold=True)

# Floor line
p.line(-20, 0, end_x + 20, 0, width=2.5)

# Dimensions from the sketch
p.dimension(door_r, SILL, GAP, horizontal=True)                     # 62, at sill level
p.dimension(open_x, open_top, OPEN_W, horizontal=True, offset=15)   # 105
p.dimension(open_r, 0, SILL, horizontal=False, offset=30, flip_label=True)       # 90
p.dimension(open_r, SILL, OPEN_H, horizontal=False, offset=30, flip_label=True)  # 110

# Terrace direction
p.text(end_x - 55, 170, "terrasse  →", size=10, boxed=True)

path = os.path.expanduser(NAME)          # "~" is not expanded automatically
os.makedirs(os.path.dirname(path), exist_ok=True)
p.save(path)
print("Saved:", path)