import os

from floorplan import FloorPlan

NAME = "~/Pictures/ouverture1.png"

# reproduces the "Couloir / Salle de jeux / Salle de bains" sketch.
# Only 23 (wall thickness), 40, 63 and 80 are given; other sizes are assumed.
T = 20                        # default wall thickness (assumed)
TJ = 23                       # thickness of the Salle de jeux top wall (given)
TV = 20                       # thickness of the vertical walls (assumed)
TOP_Y = 500                   # bottom face of the top corridor wall
ROOM_TOP = 380                # top face of the room walls (corridor is 120 wide)
WALL_X = 350                  # left face of the Salle de jeux right wall
COULOIR_W = 100               # width of the vertical corridor (assumed)
BATH_X = WALL_X + TV + COULOIR_W   # left face of the Salle de bains left wall
WIDTH = 900

p = FloorPlan()

# --- top corridor wall, full width
p.wall(0, TOP_Y, WIDTH, horizontal=True, thickness=T)

# --- Salle de jeux: top wall (23 thick) + right wall with 80 cm opening
p.wall(0, ROOM_TOP - TJ, WALL_X + TV, horizontal=True, thickness=TJ)
p.wall(WALL_X, 0, ROOM_TOP, horizontal=False, thickness=TV)
OPEN_Y = ROOM_TOP - TJ - 40 - 80          # opening starts 40 cm below the wall
p.opening(WALL_X, OPEN_Y, 80, horizontal=False, thickness=TV)

# --- Salle de bains: left wall + top wall
p.wall(BATH_X, 0, ROOM_TOP, horizontal=False, thickness=TV)
p.wall(BATH_X, ROOM_TOP - T, WIDTH - BATH_X, horizontal=True, thickness=T)

# --- dimensions (left of the Salle de jeux wall)
DX = WALL_X - 20
p.dimension(DX, ROOM_TOP - TJ, TJ, horizontal=False)
p.dimension(DX, ROOM_TOP - TJ - 40, 40, horizontal=False)
p.dimension(DX, OPEN_Y, 80, horizontal=False, label="80 cm\nouverture")
# 63 = 23 + 40, measured on the corridor side
p.dimension(WALL_X + TV + 20, ROOM_TOP - 63, 63, horizontal=False,
            flip_label=True)

# --- room names
p.room_label(450, TOP_Y - 60, "Couloir")
p.room_label(WALL_X + TV + COULOIR_W / 2, 200, "Couloir", rotation=90)
p.room_label(160, 250, "Salle de jeux")
p.room_label(BATH_X + 220, 250, "Salle de bains")

print("wrote", p.save(os.path.expanduser(NAME)))