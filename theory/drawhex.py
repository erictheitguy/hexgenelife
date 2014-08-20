
import datetime
import random
from pymongo import *
from tkinter import *

canvas = Canvas(width=500, height=500, bg='white')
canvas.pack(expand=YES, fill=BOTH)

client = MongoClient('candygram',27017)
db = client.map
hex_tiles_collection = db.hex_tiles
hex_center_collection = db.hex_tiles_center
scale_factor = 10
search_point_x = 10
search_point_y = 10

#hex_tiles = hex_tiles_collection.database.command({"geoNear": "hex_tiles", "near": [search_point_x,search_point_y]})
hex_tiles = hex_tiles_collection.find({"$and": [ {"centerX": {"$gt":0}},{"centerX": {"$lt":20}}]})

if hex_tiles.count() > 0:
    hex_count = hex_tiles.count()
    print("we found some hexagons ",hex_count)

    for hexagon_tile_found in hex_tiles:
        X1,Y1 = hexagon_tile_found["hexcp1"]
        X2,Y2 = hexagon_tile_found["hexcp2"]
        X3,Y3 = hexagon_tile_found["hexcp3"]
        X4,Y4 = hexagon_tile_found["hexcp4"]
        X5,Y5 = hexagon_tile_found["hexcp5"]
        X6,Y6 = hexagon_tile_found["hexcp6"]
        X7,Y7 = hexagon_tile_found["hexcp7"]
        print(hexagon_tile_found["centerXY"])
        # this is so bad
        X1 = X1 * scale_factor
        X2 = X2 * scale_factor
        X3 = X3 * scale_factor
        X4 = X4 * scale_factor
        X5 = X5 * scale_factor
        X6 = X6 * scale_factor
        X7 = X7 * scale_factor
        Y1 = Y1 * scale_factor
        Y2 = Y2 * scale_factor
        Y3 = Y3 * scale_factor
        Y4 = Y4 * scale_factor
        Y5 = Y5 * scale_factor
        Y6 = Y6 * scale_factor
        Y7 = Y7 * scale_factor



        #random bit color

        b1 = random.randint(0,9)
        b2 = random.randint(0,9)
        b3 = random.randint(0,9)
        color_bit = "#" + str(b1) + str(b2) + str(b3)
        print(color_bit)
        canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7, fill=color_bit)



canvas.create_oval(search_point_x,search_point_y,search_point_x+2,search_point_y+2,fill="red")

mainloop()