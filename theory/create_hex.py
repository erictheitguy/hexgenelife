# hard coded database parameters aren't we doing something bad
# should fix it later

def top_hex(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on top of source point")
    hexagon_segment_one =  hexagon_size / 4
    hexagon_segment_two = hexagon_segment_one * 2
    # create hexagon top
    newcx = cx
    newcy = cy + hexagon_segment_two + hexagon_segment_two
    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy

    # what is its center?
    centerX = (X1 + X2 + X3 + X4+ X5 + X6) / 6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id


def top_right_hex(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    # create hexagon top  right
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx + hexagon_segment_two + hexagon_segment_one
    newcy = cy + hexagon_segment_two

    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy


    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id


def top_left_hex(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on top left of source point")
    # create hexagon top left
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx - hexagon_segment_two - hexagon_segment_one
    newcy = cy + hexagon_segment_two


    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy

    # what is its center?
    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
        "type": "Polygon",
        "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id


def bottom_hex(cx, cy ,hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on bottom of source point")
    # create hexagon bottom
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx
    newcy = cy - hexagon_segment_two - hexagon_segment_two


    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy

    # what is its center?
    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id

def bottom_right_hex(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on bottom right from source point")
    # create hexagon to bottom right
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx + hexagon_segment_two + hexagon_segment_one
    newcy = cy - hexagon_segment_two
    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy

    # what is its center?
    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id

def bottom_left_hex(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on bottom left from source point")
    # create hexagon bottom left
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx - hexagon_segment_two - hexagon_segment_one
    newcy = cy - hexagon_segment_two


    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    X7 = newcx - hexagon_segment_two
    Y7 = newcy
    # what is its center?
    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id

def hex_on_point(cx, cy, hexagon_size):
    import pymongo
    import random
    import datetime
    print("create hexagon on point")
    hexagon_segment_one =  hexagon_size/4
    hexagon_segment_two = hexagon_segment_one * 2
    newcx = cx
    newcy = cy

    X1 = newcx - hexagon_segment_two
    Y1 = newcy

    X2 = newcx - hexagon_segment_one
    Y2 = newcy - hexagon_segment_two

    X3 = newcx + hexagon_segment_one
    Y3 = newcy - hexagon_segment_two

    X4 = newcx + hexagon_segment_two
    Y4 = newcy

    X5 = newcx + hexagon_segment_one
    Y5 = newcy + hexagon_segment_two

    X6 = newcx - hexagon_segment_one
    Y6 = newcy + hexagon_segment_two

    # dont forget to include the 7th point to close the polygon
    X7 = newcx - hexagon_segment_two
    Y7 = newcy

    # what is its center?
    centerX = (X1+X2+X3+X4+X5+X6)/6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    #starting water value
    rand_water = random.randint(0, 100)
    #starting grass value
    rand_grass = random.randint(0, 100)

    hex1 = {
        "loc" :
            {
                "type": "Polygon",
                "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
            },
        "centerXY": [centerX, centerY],
        "centerX": centerX,
        "centerY": centerY,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": rand_water,
        "Grass": rand_grass,
        "Created": datetime.datetime.utcnow()
    }
    client = pymongo.MongoClient('candygram',27017)
    db = client.map
    hex_insert_collection = db.hex_tiles
    new_tile_id = hex_insert_collection.insert(hex1)
    return new_tile_id

