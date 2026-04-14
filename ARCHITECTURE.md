# High-Level Architecture Design Document

This document outlines the high-level architecture for the HexGenLife project, detailing the structure of the tile system, the mob system, the communication layer, schema summaries, and component workflows.

## System Components

- **Tile System:** Manages the spatial layout and properties of the game world tiles.
- **Mob System:** Manages the state, behavior, and lifecycle of all entities (mobs) within the world.
- **Communication Layer:** Handles all real-time data exchange between the client and the server, including WebSocket message protocols.
- **Schema Summaries:** Provides concise overviews of the main data structures (`HexTileSchema`, `MobSchema`, etc.).

## Component Workflows

1. **Initialization:** Server initializes world state, loads initial mob configurations, and establishes the WebSocket connection.
2. **Tile Update Cycle:** Server processes tile state changes and broadcasts relevant updates to connected clients.
3. **Mob Lifecycle:** Mobs update their internal states (hunger, health, cognition) based on environmental factors and interactions.
4. **Client Interaction:** Clients send input/requests via WebSocket; the server processes these, updates state, and sends back necessary state updates.

## Data Flow

Data flows primarily from the server state, through the WebSocket layer, to the client for rendering and interaction. Schema definitions guide the structure of all data transmitted and stored.

---

## Project Architecture Design

This document outlines the high-level design and architectural structure of the HexGenLife project, focusing on the coherence between the client, server, and the core data schemas (HexTileSchema and MobSchema).

## 1. Overview

The system is divided into three main functional areas:

1. **Tile System:** Manages the spatial data, terrain, and resources of the hexagonal map.
2. **Mob System:** Manages the entities (mobs), their genetic traits, health, and cognitive state.
3. **Communication Layer:** Handles real-time data exchange between the client and the server via WebSockets.

## 2. Data Schemas Summary

### 2.1. Hex Tile Schema (`HexTileSchema.md`)

This schema defines the static and dynamic properties of each hex tile in the world.

- **Key Data:** Location (`loc`, `centerXY`), Hexagonal coordinates (`hexcp1` to `hexcp7`), Terrain resources (`Water`, `Grass`).
- **Design Consideration:** This data is likely authoritative on the server, and clients will request tile data based on their position.

### 2.2. Mob Schema (`MobSchema.md`)

This schema defines the complex state of each mobile entity, logically separated into three distinct entities:

- **MobGene:** Stores immutable or slowly changing genetic and trait data (e.g., `mob_type`, `genome`, `fitness_score`). This serves as the entity's core identity.
- **MobHealth:** Stores dynamic, real-time stats (e.g., `Hunger`, `Health`, `Age`). This handles immediate state changes.
- **MobBrain:** Stores cognitive state data. This allows for modular updates to the mob's intelligence.
- **Design Consideration:** The separation into Gene, Health, and Brain suggests a modular approach, allowing independent scaling and updates to different aspects of the mob entity.

## 3. Component Interaction & Workflow

### 3.1. Server-Client Communication Workflow

1. **Client Request:** The client sends position updates or queries for tile/mob data to the server via WebSocket.
2. **Server Processing:**
    - **Tile Queries:** Server uses `HexTileSchema` to retrieve tile data based on coordinates.
    - **Mob Updates:** Server processes state changes by interacting with the modular `MobSchema`:
        - Updates to genetic traits are handled by `MobGene`.
        - Real-time stat updates (e.g., consumption, damage) are handled by `MobHealth`.
        - Cognitive state updates are handled by `MobBrain`.
    - **Server Response:** Server sends updated state information back to the client, reflecting the merged state from the three schema components.

### 3.2. Mob Lifecycle Workflow (Conceptual)

This workflow describes how a mob's state evolves, driven by interactions between the schema components:

```mermaid
graph TD
    A[Mob Created] --> B{Initialize MobGene, MobHealth, MobBrain};
    B --> C[Update MobHealth (Initial Stats)];
    C --> D[Mob Acts/Interacts];
    D --> E{Check Conditions (Hunger, Health)};
    E -- Needs Update --> F[Update MobHealth / MobBrain];
    E -- Death Condition Met --> G[Update MobGene (Death Flag)];
    G --> H[Mob Deceased/Removed];
    F --> D;
```

## 4. Architectural Decisions

- **Data Source of Truth:** The Server is the single source of truth for all schema data.
- **Decoupling:** The separation of `MobGene`, `MobHealth`, and `MobBrain` allows for independent scaling and updates to different aspects of the mob entity.
- **Client Responsibility:** The client is responsible for rendering the state received from the server and sending user inputs/actions to the server.
- **Consistency:** All client/server interactions must be validated against the authoritative schemas defined in this document.

---
*This document is for design and architecture review only. No code changes are permitted.*
