class GrassEater:
    import theory.hexsearch
    import pymongo
    import random
    import datetime
    client = pymongo.MongoClient('candygram', 27017)
    db_mob = client.mob
    mob_collection = db_mob.grasseater
    db_map = client.map
    hex_tile_collection = db_map.hex_tiles

    def motivate(mob_id, x, y):
        import theory.hexsearch

        next_action = ""
        want_to_move = False
        want_to_eat = False
        munch_away = False
        # get passed an object id for getting current info

        mob_info = GrassEater.mob_collection.find_one({"_id": mob_id})

        cmx = mob_info["mX"]
        cmy = mob_info["mY"]
        hunger = mob_info["hunger"]
        energy = mob_info["energy"]
        fat = mob_info["fat"]
        size = mob_info["size"]  # size determines how much we remove each bite
        eyesight = mob_info["eyesight"]
        mob_type = mob_info["mob_type"]
        mob_herd_instinct = mob_info["mob_herd"]

        # lets see if we are near other likewise mobs
        look_same_rating = GrassEater.look_same(cmx, cmy, mob_type, eyesight)

        # danger check

        # do i need to move closer to others?
        if mob_herd_instinct < look_same_rating:
            want_to_move = True

        # should I eat?
        # needs to be more complex taking into account fat
        if energy < 90:
            want_to_eat = True

        if want_to_eat == True:
            # can i eat?
            # get current grass amount in current hex
            inside_hex_id = theory.hexsearch.HexSearch.in_hex(cmx, cmy)
            hex_info = GrassEater.hex_tile_collection.find_one({"_id": inside_hex_id})
            grass_amount = hex_info["Grass"]
            if grass_amount > size:
                munch_away = True

        food_amount = 0
        food_tile_id = ""

        # if not possible to eat where is food?
        if want_to_eat == False and munch_away == False:
            food_search_tiles = theory.hexsearch.HexSearch.get_tiles(cmx, cmx, eyesight)
            for food_around in food_search_tiles:

                temp_food = food_around["Grass"]
                if temp_food > food_amount:
                    food_amount = temp_food
                    food_tile_id = food_around["_id"]

        # am i hungry enough to go and get it?
        food_search = False
        if energy > 70:
            food_search = False

        # we get one action we can move or eat
        # if we move where do we move too...




    def eat(tile_id, size):
        eaten_amount = 0
        print("eat")
        #remove X amount from grass
        return eaten_amount

    def move(x, y, direction, distance):
        print("move")

    def look_same(cx, cy, mob_type, eyesight):
        rating = 0
        # find all mob types in the same
        print("looking for others like me")
        # this should be more of a circle not a bounding box
        upper_bounding_box_x = cx - eyesight
        upper_bounding_box_y = cy + eyesight
        lower_bounding_box_x = cx + eyesight
        lower_bounding_box_y = cy - eyesight
        look_search = GrassEater.mob_collection.find({"$and": [ {"centerX": {"$gt": upper_bounding_box_x}},
                                                                {"centerX": {"$lt": lower_bounding_box_x}},
                                                                {"centerY": {"$gt": lower_bounding_box_y}},
                                                                {"centerY": {"$lt": upper_bounding_box_y}}]})

        look_results_count = look_search.count()
        if look_results_count > 0:
            for mobs in look_search:
                print("as")
                mob_dist = []
                rating = 50
        else:
            rating = 0

        # get distance from each

        # number

        # need a formula that gives a rating

        # the more that are close versus far away
        return rating

    def find_foodself(self):
        print("where my food be at")

    def food_avail(self):
        print("can i eat without moving?")
