# Requirements

Database sqllite3
Server is written in python
Client is written in python
Viewer is written in python using pygame.
Protocol: WebSocket for communication

User mermaid style for workflow and design outline.

Try to maintain test driven develeopment.

## Game World

Game world is a tiled hexagonal grid. The tiles have properties like water and grass. The game world is controlled by the server. There are sub processes that control the world such as rain and grass growing. 

## Server

The server is the heart of the game. It is responsible for maintaining the state of the game world and the mobs. It is also responsible for handling the communication between the client and the server. The server is written in python and uses sqlite3 for the database. The server is multi-threaded and uses a queue system to communicate between the threads. The main thread handles the game loop and the client connections. There are sub processes that control the world such as rain and grass growing. 

## Client

The client is the handler for the mobs. It connects to the server and runs different mobs with in it. It handles the communcication between the mobs and the server.

## Mobs

Mobs are the agents that live in the game world. They are controlled by the client and communicate with the server. They have a variety of parameters. They can reproduce, eat and die. They are defined by their parameters in the database. The intent is to be able to have two types of initial mobs to seed the world with. One archetype is a prey mob that eats grass. The other archetype is a predator mob that eats other mobs. The mobs breed and have mutation functions that alter the mobs brain and phyiscal characteristics. Goal is to see natural selection and evolution play out over time. When a new server is spun up the two archetypes are seeded into the world and left to interact. The intial archetypes should be defined enough to not die out immediately but not so well defined that there is not room for evolution to take place. 

## Viewer

The viewer allows the user to see the game world and the mobs. It connects to the server and displays the game world and the mobs. 

