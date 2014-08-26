class HexSearch():
    from pymongo import *
    client = MongoClient('candygram', 27017)
    dbmap = client.map
    hex_tile_collection = dbmap.hex_tiles

    def in_hex(x,y):

        hex_id = 0
        inside_hex_id = 0
        upper_bounding_box_x = x - 10
        upper_bounding_box_y = y + 10
        lower_bounding_box_x = x + 10
        lower_bounding_box_y = y - 10
        hex_search = HexSearch.hex_tile_collection.find({"$and": [ {"centerX": {"$gt": upper_bounding_box_x}},{"centerX": {"$lt": lower_bounding_box_x}},
                                                 {"centerY": {"$gt": lower_bounding_box_y}},{"centerY": {"$lt": upper_bounding_box_y}}]})
        for hexagon_tile_found in hex_search:
            if point_inside:
                break
            hex_id = hexagon_tile_found["_id"]
            # determine if we are inside of it ray tracing method
            hexagon_poly = hexagon_tile_found["loc"]["coordinates"]
            hexagon_poly = hexagon_poly[0]
            point_inside = HexSearch.point_in_poly(x,y,hexagon_poly)
            if point_inside == True:
                inside_hex_id = hex_id
                break

        return inside_hex_id

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