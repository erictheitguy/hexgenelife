# Mob Schema

Mob schema is broken into multiple tables and joined by ID. The tables reflect the schema initialized in `server.py`.

**Table mobs**
mob_id : Text PRIMARY KEY
position : Text (JSON object with integer "x" and "y" coordinates)
mob_type : Text
generation : Integer
timestamp : Real

**Table mob_genes**
mob_id : Text
mobType : Text
fitnessScore : Real
death : Real (Timestamp of death, NULL if not dead)
expired : Boolean (Flag if gene has expired)
PRIMARY KEY (mob_id, mobType)

**Table mob_health**
mob_id : Text PRIMARY KEY
hunger : Real
fat : Real
health : Real
age : Real

**Table mob_brain**
mob_id : Text PRIMARY KEY
cognition_attributes : Text
