# hard coded database parameters aren't we doing something bad
# should fix it later


def create_surrounding_hex(x, y, hexagon_size):
    import theory.db_connection
    import sqlite3
    import random
    import datetime

    # Connect to SQLite database
    conn = sqlite3.connect('candygram.db')
    cursor = conn.cursor()

    hexagon_segment_one = hexagon_size / 4
    hexagon_segment_two = hexagon_segment_one * 2
    center_hex_x = x
    center_hex_y = y

    # need to check if a hex exists on each side of poly
    # if it doesnt create it

    # top
    tcx = center_hex_x
    tcy = center_hex_y + hexagon_segment_two + hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (tcx, tcy))
    top_hex_search = cursor.fetchone()
    if top_hex_search is None:
        print("create top")
        top_hex(x, y, hexagon_size)

    # top right
    trcx = center_hex_x + hexagon_segment_two + hexagon_segment_one
    trcy = center_hex_y + hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (trcx, trcy))
    topr_hex_search = cursor.fetchone()
    if topr_hex_search is None:
        print("create top right")
        top_right_hex(x, y, hexagon_size)

    # top left
    tlcx = center_hex_x - hexagon_segment_two - hexagon_segment_one
    tlcy = center_hex_y + hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (tlcx, tlcy))
    topl_hex_search = cursor.fetchone()
    if topl_hex_search is None:
        print("create top left")
        top_left_hex(x ,y, hexagon_size)

    # bottom
    bcx = center_hex_x
    bcy = center_hex_y - hexagon_segment_two - hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (bcx, bcy))
    bottom_hex_search = cursor.fetchone()
    if bottom_hex_search is None:
        print("create bottom")
        bottom_hex(x, y, hexagon_size)

    # bottom right
    brcx = center_hex_x + hexagon_segment_two + hexagon_segment_one
    brcy = center_hex_y - hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (brcx, brcy))
    bottomr_hex_search = cursor.fetchone()
    if bottomr_hex_search is None:
        print("create bottom right")
        bottom_right_hex(x, y, hexagon_size)

    # bottom left
    blcx = center_hex_x - hexagon_segment_two - hexagon_segment_one
    blcy = center_hex_y - hexagon_segment_two
    cursor.execute("SELECT id FROM hex_tiles WHERE centerX=? AND centerY=?", (blcx, blcy))
    bottoml_hex_search = cursor.fetchone()
    if bottoml_hex_search is None:
        print("create bottom left")
        bottom_left_hex(x, y, hexagon_size)

    conn.commit()
    conn.close()


def top_hex(cx, cy, hexagon_size):
    import random
    import datetime
    print("create hexagon on top of source point")
    hexagon_segment_one = hexagon_size / 4
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
    centerX = (X1 + X2 + X3 + X4 + X5 + X6) / 6
    centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6
    
    # TODO we should probably have a function that generates these values based on the surrounding hexes instead of just random
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
    return hex1


def top_right_hex(cx, cy, hexagon_size):
    import theory.db_connection
    import random
    import datetime
    # create hexagon top  right
    hexagon_segment_one = hexagon_size/4
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
    return hex1


def top_left_hex(cx, cy, hexagon_size):
    import theory.db_connection
    import random
    import datetime
    print("create hexagon on top left of source point")
    # create hexagon top left
    hexagon_segment_one = hexagon_size/4
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
    return hex1


def bottom_hex(cx, cy ,hexagon_size):
    import theory.db_connection
    import random
    import datetime
    print("create hexagon on bottom of source point")
    # create hexagon bottom
    hexagon_segment_one = hexagon_size/4
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
    return hex1

def bottom_right_hex(cx, cy, hexagon_size):
    import theory.db_connection
    import random
    import datetime
    print("create hexagon on bottom right from source point")
    # create hexagon to bottom right
    hexagon_segment_one = hexagon_size/4
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
    return hex1

def bottom_left_hex(cx, cy ,hexagon_size):
    import theory.db_connection
    import random
    import datetime
    print("create hexagon on bottom left from source point")
    # create hexagon bottom left
    hexagon_segment_one = hexagon_size/4
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
    return hex1

def hex_on_point(cx, cy, hexagon_size):
    import theory.db_connection
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
    return hex1

