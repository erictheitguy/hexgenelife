# Mob Brain

The mob brains are a flow chart style. Each box of the flow chart consists of a function that takes input of a matrix then outputs a matrix or executes a call to the server then ends it processing loop. 

Each server tic the mob starts at the top of the decision tree with a init function. Then depending on the flows connected to it will determine which sub flow it will call. The flows are connected by Gene numbers. Each function does not inhertely know which function it will be calling. It simply takes the input matrix, processes it according the code written in that function and then either makes a call to the server or outputs another matrix that will then get passed to a function. 

The mobs brain gets a memory feature of what it knows. This is stored in a json. The structure is loose in the json as what gets put in there will come from diffrent functions. 

When a function gets called the data it recieves is the matrix from the pervious function. The memory json file, and the output functions that it is connected to if any. 

When a mutation happens during breeding, depending on the type and amount of mutation the workflow can get changed. New functions added or removed. 

The mallebility of the brain is the likely hood that during the mobs life, is the likely hood of new functions being added to the flow. 

There is no limit to the number of functions that are present in the systems repository. 

An example starter function would be that it takes a the amount of fat, hunger and energy that it currently has. and it creates a matrix of [3,4,5]. It knows that it is connected to functions a , b and c. This starter box has a simple call of of matrix[0] >1 go to the first function. This function of a then gets the matrix of [3,4,5]. This function looks at the values and sees that the first value is less then 4. It then makes a call to the server to eat grass. This loop is done for this server tic. 