# # Mob Schema

Mob schema is broken into multiple tables and joined by ID.

First table is the Mob Gene Type.
Second table is the Mob health stats.
Third table is the mob brain.

**Table MobGene**
ID : Integer PRIMARY KEY
mob_type : Text
generation : Integer
parent_ids : Text
genome : Text
actual_traits : Text
    JSON Data
fitness_score : Real
death : Text (TimeStamp)
expired : integer
    Death flag if alive or not.
Created : Text (TimeStamp)
Updated : Text (TimeStamp)

**Table MobHealth**
ID : Integer PRIMARY KEY
Hunger : Real
Fat : Real
Health : Real
Age : Real
Updated : Text (TimeStamp)

**Table MobBrain**
ID : Integer PRIMARY KEY
Updated: Text (TimeStamp)
