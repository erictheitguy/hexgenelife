# create random amount of mob

import datetime
from pymongo import *
import random
import string
import theory.create_hex

def id_generator(id_size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(id_size))

client = MongoClient('candygram', 27017)
db_map = client.map
hex_tiles_collection = db_map.hex_tiles
db_mob = client.mob
mob_info_collection = db_mob.grasseater

number_to_create = 5


for i in range(1, number_to_create):
    # get random starting location
    total_hexes = hex_tiles_collection.find().count()
    random_tile_number = random.randint(0, (total_hexes - 1))
    random_tile = hex_tiles_collection.find().skip(random_tile_number).limit(-1)

    # we should offset these some random point inside random hexagon
    # to help remove chances of creating two on top of each other
    rand_diff1 = random.randint(-5, 5)
    rand_diff2 = random.randint(-5, 5)
    mx = random_tile[0]["centerX"]
    my = random_tile[0]["centerY"]

    # in case we insert on edge hex
    theory.create_hex.create_surrounding_hex(mx, my, 10)

    mx += rand_diff1
    my += rand_diff2

    # starting value for hunger, energy, fat will change once mob born and it starts to live
    # really only determine its starting actions

    rand_hunger = random.randint(0, 100)
    hunger = rand_hunger  # value 0 through 100


    rand_energy = random.randint(0, 100)
    energy = rand_energy  # value 0 through 100

    rand_fat = random.randint(0, 100)
    fat = rand_fat  # value 0 through 100

    size = 1  # size determines how much grass we remove each bite

    # age well how old it is...
    age = 0
    # eyesight determines how far away it can look for food and mobs
    # higher the better
    rand_eyesight = random.randint(0, 30)
    eyesight = rand_eyesight  # value 0 through 30
    if eyesight < 10:
        rand_eyesight = random.randint(0, 30)
        eyesight = (eyesight + rand_eyesight) / 2  # lets give it slightly better chance

    mob_type = "grass eater"

    # herd instinct determines its need to find others like itself
    # also how close it feels it needs to be
    rand_herd_instinct = random.randint(0, 100)
    mob_herd_instinct = rand_herd_instinct  # value 0 through 100

    new_mob = {
        "mob_id": id_generator(),
        "mXY": [mx, my],
        "mX": mx,
        "mY": my,
        "hunger": hunger,
        "energy": energy,
        "fat": fat,
        "size": size,
        "eyesight": eyesight,
        "mob_type": mob_type,
        "mob_herd": mob_herd_instinct,
        "age": age,
        "Created": datetime.datetime.utcnow()
    }

    mob_id = mob_info_collection.insert(new_mob)
    print(mob_id)

print("all done")