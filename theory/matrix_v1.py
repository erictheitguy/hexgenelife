from pymongo import *
import random
import math
import theory.grass_eater
import theory.HexSearch
import theory.inserthex

# select all mobs
# for now just grass eaters

client = MongoClient('candygram', 27017)
db_mob = client.mob
grass_eater_collection = db_mob.grasseater

all_grass_eaters = grass_eater_collection.find()

