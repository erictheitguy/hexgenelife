import math

# starting point
x0 = 1.0
y0 = 1.5

# theta is the angle (in radians) of the direction in which to move
#theta = math.pi/6
i = 0
while i < 360:
    deg = i
    corrected_deg = 90 - deg
    theta = math.radians(corrected_deg)
    r = 2.0
    deltax = r*math.cos(theta)
    deltay = r*math.sin(theta)
    x1 = x0 + deltax
    y1 = y0 + deltay
    print(x1,y1)
    i += 1

# add each point point to document

# add center to document

# on center add X Y 

# graph out each point make distances bigger to figure out
