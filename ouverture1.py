from floorplan import FloorPlan

# reproduces the "Atelier - dépôt / Citerne / Garage" sketch.
T = 20                       # wall thickness used throughout
WALL_X = 250                 # x of the central vertical wall (its left face)
TOP_Y = 400                  # y of the top wall's bottom face
p = FloorPlan()

# top wall spanning the whole width
p.wall(0, TOP_Y, 550, horizontal=True, thickness=T)

# central vertical wall, from bottom up to the top wall
p.wall(WALL_X, 0, TOP_Y, horizontal=False, thickness=T)
# 80 cm opening: 70 cm below the top wall
p.opening(WALL_X, TOP_Y - 70 - 80, 80, horizontal=False, thickness=T)

# citerne bottom wall + garage separation
p.wall(WALL_X + T, 130, 550 - WALL_X - T, horizontal=True, thickness=T)

# dimensions along the wall, placed to the left of it
p.dimension(WALL_X, TOP_Y - 70, 70, horizontal=False, offset=-25)
p.dimension(WALL_X, TOP_Y - 150, 80, horizontal=False, offset=-25,
            label="80 cm\nouverture")
p.dimension(WALL_X, TOP_Y - 150 - 119, 119, horizontal=False, offset=-25)
p.dimension(WALL_X, TOP_Y - 30, T, horizontal=True, label="20 cm",
            flip_label=True)

# room names
p.room_label(110, 200, "Atelier - dépôt")
p.room_label(410, 270, "Citerne")
p.room_label(410, 60, "Garage")

print("wrote", p.save("demo.png"))