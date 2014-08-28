class GrassEater:
    import theory.hexsearch
    import pymongo
    import random
    import datetime
    import math
    client = pymongo.MongoClient('candygram', 27017)
    db_mob = client.mob
    mob_collection = db_mob.grasseater
    db_map = client.map
    hex_tile_collection = db_map.hex_tiles

    def motivate(mob_id, x, y):
        import theory.hexsearch

        next_action = ["rest", 100]
        want_to_move = False
        want_to_eat = False
        munch_away = False
        inside_hex_id = ""
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

        # lets do some metabolizing
        if energy < 20:
            fat += -10
            energy + 10
            GrassEater.mob_collection.update({"_id": mob_id}, {"$inc": {"fat": -10},"$inc": {"energy": 10}})

        if fat < 30:
            hunger += 10
            GrassEater.mob_collection.update({"_id": mob_id}, {"$inc": {"hunger": 10}})

        # lets see if we are near other likewise mobs
        look_same_rating = GrassEater.look_same(cmx, cmy, mob_type, eyesight)

        # danger check

        # do i need to move closer to others?

        if look_same_rating[0] < mob_herd_instinct:
            want_to_move = True

        # should I eat?
        # needs to be more complex taking into account fat
        if energy < 90:
            want_to_eat = True

        if want_to_eat is True:
            # can i eat?
            # get current grass amount in current hex
            inside_hex_id = theory.hexsearch.HexSearch.in_hex(cmx, cmy)
            hex_info = GrassEater.hex_tile_collection.find_one({"_id": inside_hex_id})
            grass_amount = hex_info["Grass"]

            if grass_amount > size:
                munch_away = True

        food_amount = 0
        food_tile_id = ""
        food_tile_x = 0
        food_tile_y = 0

        # if not possible to eat where is food?
        if want_to_eat is True and munch_away is False:
            food_search_tiles = theory.hexsearch.HexSearch.get_tiles(cmx, cmx, eyesight)
            for food_around in food_search_tiles:

                temp_food = food_around["Grass"]
                if temp_food > food_amount:
                    # this is bad, we should be be an sorted array of amount of food and their direction
                    # in corresponding to the herd. Food in direction of the herd is better
                    # than more food away from herd factored into the herd instinct
                    food_amount = temp_food
                    food_tile_id = food_around["_id"]
                    food_tile_x = food_around["centerX"]
                    food_tile_y = food_around["centerY"]

        # am i hungry enough to go and get it?
        food_search = False
        if energy > 70 and fat > 50 and want_to_move is False:

            food_search = False

        if fat < 50 and energy < 50 and munch_away is False:
            food_search = True

        if hunger > 50 and food_search is False:
            food_search = True

        if want_to_eat is True and munch_away is True:
            next_action = ["eat", 100]

        if next_action[0] == "eat":
            if fat > 90:
                next_action[1] = 50

        if want_to_eat is True and food_search is True and munch_away is False:
            next_action = ["move food", 100]

        if next_action[1] < 60 and next_action[0] == "eat" and want_to_move is True:
            next_action = ["move", 80]

        if want_to_eat is False and want_to_move is True:
            next_action = ["move", 100]

        if want_to_move is True and want_to_eat is False:
            next_action = ["move", 80]

        if want_to_move is True and want_to_eat is True and food_search is False:
            next_action = ["move", 80]

        if next_action[0] == "eat":
            eaten = GrassEater.eat(inside_hex_id, size)
            eaten = abs(eaten)
            GrassEater.mob_collection.update({"_id": mob_id}, {"$inc": {"fat": 1}, "$inc": {"energy": 10}, "$inc": {"hunger": -10 }})

        if next_action[0] == "move food":
            GrassEater.move(mob_id, cmx, cmy, food_tile_x, food_tile_y, 1)

        if next_action[0] == "move":

            if look_same_rating[1] == 0:
                # should look at last direction moved then vector from that with slight heading change
                diff1 = GrassEater.random.randint(-5, 5)
                diff2 = GrassEater.random.randint(-5, 5)
                look_same_rating[1] = cmx + diff1
                look_same_rating[2] = cmy + diff2
            GrassEater.move(mob_id, cmx, cmy, look_same_rating[1], look_same_rating[2], 1)

        if next_action[0] == "rest":
            print("we are resting")
            GrassEater.mob_collection.update({"_id": mob_id}, {"$inc": {"energy": -2}})


    def eat(tile_id, size):
        eaten_amount = size * -1
        # print("eat")
        # remove X amount from grass
        eaten = GrassEater.hex_tile_collection.update({"_id": tile_id}, {"$inc": {"Grass": eaten_amount}})
        return eaten_amount

    def move(mob_id, source_x, source_y, destination_x, destination_y, move_speed):

        # print("move")
        xdiff = source_x - destination_x
        ydiff = source_y - destination_y

        angle_points = GrassEater.math.degrees(GrassEater.math.atan2(ydiff,xdiff))
        if angle_points < 0:
            angle_points = abs(angle_points) + 90
        else:
            angle_points = 90 - angle_points
        if angle_points < 0:
            angle_points = angle_points + 360

        change_dir_amount = GrassEater.random.randint(-5, 5)
        change_dir_amount = angle_points + change_dir_amount


        corrected_deg = 90 - change_dir_amount
        print(corrected_deg)
        theta = GrassEater.math.radians(corrected_deg)
        delta_x = move_speed*GrassEater.math.cos(theta)
        delta_y = move_speed*GrassEater.math.sin(theta)
        # new point
        source_x += delta_x
        source_y += delta_y

        # okay we have a new location
        GrassEater.mob_collection.update({"_id": mob_id}, {"$set": {"mX": source_x},"$set": {"mY": source_y},
                                                           "$inc": {"Fat": -1}, "$inc": {"energy": -10}})



    def look_same(cx, cy, mob_type, look_distance):
        rating = [0, 0, 0]

        fx = 0
        fy = 0
        # find all mob types in the same
        # this should be more of a circle not a bounding box
        upper_bounding_box_x = cx - look_distance
        upper_bounding_box_y = cy + look_distance
        lower_bounding_box_x = cx + look_distance
        lower_bounding_box_y = cy - look_distance
        look_search = GrassEater.mob_collection.find({"$and": [ {"centerX": {"$gt": upper_bounding_box_x}},
                                                                {"centerX": {"$lt": lower_bounding_box_x}},
                                                                {"centerY": {"$gt": lower_bounding_box_y}},
                                                                {"centerY": {"$lt": upper_bounding_box_y}}]})

        look_results_count = look_search.count()
        if look_results_count > 0:
            rating[0] = 50
            for mobs in look_search:
                fx = fx + mobs["mX"]
                fy = fy + mobs["mY"]
                mob_dist = []
                rating[0] = rating[0] + 5
            fx = fx / look_results_count
            fy = fy / look_results_count
            rating[1] = fx
            rating[2] = fy
        else:
            rating[0] = 0

        # get distance from each

        # number

        # need a formula that gives a rating

        # the more that are close versus far away
        return rating

    def find_food(self):
        print("where my food be at")

    def food_avail(self):
        print("can i eat without moving?")

    def update_mob_info(self):
        print("actions done updating db with new values")
