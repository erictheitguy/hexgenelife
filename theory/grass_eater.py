class GrassEater:
    import theory.hexsearch
    from pymongo import *
    import random
    import datetime
    client = MongoClient('candygram', 27017)
    dbmob = client.mob
    mob_collection = dbmob.grass_eater
    dbmap = client.map
    hex_tile_collection = dbmap.hex_tiles

    def motivate(self, mob_id, x, y):
        import theory.hexsearch
        print("do something")
        # get passed an object id for getting current info

        mob_info = GrassEater.mob_collection.find({"id": mob_id})

        cmx = mob_info["X"]
        cmy = mob_info["Y"]
        hunger = mob_info["hunger"]
        energy = mob_info["energy"]
        fat = mob_info["fat"]
        size = mob_info["size"] # size determines how much we remove each bite
        eyesight = mob_info["eyesight"]
        mob_type = mob_info["type"]
        mob_herd_instinct = mob_info["herd instinct"]

        # first lets make sure we are near other likewise mobs
        look_same_rating = GrassEater.look_same(cmx,cmy,mob_type,eyesight)

        # danger check

        # do i need to move closer to others?
        if mob_herd_instinct < look_same_rating:
            want_to_move = True

        # should I eat?
        if energy < 90:
            want_to_eat = True

        if want_to_eat == True:
            # can i eat?
            # get current grass amount in current hex
            theory.hexsearch.in_hex(cmx,cmy)



        # if not possible to eat where is food?

        # am i hungry enough to go and get it?


    def eat(self):
        eaten_amount = 0
        print("eat")
        #remove X amount from grass
        return(eaten_amount)

    def move(self):
        print("move")

    def look_same(cx,cy,mob_type,eyesight):
        rating = 0
        # find all mob types in the same
        print("looking for others like me")
        GrassEater.mob_collection.find({"type": mob_type})

        # get distance from each
        mob_dist = []
        # number

        # need a formula that gives a rating

        # the more that are close versus far away
        return(rating)

    def find_food(self):
        print("where my food be at")

    def food_avail(self):
        print("can i eat without moving?")
