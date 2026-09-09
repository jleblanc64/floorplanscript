import os

from floorplan import FloorPlan

NAME = "~/Pictures/ouverture2.png"

# reproduces the "Atelier - dépôt / Citerne / Garage" sketch.
T = 20                       # thickness of the horizontal walls
TV = 30                      # thickness of the central vertical wall
WALL_X = 250                 # x of the central vertical wall (its left face)
TOP_Y = 400                  # y of the top wall's bottom face

# vertical positions derived from the measurements, top to bottom
OPEN_TOP = TOP_Y - 70                    # 70 cm below the top wall
OPEN_BOTTOM = OPEN_TOP - 80              # 80 cm opening
WALL_BOTTOM_TOP = OPEN_BOTTOM - 119      # top face of the citerne/garage wall

p = FloorPlan()

# top wall spanning the whole width
p.wall(0, TOP_Y, 550, horizontal=True, thickness=T)

# central vertical wall, from bottom up to the top wall
p.wall(WALL_X, 0, TOP_Y, horizontal=False, thickness=TV)
# 80 cm opening
p.opening(WALL_X, OPEN_BOTTOM, 80, horizontal=False, thickness=TV)

# citerne bottom wall + garage separation (starts at the vertical wall's right face),
# its top face exactly 119 cm below the opening
p.wall(WALL_X + TV, WALL_BOTTOM_TOP - T, 550 - WALL_X - TV, horizontal=True, thickness=T)

# dimensions along the wall, placed to the left of it
p.dimension(WALL_X, OPEN_TOP, 70, horizontal=False, offset=-25)
p.dimension(WALL_X, OPEN_BOTTOM, 80, horizontal=False, offset=-25,
            label="80 cm\nouverture")
p.dimension(WALL_X, WALL_BOTTOM_TOP, 119, horizontal=False, offset=-25)
p.dimension(WALL_X, TOP_Y - 30, TV, horizontal=True, flip_label=True)

# room names
p.room_label(100, 240, "Atelier - dépôt")
p.room_label(410, 270, "Citerne")
p.room_label(410, 50, "Garage")

print("wrote", p.save(os.path.expanduser(NAME)))