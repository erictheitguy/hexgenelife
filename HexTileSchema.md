# #SqlLite3 Database schema for the hext tiles

loc : Text
    loc is storing json data.
centerXY: Text
    CenterXY is storing an array
centerX : interger
centerY : interger
hexcp1 : Text
    hexcp1 is storing an array
hexcp2 : Text
    hexcp2 is storing an array
hexcp3 : Text
    hexcp3 is storing an array
hexcp4 : Text
    hexcp4 is storing an array
hexcp5 : Text
    hexcp5 is storing an array
hexcp6 : Text
    hexcp6 is storing an array
hexcp7 : Text
    hexcp7 is storing an array
Water : Real
Grass : Real
Created : datetime.datetime.utcnow()
Updated : datetime.datetime.utcnow()

Sample of a hexagon
"loc" :
        {
          "type": "Polygon",
          "coordinates": [ [ [ X1 , Y1 ] , [ X2 , Y2 ] , [ X3 , Y3 ] , [ X4 , Y4  ] , [X5 , Y5] , [ X6 , Y6 ] , [ X7 , Y7 ] ] ]
        },
        "centerXY": centerX, centerY,
        "centerX": 1,
        "centerY": 1,
        "hexcp1": [X1, Y1],
        "hexcp2": [X2, Y2],
        "hexcp3": [X3, Y3],
        "hexcp4": [X4, Y4],
        "hexcp5": [X5, Y5],
        "hexcp6": [X6, Y6],
        "hexcp7": [X7, Y7],
        "Water": 1,
        "Grass": 2,
        "Created": datetime.datetime.utcnow()
        "Updated": datetime.datetime.utcnow()
