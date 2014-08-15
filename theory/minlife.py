import datetime
from pymongo import *
import random
import time
import math
from tkinter import *


canvas = Canvas(width=300, height=300, bg='white')
canvas.pack(expand=YES, fill=BOTH)

client = MongoClient('candygram', 27017)
db = client.map

hex_tiles_collection = db.hex_tiles
hex_center_collection = db.hex_tiles_center

# db.yourCollection.find().limit(-1).skip(yourRandomNumber).next()

# get random hexagon to start on
# lets use the center points then intersect from there

# hex_tile_center = hex_center_collection.find_one() # not really random
#point_cords = hex_tile_center['loc']['coordinates']
#pX1,pY1 = point_cords

#temp i know this hex exists random start to replace this
pX1 = 10
pY1 = 10
#temp

#instance new life
life_loc_x = pX1
life_loc_y = pY1
life_id = "test"
# direction
life_dir = random.randint(0, 360)
#speed
life_speed = 1

#willingness to change direction multiplier 0 - 100
life_dir_change = 30


#insert life into db

i = 0
while i < 100:
    # direction
    change_dir_amount = random.randint(1, 100)
    change_dir_amount = life_dir_change / change_dir_amount
    print(change_dir_amount, " <- amount to change dir")
    life_dir += change_dir_amount
    print (life_dir, " <- life direction")
    life_loc_x += math.sin(life_dir) * life_speed
    life_loc_y += math.cos(life_dir) * life_speed
    print (life_loc_x,life_loc_y," <- new location")
    # okay we have a new location
    # lets see if we have a hexagon there
    hex_search = hex_tiles_collection.find( {"loc": {"$geoIntersects" : {"$geometry" : { "type": "Point" , "coordinates": [ life_loc_x, life_loc_y] } } } } )
    if (hex_search.count() > 0) :
        print ("we got a match")
    else:
        print("no hex found here")
        #need to create a hexagon
        # first lets figure out which direction we need to create our
        # new hexagon in
    time.sleep(.5) # sleep for half a second
    canvas.create_oval(pX1,pY1,pX1+2,pY1+2,fill="red")
    i += 1
