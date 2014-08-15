
import datetime
from pymongo import *
from tkinter import *

canvas = Canvas(width=50, height=50, bg='white')
canvas.pack(expand=YES, fill=BOTH)

client = MongoClient('candygram',27017)
db = client.map
hex_tiles_collection = db.hex_tiles
hex_center_collection = db.hex_tiles_center
hex_tile = hex_tiles_collection.find_one()
hex_tile_center = hex_center_collection.find_one()
#hex_tile_coords = hex_tile.get("loc")
poly_cords = hex_tile['loc']['coordinates']
X1,Y1 = poly_cords[0][0]
X2,Y2 = poly_cords[0][1]
X3,Y3 = poly_cords[0][2]
X4,Y4 = poly_cords[0][3]
X5,Y5 = poly_cords[0][4]
X6,Y6 = poly_cords[0][5]
X7,Y7 = poly_cords[0][6]


canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7, fill="green")

point_cords = hex_tile_center['loc']['coordinates']
pX1,pY1 = point_cords
canvas.create_oval(pX1,pY1,pX1+2,pY1+2,fill="red")

mainloop()