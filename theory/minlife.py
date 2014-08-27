import datetime
from pymongo import *
import random
import time
import math
import theory.create_hex


def point_in_poly(x,y,poly):
# stolen from http://stackoverflow.com/questions/16625507/python-checking-if-point-is-inside-a-polygon
    n = len(poly)
    inside = False

    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x,p1y = p2x,p2y

    return inside


def insert_hex(ix1,iy1, ix2,iy2, ix3,iy3, ix4,iy4 ,ix5,iy5, ix6,iy6, ix7,iy7, icx,icy):
    hex_tiles = db.hex_tiles
    hex_tiles_center = db.hex_tiles_center
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)
    centerX = icx
    centerY = icy
    hex1 = {
        "loc":
        {
            "type": "Polygon",
            "coordinates": [ [ [ ix1 , iy1 ] , [ ix2 , iy2 ] , [ ix3 , iy3 ] , [ ix4 , iy4  ] , [ix5 , iy5] , [ ix6 , iy6 ] , [ ix7 , iy7 ] ] ]
        },
        "centerXY": [icx, icy],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [ix1, iy1],
        "hexcp2": [ix2, iy2],
        "hexcp3": [ix3, iy3],
        "hexcp4": [ix4, iy4],
        "hexcp5": [ix5, iy5],
        "hexcp6": [ix6, iy6],
        "hexcp7": [ix7, iy7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    # we also need to insert the center
    hex1_center = {
        "loc":
        {
            "type": "Point",
            "coordinates": [ centerX , centerY ]
            },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "Created": datetime.datetime.utcnow()
    }
    hex_insert_id = hex_tiles.insert(hex1)
    center_tile_id = hex_tiles_center.insert(hex1_center)
    return hex_insert_id


def create_surrounding_hex(x,y,hexagon_size):

    center_hex_x = x
    center_hex_y = y
    # need to check if a hex exists on each side of poly
    # if it doesnt create it

    # top
    tcx = center_hex_x
    tcy = center_hex_y + hex_twoseg + hex_twoseg
    top_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": tcx}, {"centerY": tcy}]})
    if top_hex_search is None:
        print("create top")
        theory.create_hex.top_hex(x,y,hexagon_size)


    # top right
    trcx = center_hex_x + hex_twoseg + hex_oneseg
    trcy = center_hex_y + hex_twoseg
    topr_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": trcx}, {"centerY": trcy}]})
    if topr_hex_search is None:
        print("create top right")
        theory.create_hex.top_right_hex(x,y,hexagon_size)

    # top left
    tlcx = center_hex_x - hex_twoseg - hex_oneseg
    tlcy = center_hex_y + hex_twoseg
    topl_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": tlcx}, {"centerY": tlcy}]})
    if topl_hex_search is None:
        print("create top left")
        theory.create_hex.top_left_hex(x,y,hexagon_size)

    # bottom
    bcx = center_hex_x
    bcy = center_hex_y - hex_twoseg - hex_twoseg
    bottom_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": bcx}, {"centerY": bcy}]})
    if bottom_hex_search is None:
        print("create bottom")
        theory.create_hex.bottom_hex(x,y,hexagon_size)

    # bottom right
    brcx = center_hex_x + hex_twoseg + hex_oneseg
    brcy = center_hex_y - hex_twoseg
    bottomr_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": brcx}, {"centerY": brcy}]})
    if bottomr_hex_search is None:
        print("create bottom right")
        theory.create_hex.bottom_right_hex(x,y,hexagon_size)

    # bottom left
    blcx = center_hex_x - hex_twoseg - hex_oneseg
    blcy = center_hex_y - hex_twoseg
    bottoml_hex_search = hex_tiles_collection.find_one({"$and": [{"centerX": blcx}, {"centerY": blcy}]})
    if bottoml_hex_search is None:
        print("create bottom left")
        theory.create_hex.bottom_left_hex(x,y,hexagon_size)


client = MongoClient('candygram', 27017)
db = client.map

hex_tiles_collection = db.hex_tiles
hex_center_collection = db.hex_tiles_center

# get random hexagon to start on
total_hexes = hex_tiles_collection.find().count()
random_tile_number = random.randint(0,(total_hexes - 1))
random_tile = hex_tiles_collection.find().skip(random_tile_number).limit(-1)

# random_tile
pX1 = random_tile[0]["centerX"]
pY1 = random_tile[0]["centerY"]

print("starting hex tile", pX1, pY1)
#hexagon size why is it 10? because I like 10
hex_size = 10
hex_oneseg = hex_size/4
hex_twoseg = hex_oneseg * 2

# instance new life
life_loc_x = pX1
life_loc_y = pY1
life_id = "test"
# direction
life_dir = random.randint(0, 360)
# speed
life_speed = 1

# willingness to change direction multiplier 0 - 100
life_dir_change = 30


# insert life into db


old_hex_poly = []
old_hex_center = []
new_hex_poly = []
new_hex_center = []


i = 0
while i < 1000:
    # direction
    change_dir_amount = random.randint(1, 100)
    change_dir_amount = life_dir_change / change_dir_amount
    # print(change_dir_amount, " <- amount to change dir")
    life_dir += change_dir_amount
    # add if above 360 convert it to 0 - 360
    # print(life_dir, " <- life direction")

    corrected_deg = 90 - life_dir
    theta = math.radians(corrected_deg)
    deltax = life_speed*math.cos(theta)
    deltay = life_speed*math.sin(theta)
    # new point
    life_loc_x += deltax
    life_loc_y += deltay
    # print(life_loc_x,life_loc_y," <- new location")
    # okay we have a new location

    # lets see if we have a hexagon there
    # get nearest 7 tiles
    # the value 10 comes from creating the hexagon values
    upper_bounding_box_x = life_loc_x - 10
    upper_bounding_box_y = life_loc_y + 10
    lower_bounding_box_x = life_loc_x + 10
    lower_bounding_box_y = life_loc_y - 10
    hex_search = hex_tiles_collection.find({"$and": [ {"centerX": {"$gt": upper_bounding_box_x}},{"centerX": {"$lt": lower_bounding_box_x}},
                                                 {"centerY": {"$gt": lower_bounding_box_y}},{"centerY": {"$lt": upper_bounding_box_y}}]})

    # lets create some emtpy hexagon poly in this loop

    create_new_poly = False
    point_inside = False
    if hex_search.count() > 0:
        # print("we found some hexagons", hex_search.count())
        hex_count = hex_search.count()  # I really don't know if i need this?

        for hexagon_tile_found in hex_search:
            if point_inside: break
            X1,Y1 = hexagon_tile_found["hexcp1"]
            X2,Y2 = hexagon_tile_found["hexcp2"]
            X3,Y3 = hexagon_tile_found["hexcp3"]
            X4,Y4 = hexagon_tile_found["hexcp4"]
            X5,Y5 = hexagon_tile_found["hexcp5"]
            X6,Y6 = hexagon_tile_found["hexcp6"]
            X7,Y7 = hexagon_tile_found["hexcp7"]
            CX1,CY1 = hexagon_tile_found["centerXY"]

            # determine if we are inside of it ray tracing method
            hexagon_poly = hexagon_tile_found["loc"]["coordinates"]
            hexagon_poly = hexagon_poly[0]
            point_inside = point_in_poly(life_loc_x,life_loc_y,hexagon_poly)
            # print(point_inside," are we still inside a polygon")
            if point_inside == True:
                old_hex_poly = hexagon_poly
                old_hex_center = hexagon_tile_found["centerXY"]
                # do nothing else
                create_new_poly = False
                break
            else:
                create_new_poly = True

            # we now know if we inside or not what to do now.
        if create_new_poly == True:
            print("creating a new hexagon")
            # what is the last hexagon that I was in?

            # print(old_hex_center, " old hex center to start from") # this should be the last hexagon center I was in
            # note we always start inside a hexagon so the above var should be set hopefully

            # what side of the hexagon are we on?
            xdiff = abs(old_hex_center[0] - life_loc_x)
            ydiff = abs(old_hex_center[1] - life_loc_y)

            #what side of the hexagon are we on?
            xdiff = life_loc_x - old_hex_center[0]
            ydiff = life_loc_y - old_hex_center[1]
            # print(xdiff,ydiff, " diffs")

            angle_points = math.degrees(math.atan2(ydiff,xdiff))
            # print(angle_points, " unconverted angle")
            # 180 unconverted is really 270
            if angle_points < 0:
                angle_points = abs(angle_points) + 90
            else:
                angle_points = 90 - angle_points
            if angle_points < 0:
                angle_points = angle_points + 360
            # print(angle_points, " final angle")

            # print(angle_points, " angle between the two points")
            if angle_points > 330 or angle_points < 30:
                print("top of hexagon")
                # create hexagon top

                new_tile_id = theory.create_hex.top_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id, old_hex_center, "new tile information")
                point_inside = True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)

            if angle_points > 30 and angle_points < 90:
                print("top right")
                # create hexagon top  right
                new_tile_id = theory.create_hex.top_right_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id,old_hex_center, "new tile information")
                point_inside == True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)

            if angle_points > 90 and angle_points < 150:
                print("bottom right")
                # create hexagon to bottom right
                new_tile_id = theory.create_hex.bottom_right_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id,old_hex_center, "new tile information")
                point_inside = True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)

            if angle_points > 150 and angle_points < 210:
                print("bottom")
                # create hexagon bottom
                new_tile_id = theory.create_hex.bottom_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id,old_hex_center, "new tile information")
                point_inside = True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)

            if angle_points > 210 and angle_points < 270:
                print("bottom left")
                # create hexagon bottom left
                new_tile_id = theory.create_hex.bottom_left_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id,old_hex_center, "new tile information")
                point_inside == True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)

            if angle_points > 270 and angle_points < 330:
                print("top left")
                # create hexagon top left
                new_tile_id = theory.create_hex.top_left_hex(old_hex_center[0], old_hex_center[1], hex_size)
                print(new_tile_id, old_hex_center, "new tile information")
                point_inside = True
                # we now have a new hexagon tile
                create_surrounding_hex(old_hex_center[0],old_hex_center[1],hex_size)





    else:
        print("no hexes found here any where around here")
        print("since no hexes found close by we quiting")
        break
        # need to create a hexagon
        # first lets figure out which direction we need to create our
        # new hexagon in

    time.sleep(.1)  # sleep for half a second

    i += 1
print ("all done")
