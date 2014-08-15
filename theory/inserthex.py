import datetime
from pymongo import *

client = MongoClient('candygram',27017)
db = client.map
collection = db.hex_tiles

# the cx and cy are only for the initial hexagon population
# in future we should be getting a center point
# from another hexagon and then drawing a new hexagon
# based upon an existing one in one of the directions
cx = 10
cy = 10

# sizing of the hexagons
# change 100 to whatever unit
oneseg = 10/4
twoseg = oneseg * 2

# new CX and CY are actually the hexagon centers
newCX = cx
newCY = cy

X1 = newCX - twoseg 
Y1 = newCY 

X2 = newCX - oneseg
Y2 = newCY - twoseg

X3 = newCX + oneseg
Y3 = newCY - twoseg

X4 = newCX + twoseg
Y4 = newCY

X5 = newCX + oneseg
Y5 = newCY + twoseg

X6 = newCX - oneseg
Y6 = newCY + twoseg

# dont forget to include the 7th point to close the polygon
X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

print (centerX,centerY)
print (newCX,newCY)

hex1 = {
    "loc" :
    {
      "type": "Polygon",
      "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
    },
    "Water": 0,
    "Grass": 0,
    "Created": datetime.datetime.utcnow()
}
# we also need to insert the center
hex1_center = {
    "loc" :
    {
        "type": "Point",
        "coordinates": [ centerX , centerY ]
        },
     "Created": datetime.datetime.utcnow()   
}
hex_tiles = db.hex_tiles
hex_tiles_center = db.hex_tiles_center
tile_id = hex_tiles.insert(hex1)
center_tile_id = hex_tiles_center.insert(hex1_center)
print (tile_id)
print (center_tile_id)

# should we put the object id on either of the inserts?
