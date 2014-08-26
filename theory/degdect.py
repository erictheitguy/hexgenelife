import math

life_loc_x = 10
life_loc_y = 11
old_hex_center = [10,10]
xdiff = life_loc_x - old_hex_center[0]
ydiff = life_loc_y - old_hex_center[1]
print(xdiff,ydiff, " diffs")
angle_points = math.degrees(math.atan2(ydiff,xdiff))
print(angle_points, " unconverted angle")
# 180 unconverted is really 270
if angle_points < 0:
    angle_points = abs(angle_points) + 90
else:
    angle_points = 90 - angle_points
if angle_points < 0:
    angle_points = angle_points + 360
print(angle_points, " final angle")
