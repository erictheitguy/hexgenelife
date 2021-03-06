

import random
from pymongo import *
from tkinter import *

canvas_width = 1000
canvas_height = 1000
canvas = Canvas(width=canvas_width, height=canvas_height, bg='white')
canvas.pack(expand=YES, fill=BOTH)

client = MongoClient('candygram',27017)
db = client.map
hex_tiles_collection = db.hex_tiles
hex_center_collection = db.hex_tiles_center

db_mob = client.mob
grass_eater_collection =  db_mob.grasseater

scale_factor = 2
search_point_x = 1
search_point_y = 1
canvas_center_x = canvas_width / 2
canvas_center_y = (canvas_height / 2)

xdiff = abs(canvas_center_x - search_point_x * scale_factor)
ydiff = abs(canvas_center_y - search_point_y * scale_factor)
xdiff = xdiff - (10 * scale_factor)
ydiff = ydiff + (10 * scale_factor)

upper_bounding_box_x = search_point_x - 1000
upper_bounding_box_y = search_point_y + 1000
lower_bounding_box_x = search_point_x + 1000
lower_bounding_box_y = search_point_y - 1000

hex_tiles = hex_tiles_collection.find()
all_mobs = grass_eater_collection.find()

if hex_tiles.count() > 0:
    hex_count = hex_tiles.count()
    print("we found some hexagons ",hex_count)

    for hexagon_tile_found in hex_tiles:
        X1, Y1 = hexagon_tile_found["hexcp1"]
        X2, Y2 = hexagon_tile_found["hexcp2"]
        X3, Y3 = hexagon_tile_found["hexcp3"]
        X4, Y4 = hexagon_tile_found["hexcp4"]
        X5, Y5 = hexagon_tile_found["hexcp5"]
        X6, Y6 = hexagon_tile_found["hexcp6"]
        X7, Y7 = hexagon_tile_found["hexcp7"]
        grass_color = hexagon_tile_found["Grass"]
        grass_color = round(grass_color * .1, 0)
        grass_color = int(grass_color)
        if grass_color == 10:
            grass_color = 9


        X1 = ((X1 + 1) * scale_factor) + xdiff
        X2 = ((X2 + 1) * scale_factor) + xdiff
        X3 = ((X3 + 1) * scale_factor) + xdiff
        X4 = ((X4 + 1) * scale_factor) + xdiff
        X5 = ((X5 + 1) * scale_factor) + xdiff
        X6 = ((X6 + 1) * scale_factor) + xdiff
        X7 = ((X7 + 1) * scale_factor) + xdiff
        Y1 = ((1 - Y1) * scale_factor) + ydiff
        Y2 = ((1 - Y2) * scale_factor) + ydiff
        Y3 = ((1 - Y3) * scale_factor) + ydiff
        Y4 = ((1 - Y4) * scale_factor) + ydiff
        Y5 = ((1 - Y5) * scale_factor) + ydiff
        Y6 = ((1 - Y6) * scale_factor) + ydiff
        Y7 = ((1 - Y7) * scale_factor) + ydiff

        #random bit color
        b1 = random.randint(0,9)
        b2 = random.randint(0,9)
        b3 = random.randint(0,9)
        b1 = 0
        b2 = grass_color
        b3 = 0
        if grass_color < 2:
            b1 = 9
        color_bit = "#" + str(b1) + str(b2) + str(b3)
        canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7, fill=color_bit)

if all_mobs.count() > 0:
    for mob_found in all_mobs:
        mx = mob_found["mX"]
        my = mob_found["mY"]

        mx = ((mx + 1) * scale_factor) + xdiff
        my = ((1 - my) * scale_factor) + ydiff
        b1 = random.randint(0,9)
        b2 = random.randint(0,9)
        b3 = random.randint(0,9)
        color_bit = "#" + str(b1) + str(b2) + str(b3)
        canvas.create_oval(mx - (.5* scale_factor),my - (.5* scale_factor),mx + (.5 * scale_factor),my + (.5 * scale_factor),fill=color_bit)

canvas.create_oval(search_point_x, search_point_y, search_point_x+2, search_point_y+2, fill="red")


mainloop()