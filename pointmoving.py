
import math

# starting point
x0 = 1.0
y0 = 1.5

# theta is the angle (in radians) of the direction in which to move
theta = math.pi/6

# r is the distance to move
r = 2.0

deltax = r*math.cos(theta)
deltay = r*math.sin(theta)

# new point
x1 = x0 + deltax
y1 = y0 + deltay

print "The new point is (%.5f,%.5f)." % (x1,y1)


# add each point point to document

# add center to document

# on center add X Y 

#graph out each point make distances bigger to figure out