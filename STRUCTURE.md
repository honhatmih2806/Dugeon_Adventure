# Project Structure
AI_Dungeon_Adventure/
│
├── ai/
│   ├── alpha_beta.py              # Alpha-Beta Pruning optimization
│   ├── astar.py                   # A* pathfinding
│   ├── bfs.py                     # Breadth-First Search
│   ├── forward_checking.py        # Forward Checking CSP solver
│   ├── greedy.py                  # Greedy Best-First Search
│   ├── hill_climbing.py           # Hill Climbing optimization
│   ├── map_constraints.py         # Placement constraint utilities
│   ├── min_conflicts.py           # Min-Conflicts CSP solver
│   ├── min_conflicts_boss.py      # Boss puzzle helper using Min-Conflicts
│   ├── minimax.py                 # Minimax search
│   ├── simulated_annealing.py     # Simulated Annealing optimization
│   └── ucs.py                     # Uniform Cost Search
│
├── assets/
│   ├── maps/
│   ├── sounds/
│   ├── sprites/
│   ├── sprite_manager.py
│   ├── font_cache.py
│   └── make_placeholders.py
│
├── game/
│   ├── boss.py                    # Boss entity
│   ├── combat.py                  # Combat mechanics
│   ├── enemy.py                   # Enemy AI controller
│   ├── game_state.py              # Global game state
│   ├── inventory.py               # Inventory management
│   ├── item.py                    # Item definitions
│   ├── player.py                  # Player controller
│   └── trap.py                    # Trap definitions
│
├── maps/
│   ├── boss_arena.py              # Tic-Tac-Toe boss arena
│   ├── dungeon.py                 # Main dungeon generation
│   ├── fog_of_war.py              # Fog of war system
│   ├── map_loader.py
│   ├── maze_generator.py          # DFS Recursive Backtracking maze generation
│   └── room.py                    # Room definitions
│
├── systems/
│   ├── boss_ai_system.py          # Boss AI controller
│   ├── boss_battle.py             # Boss battle management
│   ├── item_system.py             # Item interactions
│   ├── laboratory_system.py       # Laboratory room logic
│   ├── pathfinding_system.py      # Pathfinding wrapper
│   └── trap_system.py             # Trap generation & validation
│
├── ui/
│   ├── game_over.py
│   ├── hud.py                     # HUD & inventory display
│   ├── inventory_ui.py            # Inventory window
│   ├── laboratory_ui.py           # Laboratory UI
│   └── menu.py
│
├── AI_USAGE.md
├── CLAUDE.md
├── PROJECT_CONTEXT.md
├── STRUCTURE.md
├── TASK_LIST.md
├── config.py
└── main.py                        # Game entry point