# Sokoban with AI Solver

A 2D Sokoban (box-pushing) puzzle game built with **Python + Pygame**, where AI search algorithms can solve levels automatically.

> Group project – *Artificial Intelligence* course, Ho Chi Minh City University of Industry and Trade (HUIT), Group 08, 2026.
> Team of 6. **My role (Nguyen Thu Thao): level / map design.**

## Features
- 4 levels with progressive difficulty, from a starter map to large symmetric "fortress" maps
- Smooth movement & push animation, HUD with steps, timer, progress and AI status
- Undo with a per-level budget (`Z`), restart (`R`), level select menu
- Win / lose detection with sound effects
- **AI solvers** (toggle with `Tab`):
  - **Greedy best-first + Tabu list**: priority-queue search with a Hungarian-algorithm box-to-goal matching heuristic, goal-packing order and smart restarts
  - **Hill Climbing**: local search over push-only successor states
- Deadlock detection: static dead squares, 2×2 freeze patterns and frozen box clusters

## Run
```bash
pip install -r requirements.txt
python main.py
```

| Key | Action |
|---|---|
| Arrow keys | Move / push |
| `Z` | Undo |
| `R` | Restart level |
| `Tab` | Turn on / choose AI solver |
| `Esc` | Back to menu |

## Level format
Levels live in [`src/levels.py`](src/levels.py). Each map is a list of strings: `1` = wall, `0` = floor, `2` = goal, `3` = box, `4` = player.

## Project structure
```
main.py            entry point
src/game.py        game loop, input, screens
src/logic.py       game state, collision, deadlocks, AI solvers
src/levels.py      level data
src/render.py      drawing, src/ui.py menus & HUD, src/animation.py
assets/            sprites (Kenney), background, sounds
```

## Credits
- Sprites: [Kenney Sokoban pack](https://kenney.nl/assets/sokoban) (CC0)
- Team members: Nguyen Thi Bich Huong, Doan Yen Nhi, Cao Le Phuong Nghi, Nguyen Thu Thao, Nguyen Thi Kieu Trang, Lam Phuong Vi
