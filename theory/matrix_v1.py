from pymongo import *
import random
import math
import theory.grass_eater
import theory.hexsearch
import theory.create_hex
import datetime
import time


# select all mobs
# for now just grass eaters

client = MongoClient('candygram', 27017)
db_mob = client.mob
grass_eater_collection = db_mob.grasseater

grass_eaters_ids = grass_eater_collection.distinct("mob_id")
i = 0

while i < 100:
    for grass_eater in grass_eaters_ids:
        last_mob_info = grass_eater_collection.find({"$query": {"mob_id": grass_eater}, "$orderby":{"Created": -1}}).limit(1)
        # got current mob info

        # lets check to make sure all surrounding tiles exist
        theory.create_hex.create_surrounding_hex(last_mob_info[0]["mX"], last_mob_info[0]["mY"], 10)
        stork = theory.grass_eater.GrassEater
        stork.motivate(last_mob_info[0]["_id"], last_mob_info[0]["mX"], last_mob_info[0]["mY"])

    i += 1


