# AI Usage

This document summarizes how Artificial Intelligence algorithms are integrated into AI Dungeon Adventure. Rather than concentrating AI in a single gameplay mechanic, the project applies different AI techniques to procedural dungeon generation, enemy behavior, pathfinding, optimization, constraint satisfaction, and adversarial decision-making.

---

# 1. Uniform Cost Search (UCS)

## Purpose

Provide the optimal navigation route from the Laboratory Room to the Boss Room.

## Usage

During dungeon generation, Uniform Cost Search computes the minimum-cost path between the Laboratory Room and the Boss Room.

The generated path is stored before gameplay begins.

After the player completes the Laboratory Room, pressing **M** displays the minimap containing:

- Player Position
- Boss Room
- UCS Navigation Route

Because every movement has equal cost, UCS guarantees the optimal path while also reporting path length, total cost, and expanded nodes for debugging purposes.

## AI Category

Uninformed Search

---

# 2. Greedy Best-First Search

## Purpose

Fast enemy pathfinding.

## Usage

Greedy Best-First Search controls one type of enemy behavior.

At every movement step, the algorithm evaluates neighboring cells using the Manhattan Distance heuristic and always expands the position estimated to be closest to the player.

Since only the heuristic value is considered, Greedy responds very quickly, making it suitable for real-time enemy chasing even though it does not always generate the shortest path.

## AI Category

Informed Search

---

# 3. A* Search

## Purpose

Optimal heuristic pathfinding.

## Usage

A* Search is implemented as a second enemy pathfinding algorithm.

Unlike Greedy Best-First Search, A* considers both:

- accumulated movement cost g(n)
- heuristic estimate h(n)

using

f(n) = g(n) + h(n)

This allows EnemyAStar to compute an optimal path toward the player while maintaining efficient search performance.

The implementation is located in:

- ai/astar.py

and is used by the EnemyAStar class in:

- game/enemy.py

## AI Category

Informed Search

---

# 4. Breadth-First Search (BFS)

## Purpose

Search and validation in a complex dungeon environment.

## Usage

Breadth-First Search is used to validate dungeon connectivity after maze generation and trap placement.

The algorithm explores the maze layer by layer to verify that every important location remains reachable.

BFS ensures that optimization algorithms never create isolated areas or impossible game states.

## AI Category

Search in Complex Environments

---

# 5. Depth-First Search (DFS) Recursive Backtracking

## Purpose

Procedural dungeon generation.

## Usage

The dungeon layout is generated using Recursive Backtracking based on the Depth-First Search algorithm.

Beginning from an initial cell, DFS recursively visits unvisited neighboring cells while carving passages between them.

The result is a fully connected maze that becomes the foundation for all later optimization stages.

## AI Category

Maze Generation

---

# 6. Hill Climbing

## Purpose

Optimize important item placement.

## Usage

Hill Climbing optimizes the placement of:

- Key #3
- Sword
- Torch
- Health Potion

The optimization attempts to:

- maximize exploration
- distribute items evenly
- avoid clustering
- maintain reachability
- avoid spawning near the player
- prevent placement inside protected rooms

Only neighboring states with better evaluation scores are accepted, allowing the algorithm to converge rapidly toward a locally optimal solution.

## AI Category

Local Search

---

# 7. Simulated Annealing

## Purpose

Optimize important room placement.

## Usage

Simulated Annealing determines suitable positions for:

- Boss Room
- Laboratory Room
- Key #4

The optimization attempts to:

- maximize exploration
- maximize distance from player spawn
- satisfy room separation constraints
- avoid overlap
- maintain reachability

Unlike Hill Climbing, Simulated Annealing may temporarily accept worse solutions according to a temperature schedule, allowing it to escape local optima.

## AI Category

Local Search

---

# 8. Forward Checking

## Purpose

Constraint Satisfaction Problem.

## Usage

Forward Checking is implemented as one of the puzzle-solving algorithms.

Whenever a variable is assigned a value, the algorithm immediately removes inconsistent values from the remaining variables' domains.

This early pruning greatly reduces unnecessary search and detects conflicts before deeper exploration occurs.

## AI Category

Constraint Satisfaction

---

# 9. Min-Conflicts

## Purpose

Constraint Satisfaction Problem.

## Usage

Min-Conflicts is implemented as an alternative CSP algorithm.

Instead of performing systematic search, the algorithm begins with a complete assignment and repeatedly selects variables involved in conflicts.

Each selected variable is reassigned the value that minimizes the total number of remaining conflicts.

Because of its iterative repair strategy, Min-Conflicts performs efficiently on large constraint satisfaction problems and complements Forward Checking within the puzzle system.

## AI Category

Constraint Satisfaction

---

# 10. Minimax with Alpha-Beta Pruning

## Purpose

Final Boss Artificial Intelligence.

## Usage

The final boss battle is implemented as a Tic-Tac-Toe strategy game.

The boss evaluates future board states using the Minimax algorithm.

Alpha-Beta Pruning is applied to eliminate branches that cannot influence the final decision, allowing significantly deeper search while producing the same optimal move as the original Minimax algorithm.

## AI Category

Adversarial Search

---

# AI Algorithms Summary

| AI Algorithm | Category | Purpose |
|--------------|----------|---------|
| Uniform Cost Search (UCS) | Uninformed Search | Laboratory → Boss navigation |
| Greedy Best-First Search | Informed Search | Fast enemy pathfinding |
| A* Search | Informed Search | Optimal enemy pathfinding |
| Breadth-First Search (BFS) | Search in Complex Environments | Dungeon validation and reachability |
| DFS Recursive Backtracking | Maze Generation | Procedural dungeon generation |
| Hill Climbing | Local Search | Item placement optimization |
| Simulated Annealing | Local Search | Special room optimization |
| Forward Checking | Constraint Satisfaction | Puzzle solving |
| Min-Conflicts | Constraint Satisfaction | Alternative puzzle solving |
| Minimax with Alpha-Beta Pruning | Adversarial Search | Boss AI |