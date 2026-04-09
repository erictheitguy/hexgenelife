# hexgenelife

===========
An expansion on Conways game of life.

Learning expirence in genetic adaption models in a simplifed computer simulation.
Requirements -> requirements.md

Parts:
A server that clients connect to. The server connects to a sqllite3 database that contains the data. The server and clients will operate on a tick schedule. In that each client gets a limited amount of actions it can perform per tick. The server will keep track of all active mobs and once all active mobs have performed their actions for that tick, it will inform connected clients that they can began submitting the next set of actions. The server will also handle informing the client if two mobs interacted and the outcome of that interactions. Interactions could be breding or attacking in order to reduce the health of a mob so that it may be consumed for food.
See folder server_doc for more infomation.  

A viewer that allows a user to see the simulated world. It connects directly to the sqllite database. It only performs read only actions. The controls allow you to pan /zoom around the world. Click on mobs and view the information about them.
See folder viewer_doc for more infomation.

A client which represents the mobs. It will connect to the server. It will be able to process a certain number of mobs. It will take in a list of ids which represent the ids of the mobs it should process.
See folder client_doc for more infomation.

Schema for the game world of hex tiles is HexTileSchema.md
Schema for the mobs is MobSchema.md
