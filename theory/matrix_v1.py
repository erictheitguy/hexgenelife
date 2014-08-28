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
db_map = client.map
hex_growing = db_map.hex_tiles

grass_eaters_ids = grass_eater_collection.distinct("mob_id")
i = 0

while i < 50:
    for grass_eater in grass_eaters_ids:
        last_mob_info = grass_eater_collection.find({"$query": {"mob_id": grass_eater}, "$orderby":{"Created": -1}}).limit(1)
        # got current mob info

        # lets check to make sure all surrounding tiles exist
        # first get the hex we are inside
        hex_im_inside_id = theory.hexsearch.HexSearch.in_hex(last_mob_info[0]["mX"], last_mob_info[0]["mY"])
        hex_to_check = theory.hexsearch.HexSearch.hex_tile_collection.find({"_id": hex_im_inside_id})
        theory.create_hex.create_surrounding_hex(hex_to_check[0]["centerX"],hex_to_check[0]["centerY"], 10)
        stork = theory.grass_eater.GrassEater
        stork.motivate(last_mob_info[0]["_id"], last_mob_info[0]["mX"], last_mob_info[0]["mY"])

    hex_growing.update({"$and": [ {"Water": {"$gt": 2} }, {"Grass": { "$lt":99}} ]},
        { "$inc": { "Water": -2} , "$inc": {"Grass": 1},"$inc": {"Water": -2} }, upsert=True,multi=True)
    hex_growing.update({"Water": {"$lt": 100} }, { "$inc": { "Water": 1} }, upsert = False, multi = True)

    i += 1


