class HexSearch():
    import theory.db_connection

    def in_hex(self, x, y):
        point_inside = False
        hex_id = None
        inside_hex_id = None
        # Use the new helper function for bounding box search
        hex_search_results = theory.db_connection.find_hex_tiles_in_bounds(x - 10, x + 10, y - 10, y + 10)
        
        for hexagon_tile_found in hex_search_results:
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
    
    def point_in_poly(self, x, y, poly):
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
    
    def get_tiles(self, x , y, range):
        # get all tiles within range
        tile_results = theory.db_connection.find_hex_tiles_in_bounds(x - range, x + range, y - range, y + range)
        return tile_results