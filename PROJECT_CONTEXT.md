# AI Dungeon Adventure - Project Context

## Project Overview

AI Dungeon Adventure is a 2D dungeon exploration game developed with Python and Pygame for the Artificial Intelligence course.

The objective of the game is to explore a randomly generated dungeon, collect all required keys, unlock the boss room, and defeat the final boss. The project demonstrates the application of multiple Artificial Intelligence algorithms in different gameplay systems instead of using AI only for enemy movement.

The dungeon is generated procedurally every time the game starts, ensuring that each playthrough is different while remaining fully solvable.

---

# Current Gameplay Flow

1. Generate a random dungeon using DFS Recursive Backtracking.
2. Optimize special room placement using Simulated Annealing.
3. Optimize important item placement using Hill Climbing.
4. Validate trap placement to ensure the dungeon is always completable.
5. Randomly select a valid player spawn position.
6. Explore the dungeon.
7. Collect Keys #1 - #4.
8. Visit the Laboratory Room to unlock the minimap.
9. Enter the Boss Room.
10. Defeat the boss in a Tic-Tac-Toe battle powered by Minimax with Alpha-Beta Pruning.
11. Win the game.

---

# Artificial Intelligence Algorithms

The project demonstrates six major AI algorithm groups.

## Uninformed Search

### Uniform Cost Search (UCS)

Used to compute and visualize the optimal navigation route from the Laboratory Room to the Boss Room after the player unlocks the Laboratory.

The minimap displays this optimal route as navigation assistance.

---

## Informed Search

### Greedy Best-First Search

Used by enemy AI to pursue the player.

The heuristic function is the Manhattan Distance between the enemy and the player.

---

## Search in Complex Environments

### Breadth-First Search (BFS)

Breadth-First Search is used to explore the dungeon level by level in complex maze environments.

In this project, BFS is applied for environment exploration and path validation tasks, ensuring that important locations remain reachable and demonstrating uninformed search in a complex environment where the complete map is not initially known.

---

## Maze Generation

### Depth-First Search (DFS) Recursive Backtracking

The dungeon layout is generated using Recursive Backtracking, a Depth-First Search based maze generation algorithm.

DFS recursively visits unvisited neighboring cells, carving passages until every cell has been explored. This guarantees that the generated maze is fully connected and every important location is reachable before later optimization algorithms place special rooms and items.

---

## Local Search

### Hill Climbing

Optimizes placement of:

- Key #3
- Sword
- Torch
- Health Potion

Optimization goals:

- Reachable positions
- Good distribution
- Avoid clustering
- Keep away from spawn

---

## Constraint Satisfaction

### Forward Checking

Used inside the puzzle system.

The algorithm validates future variable domains while constructing solutions, reducing invalid search branches compared with plain Backtracking.

Puzzle rooms remain in the dungeon for demonstrating CSP algorithms.

---

## Adversarial Search

### Minimax with Alpha-Beta Pruning

Used by the final boss.

The boss evaluates future board states using the Minimax algorithm while Alpha-Beta Pruning removes unnecessary branches, allowing deeper search with significantly better performance without changing the final decision.

---

# Dungeon Structure

Every generated dungeon contains:

- Spawn Position
- Boss Room
- Laboratory Room
- Puzzle Room (Forward Checking)
- Puzzle Room (Min-Conflicts)
- Four Keys
- Enemies
- Traps
- Weapons
- Torches
- Health Potions

All important locations are validated to remain reachable.

---

# Laboratory System

The Laboratory Room is an optional special room.

After interacting with it:

- The laboratory becomes completed.
- The minimap feature is permanently unlocked.
- The player can toggle the minimap using the M key.

The minimap displays only:

- Player position
- Boss Room
- UCS navigation route

---

# Item System

Current collectible items include:

- Sword
- Torch
- Health Potion
- Four Keys

Health Potions are consumed immediately when collected.

Weapons and torches remain inside the player's inventory.

Keys are required to unlock the boss encounter.

---

# Enemy System

Enemies continuously search for the player using Greedy Best-First Search.

Enemy spawning is validated so they never appear inside:

- Boss Room
- Laboratory Room
- Puzzle Rooms

---

# Trap System

Trap placement is validated after generation.

The validation guarantees:

- Every important room remains reachable.
- Traps never block the only valid route.
- The dungeon can always be completed.

---

# Boss Battle

The final boss is encountered after collecting all required keys.

Instead of traditional combat, the boss battle is implemented as a Tic-Tac-Toe strategy game.

The boss AI uses:

- Minimax
- Alpha-Beta Pruning

to determine the optimal move for each turn.

---

# Development Principles

The project emphasizes:

- Modular architecture
- Independent AI algorithms
- Separation between gameplay systems
- Reusable AI implementations
- Easy algorithm comparison
- Procedural content generation