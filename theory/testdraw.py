from tkinter import *

canvas = Canvas(width=300, height=300, bg='white')  
canvas.pack(expand=YES, fill=BOTH)                  

#canvas.create_line(100, 100, 200, 200)             
#canvas.create_line(100, 200, 200, 300)
#canvas.create_polygon(0,50,25,0,75,0,100,50,75,100,25,100,0,50)


cx = 100
cy = 100

# sizing of the hexagons
# change 100 to whatever unit
oneseg = 100/4
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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

print (centerX,centerY)
print (newCX,newCY)

# why figure out the center? we only draw one hexagon polygon
# at a time using the center of only one other hexagon

# draw the above polygon using what we have.
canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7, fill="green")

# create hexagon to bottom right
newCX = cx + twoseg +oneseg
newCY = cy + twoseg 


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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7)


# create hexagon bottom

newCX = cx 
newCY = cy +twoseg +twoseg

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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7,fill="red")

# create hexagon bottom left

newCX = cx - twoseg -oneseg
newCY = cy + twoseg 


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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7,fill="blue")

# create hexagon top left

newCX = cx - twoseg -oneseg
newCY = cy - twoseg 


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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7,fill="purple")

# create hexagon top 

newCX = cx 
newCY = cy - twoseg - twoseg 


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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7,fill="brown")

# create hexagon top  right
newCX = cx +twoseg +oneseg
newCY = cy - twoseg


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

X7 = newCX - twoseg
Y7 = newCY

# what is its center?
centerX = (X1+X2+X3+X4+X5+X6)/6
centerY = (Y1+Y2+Y3+Y4+Y5+Y6)/6

canvas.create_polygon(X1,Y1,X2,Y2,X3,Y3,X4,Y4,X5,Y5,X6,Y6,X7,Y7,fill="yellow")
mainloop()
