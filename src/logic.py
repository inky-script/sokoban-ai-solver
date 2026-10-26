import collections
import functools
import heapq
import random
import time
from dataclasses import dataclass, field

@dataclass
class MoveResult:
    moved: bool
    pushed: bool = False
    box_from: tuple[int, int] | None = None
    box_to: tuple[int, int] | None = None


@dataclass
class GameState:
    name: str
    rows: list[str]
    walls: set[tuple[int, int]] = field(default_factory=set)
    targets: set[tuple[int, int]] = field(default_factory=set)
    boxes: set[tuple[int, int]] = field(default_factory=set)
    player: tuple[int, int] = (0, 0)
    steps: int = 0
    undo_stack: list[tuple[tuple[int, int], frozenset[tuple[int, int]], int]] = field(default_factory=list)

    @classmethod
    def from_rows(cls, name: str, rows: list[str]) -> "GameState":
        state = cls(name=name, rows=rows)
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "1":
                    state.walls.add((r, c))
                elif ch == "2":
                    state.targets.add((r, c))
                elif ch == "3":
                    state.boxes.add((r, c))
                elif ch == "4":
                    state.player = (r, c)
        state.static_deadlocks = _precompute_deadlocks(state.walls, state.targets, len(rows), len(rows[0]))
        return state

    def save_undo(self) -> None:
        self.undo_stack.append((self.player, frozenset(self.boxes), self.steps))

    def undo(self) -> None:
        if not self.undo_stack:
            return
        player, boxes, steps = self.undo_stack.pop()
        self.player = player
        self.boxes = set(boxes)
        self.steps = steps

    def try_move(self, dr: int, dc: int) -> MoveResult:
        nr, nc = self.player[0] + dr, self.player[1] + dc
        if (nr, nc) in self.walls:
            return MoveResult(moved=False)
        self.save_undo()
        if (nr, nc) in self.boxes:
            nnr, nnc = nr + dr, nc + dc
            if (nnr, nnc) in self.walls or (nnr, nnc) in self.boxes:
                self.undo_stack.pop()
                return MoveResult(moved=False)
            self.boxes.remove((nr, nc))
            self.boxes.add((nnr, nnc))
            self.player = (nr, nc)
            self.steps += 1
            return MoveResult(True, True, (nr, nc), (nnr, nnc))
        self.player = (nr, nc)
        self.steps += 1
        return MoveResult(True, False)

    def is_complete(self) -> bool:
        return len(self.boxes) > 0 and all(b in self.targets for b in self.boxes)

    def is_deadlocked(self) -> bool:
        if self.is_complete():
            return False

        # 1. Existing checks: boxes in static deadlocked positions or 2x2 freezes
        for b in self.boxes:
            if b in self.targets:
                continue
            if b in self.static_deadlocks:
                return True
            if _is_2x2_freeze(b[0], b[1], self.boxes, self.walls, self.targets):
                return True

        # 2. Player-Box reachability check
        # If the player cannot perform ANY push move, it's a deadlock.
        reachable = _reachable_cells(self.player, self.walls, self.boxes)
        
        any_push_possible = False
        for b in self.boxes:
            for dr, dc in DIRECTIONS:
                push_from = (b[0] - dr, b[1] - dc)
                push_to = (b[0] + dr, b[1] + dc)
                
                # Player must be able to stand on 'push_from' to push box b to 'push_to'
                if push_from in reachable:
                    # 'push_to' must be within bounds and empty
                    if 0 <= push_to[0] < len(self.rows) and 0 <= push_to[1] < len(self.rows[0]):
                        if push_to not in self.walls and push_to not in self.boxes:
                            any_push_possible = True
                            break
            if any_push_possible:
                break
        
        if not any_push_possible:
            if any(b not in self.targets for b in self.boxes):
                return True
            if len(reachable) <= 1 and not self.is_complete():
                return True
        
        # 3. Check for boxes that can NO LONGER reach any target because they are 
        # blocked by other boxes in a narrow space (even if not strictly frozen)
        for b in self.boxes:
            if b in self.targets: continue
            # If a box is in a 1-tile wide corridor and blocked by another box
            r, c = b
            h_corridor = (r-1, c) in self.walls and (r+1, c) in self.walls
            v_corridor = (r, c-1) in self.walls and (r, c+1) in self.walls
            if h_corridor:
                # Blocked H?
                if (r, c-1) in self.boxes or (r, c+1) in self.boxes:
                    # If it's a corridor and there are multiple boxes, 
                    # and no target in reach...
                    pass # Handled by freeze cluster mostly, but could add more here
            
        # 4. Freeze cluster check (boxes blocking each other)
        if _is_freeze_cluster(self.boxes, self.walls, self.targets):
            return True
            
        return False



DIRECTIONS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def _parse_level_map(rows):
    walls, targets, boxes = set(), set(), set()
    player = (0, 0)
    R, C = len(rows), len(rows[0])
    for r in range(R):
        for c in range(C):
            ch = rows[r][c]
            if ch == "1":
                walls.add((r, c))
            elif ch == "2":
                targets.add((r, c))
            elif ch == "3":
                boxes.add((r, c))
            elif ch == "4":
                player = (r, c)
    return walls, targets, boxes, player, R, C


def _precompute_deadlocks(walls, targets, R, C):
    """
    Standard pull-based static deadlock detection.
    A cell is NOT a static deadlock if a box can be 'pulled' from a target to that cell.
    Pulling: A box at B can be pulled to A if the player can stand at C to pull it.
    (Player at C, Box at B) -> (Player at B, Box at A)
    Requirement: A and C must be empty (non-wall).
    """
    not_deadlock = set()
    queue = collections.deque()
    
    for t in targets:
        not_deadlock.add(t)
        queue.append(t)
        
    while queue:
        br, bc = queue.popleft()
        for dr, dc in DIRECTIONS:
            # Try to pull box from (br, bc) to (pr, pc)
            # pr, pc is where the box ends up. ar, ac is where the player stands.
            pr, pc = br + dr, bc + dc
            ar, ac = br + 2*dr, bc + 2*dc
            
            if 0 <= pr < R and 0 <= pc < C and (pr, pc) not in walls:
                if 0 <= ar < R and 0 <= ac < C and (ar, ac) not in walls:
                    if (pr, pc) not in not_deadlock:
                        not_deadlock.add((pr, pc))
                        queue.append((pr, pc))
                    
    static_deadlocks = set()
    for r in range(R):
        for c in range(C):
            if (r, c) not in walls and (r, c) not in not_deadlock:
                static_deadlocks.add((r, c))
    return static_deadlocks


def _is_2x2_freeze(r, c, boxes, walls, targets):
    for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        g = [(r, c), (r + dr, c), (r, c + dc), (r + dr, c + dc)]
        if all(p in walls or p in boxes for p in g):
            if any(p in boxes and p not in targets for p in g):
                return True
    return False


def _goal_priority(targets, walls):
    gp = {}
    for tr, tc in targets:
        wa = sum(1 for dr, dc in DIRECTIONS if (tr + dr, tc + dc) in walls)
        gp[(tr, tc)] = wa * 25000
    return gp


def _normalize_state(player, boxes, walls):
    """Normalize player position to reachable area hash for better state dedup."""
    return (player, boxes)

# ─────────────────────────────────────────────
# Hungarian algorithm for optimal box-target matching
# ─────────────────────────────────────────────

def _hungarian_solve(cost):
    """O(n^3) Hungarian algorithm. Returns minimum total cost for NxN matrix."""
    n = len(cost)
    if n == 0:
        return 0
    INF = float("inf")
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]
    total = 0
    for j in range(1, n + 1):
        if p[j] != 0:
            total += cost[p[j] - 1][j - 1]
    return total


# ─────────────────────────────────────────────
# 1) GREEDY + TABU (Bounded best-first + goal packing + smart restarts)
# ─────────────────────────────────────────────

def _is_freeze_cluster(boxes_set, walls, targets):
    """
    Check if any box NOT on a target is permanently frozen.
    A box is frozen if it can never be pushed horizontally AND never be pushed vertically.
    """
    # 1. Find all boxes that can EVER be pushed Right/Left
    can_r = set()
    can_l = set()
    changed = True
    while changed:
        changed = False
        for b in boxes_set:
            r, c = b
            if b not in can_r:
                # To push right: Left side must not be a wall, and Right side must be 
                # either empty or a box that can also be pushed right.
                if (r, c-1) not in walls and \
                   ((r, c+1) not in walls and ((r, c+1) not in boxes_set or (r, c+1) in can_r)):
                    can_r.add(b)
                    changed = True
            if b not in can_l:
                if (r, c+1) not in walls and \
                   ((r, c-1) not in walls and ((r, c-1) not in boxes_set or (r, c-1) in can_l)):
                    can_l.add(b)
                    changed = True

    # 2. Find all boxes that can EVER be pushed Up/Down
    can_u = set()
    can_d = set()
    changed = True
    while changed:
        changed = False
        for b in boxes_set:
            r, c = b
            if b not in can_u:
                if (r+1, c) not in walls and \
                   ((r-1, c) not in walls and ((r-1, c) not in boxes_set or (r-1, c) in can_u)):
                    can_u.add(b)
                    changed = True
            if b not in can_d:
                if (r-1, c) not in walls and \
                   ((r+1, c) not in walls and ((r+1, c) not in boxes_set or (r+1, c) in can_d)):
                    can_d.add(b)
                    changed = True

    # A box is frozen H if it can move neither Left nor Right
    # A box is frozen V if it can move neither Up nor Down
    for b in boxes_set:
        if b not in targets:
            frozen_h = (b not in can_r and b not in can_l)
            frozen_v = (b not in can_u and b not in can_d)
            if frozen_h and frozen_v:
                return True
                
    return False


class StrategicProAI:
    LABEL = "Greedy + Tabu"
    DESC = "Tìm kiếm tham lam kết hợp danh sách Tabu. Nhanh, chạy real-time."

    def __init__(self) -> None:
        self.max_restarts = 100
        self._max_stale_restarts = 10
        self.ai_mode = False
        self.failed = False
        self.reset_internal()

    def reset_internal(self) -> None:
        self.walls, self.targets, self.boxes = set(), set(), set()
        self.goal_priority, self.static_deadlocks = {}, set()
        self.steps = self.no_improve = self.restart_count = 0
        self.best_h = float("inf")
        self.failed = False
        # Do not reset self.ai_mode here as it kills the AI loop on restart
        self.player = (0, 0)
        self.R = self.C = 0
        self.current_idx = 0
        self._level_data = None
        self._solution = None
        self._sol_idx = 0
        self._planned_path = []
        self._plan_goal = None
        self._last_dir = None
        self._last_pushed = False
        self._visited_global = set()
        self._player_recent = collections.deque(maxlen=16)
        self._boxes_at_recent = None
        self._stale_count = 0
        self._h_cache = {}
        self._target_ranks = {}
        self._corner_targets = set()
        self._wall_targets = set()
        self._open_targets = set()
        self._bfs_dist_cache = {}
        self._frozen_cache = {}
        self._best_state = None
        self._best_global_h = float("inf")
        self._restarts_without_global_improve = 0
        self._h_at_last_restart = float("inf")

    def load_from_state(self, state: GameState) -> None:
        self.reset_internal()
        self.R, self.C = len(state.rows), len(state.rows[0])
        self.walls = set(state.walls)
        self.targets = set(state.targets)
        self.boxes = set(state.boxes)
        self.player = state.player
        self._rows = state.rows
        self.static_deadlocks = _precompute_deadlocks(self.walls, self.targets, self.R, self.C)
        self.goal_priority = _goal_priority(self.targets, self.walls)
        self._classify_targets()
        self._precompute_bfs_distances()

    def load_from_level_data(self, level_data: list[dict], idx: int) -> None:
        self._level_data = level_data
        self.current_idx = idx
        m = level_data[idx]["map"]
        self.reset_internal()
        self._level_data = level_data
        self.current_idx = idx
        self.R, self.C = len(m), len(m[0])
        self._rows = m
        self.walls, self.targets, self.boxes, self.player, _, _ = _parse_level_map(m)
        self.static_deadlocks = _precompute_deadlocks(self.walls, self.targets, self.R, self.C)
        self.goal_priority = _goal_priority(self.targets, self.walls)
        self._classify_targets()
        self._precompute_bfs_distances()

    def _reload_level(self) -> None:
        if self._level_data is not None:
            saved_visited = self._visited_global
            saved_bfs = self._bfs_dist_cache
            saved_best = self._best_state
            saved_best_h = self._best_global_h
            saved_restarts = self.restart_count
            saved_stale = self._restarts_without_global_improve
            saved_h_last = self._h_at_last_restart
            self.load_from_level_data(self._level_data, self.current_idx)
            self._visited_global = saved_visited
            self._bfs_dist_cache = saved_bfs
            self._best_state = saved_best
            self._best_global_h = saved_best_h
            self.restart_count = saved_restarts
            self._restarts_without_global_improve = saved_stale
            self._h_at_last_restart = saved_h_last

    def _restore_best_state(self):
        if self._best_state and self._level_data:
            self._reload_level()
            player, boxes_fs = self._best_state
            self.player = player
            self.boxes = set(boxes_fs)

    # ── Target classification ──

    def _classify_targets(self):
        self._corner_targets = set()
        self._wall_targets = set()
        self._open_targets = set()
        self._target_ranks = {}
        for t in self.targets:
            r, c = t
            wadj = sum(1 for dr, dc in DIRECTIONS if (r + dr, c + dc) in self.walls)
            self._target_ranks[t] = wadj
            if wadj >= 2:
                self._corner_targets.add(t)
            elif wadj == 1:
                self._wall_targets.add(t)
            else:
                self._open_targets.add(t)

    # ── BFS distance precomputation ──

    def _precompute_bfs_distances(self):
        self._bfs_dist_cache = {}
        for target in self.targets:
            dist = {}
            queue = collections.deque([target])
            dist[target] = 0
            while queue:
                r, c = queue.popleft()
                d = dist[(r, c)]
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if (nr, nc) not in self.walls and (nr, nc) not in dist:
                        dist[(nr, nc)] = d + 1
                        queue.append((nr, nc))
            self._bfs_dist_cache[target] = dist

    def _bfs_distance(self, cell, target):
        td = self._bfs_dist_cache.get(target)
        if td is None:
            return abs(cell[0] - target[0]) + abs(cell[1] - target[1])
        return td.get(cell, 9999)

    # ── Frozen box detection (cached) ──

    def _frozen_on_target(self, boxes_fs):
        if boxes_fs in self._frozen_cache:
            return self._frozen_cache[boxes_fs]
        boxes_set = set(boxes_fs) if isinstance(boxes_fs, frozenset) else boxes_fs
        frozen = set()
        walls_ext = set(self.walls)
        changed = True
        while changed:
            changed = False
            for b in boxes_set:
                if b in frozen or b not in self.targets:
                    continue
                r, c = b
                h_stuck = (r, c - 1) in walls_ext and (r, c + 1) in walls_ext
                v_stuck = (r - 1, c) in walls_ext and (r + 1, c) in walls_ext
                if h_stuck or v_stuck:
                    frozen.add(b)
                    walls_ext.add(b)
                    changed = True
        key = boxes_fs if isinstance(boxes_fs, frozenset) else frozenset(boxes_fs)
        if len(self._frozen_cache) < 300000:
            self._frozen_cache[key] = (frozen, walls_ext)
        return frozen, walls_ext

    # ── Advanced heuristic with goal packing ──

    def _push_heuristic(self, new_boxes_fs):
        if new_boxes_fs in self._h_cache:
            return self._h_cache[new_boxes_fs]
        boxes = set(new_boxes_fs)
        score = 0
        frozen, _ = self._frozen_on_target(new_boxes_fs)
        n_frozen = len(frozen)
        score -= n_frozen * 300000
        on_target_unfrozen = (boxes & self.targets) - frozen
        n_on_target = len(on_target_unfrozen)
        score -= n_on_target * 150000
        corner_filled = len(frozen & self._corner_targets) + len(on_target_unfrozen & self._corner_targets)
        score -= corner_filled * 100000
        active_boxes = list(boxes - self.targets)
        active_targets = list(self.targets - boxes)
        n = len(active_boxes)
        if n == 0:
            self._h_cache[new_boxes_fs] = score
            return score
        cost = [[self._bfs_distance(b, t) for t in active_targets] for b in active_boxes]
        match_cost = _hungarian_solve(cost)
        score += match_cost * 10000
        unfilled_corners = self._corner_targets - boxes
        if unfilled_corners:
            for uc in unfilled_corners:
                nearest = min(self._bfs_distance(b, uc) for b in active_boxes)
                score += nearest * 2000
        for b in active_boxes:
            br, bc = b
            adj_box = sum(1 for dr, dc in DIRECTIONS
                          if (br + dr, bc + dc) in boxes
                          and (br + dr, bc + dc) not in self.targets)
            if adj_box >= 2:
                score += 25000
            wall_adj = sum(1 for dr, dc in DIRECTIONS if (br + dr, bc + dc) in self.walls)
            if wall_adj >= 2:
                score += 18000
            can_h = ((br, bc - 1) not in self.walls and (br, bc - 1) not in boxes) or \
                    ((br, bc + 1) not in self.walls and (br, bc + 1) not in boxes)
            can_v = ((br - 1, bc) not in self.walls and (br - 1, bc) not in boxes) or \
                    ((br + 1, bc) not in self.walls and (br + 1, bc) not in boxes)
            if not can_h and not can_v and b not in self.targets:
                score += 500000
        self._h_cache[new_boxes_fs] = score
        return score

    # ── Bounded best-first search (core solver) ──

    def _bounded_best_first(self, max_nodes=2000):
        boxes_fs = frozenset(self.boxes)
        initial_h = self._push_heuristic(boxes_fs)
        counter = 0
        open_set = [(initial_h, counter, self.player, boxes_fs, [])]
        closed = {boxes_fs}
        best_h = initial_h
        best_result = None
        nodes_expanded = 0

        while open_set and nodes_expanded < max_nodes:
            score, _, cur_player, cur_boxes_fs, cur_path = heapq.heappop(open_set)
            if score > best_h + 200000:
                continue
            cur_boxes_set = set(cur_boxes_fs)
            frozen, walls_ext = self._frozen_on_target(cur_boxes_fs)
            active = cur_boxes_set - frozen
            reachable = _reachable_cells(cur_player, walls_ext, active)
            nodes_expanded += 1

            for box in list(active):
                br, bc = box
                for dr, dc in DIRECTIONS:
                    pf = (br - dr, bc - dc)
                    pt = (br + dr, bc + dc)
                    if pf not in reachable:
                        continue
                    if pt in walls_ext or pt in active:
                        continue
                    if pt in self.static_deadlocks:
                        continue
                    nb = set(cur_boxes_set)
                    nb.remove(box)
                    nb.add(pt)
                    if _is_2x2_freeze(pt[0], pt[1], nb, self.walls, self.targets):
                        continue
                    nbfs = frozenset(nb)
                    if nbfs in closed or nbfs in self._visited_global:
                        continue
                    closed.add(nbfs)
                    if _is_freeze_cluster(nb, self.walls, self.targets):
                        continue
                    h = self._push_heuristic(nbfs)
                    if all(b in self.targets for b in nbfs):
                        walk = _find_player_path(cur_player, pf, walls_ext, active)
                        if walk is None:
                            continue
                        return cur_path + walk + [(dr, dc)], nbfs, -999999999
                    walk = _find_player_path(cur_player, pf, walls_ext, active)
                    if walk is None:
                        continue
                    new_path = cur_path + walk + [(dr, dc)]
                    if h < best_h:
                        best_h = h
                        best_result = (new_path, nbfs, h)
                    counter += 1
                    depth_cost = len(new_path) * 200
                    heapq.heappush(open_set, (h + depth_cost, counter, box, nbfs, new_path))

        if best_result:
            self._visited_global.add(best_result[1])
            if len(self._visited_global) > 200000:
                self._visited_global.clear()
        return best_result

    # ── Greedy fallback for single push ──

    def _greedy_push(self):
        boxes_set = set(self.boxes)
        boxes_fs = frozenset(self.boxes)
        frozen, walls_ext = self._frozen_on_target(boxes_fs)
        active_boxes = boxes_set - frozen
        reachable = _reachable_cells(self.player, walls_ext, active_boxes)
        candidates = []
        for box in list(active_boxes):
            for dr, dc in DIRECTIONS:
                pf = (box[0] - dr, box[1] - dc)
                pt = (box[0] + dr, box[1] + dc)
                if pf not in reachable:
                    continue
                if pt in walls_ext or pt in active_boxes or pt in self.static_deadlocks:
                    continue
                nb = set(boxes_set)
                nb.remove(box)
                nb.add(pt)
                if _is_2x2_freeze(pt[0], pt[1], nb, self.walls, self.targets):
                    continue
                nbfs = frozenset(nb)
                if nbfs in self._visited_global:
                    continue
                h = self._push_heuristic(nbfs)
                target_bonus = 0
                if pt in self.targets:
                    target_bonus = 300000 + self._target_ranks.get(pt, 0) * 60000
                # Add a small random jitter to break ties and vary paths
                s = h - target_bonus + random.randint(-1000, 1000)
                candidates.append((s, box, pf, (dr, dc), nbfs, h))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        idx = 0
        # Increased randomness based on restarts to ensure different paths
        chance = 0.15 + min(0.4, self.restart_count * 0.01)
        if random.random() < chance:
            max_idx = min(len(candidates) - 1, 1 + self.restart_count // 10)
            idx = random.randint(0, max_idx)
        
        _, box, pf, d, nbfs, h = candidates[idx]
        walk = _find_player_path(self.player, pf, walls_ext, active_boxes)
        if walk is None:
            for i in range(len(candidates)):
                if i == idx:
                    continue
                _, box2, pf2, d2, nbfs2, h2 = candidates[i]
                walk2 = _find_player_path(self.player, pf2, walls_ext, active_boxes)
                if walk2 is not None:
                    return (candidates[i][0], walk2 + [d2], nbfs2, h2)
            return None
        return (candidates[idx][0], walk + [d], nbfs, h)

    # ── Plan validation ──

    def _validate_plan(self):
        if not self._planned_path or self._plan_goal is None:
            return False
        sim_player = self.player
        boxes_set = set(self.boxes)
        for step_dr, step_dc in self._planned_path:
            nr, nc = sim_player[0] + step_dr, sim_player[1] + step_dc
            if (nr, nc) in self.walls:
                return False
            if (nr, nc) in boxes_set:
                nnr, nnc = nr + step_dr, nc + step_dc
                if (nnr, nnc) in self.walls or (nnr, nnc) in boxes_set:
                    return False
                boxes_set.remove((nr, nc))
                boxes_set.add((nnr, nnc))
            sim_player = (nr, nc)
        return True

    # ── Execution ──

    def _execute_step(self, dr, dc):
        nr, nc = self.player[0] + dr, self.player[1] + dc
        pushed = False
        if (nr, nc) in self.boxes:
            nnr, nnc = nr + dr, nc + dc
            self.boxes.remove((nr, nc))
            self.boxes.add((nnr, nnc))
            pushed = True
        self.player = (nr, nc)
        self.steps += 1
        self._last_dir = (dr, dc)
        self._last_pushed = pushed
        if pushed:
            self._player_recent.clear()
            self._boxes_at_recent = frozenset(self.boxes)
            self._stale_count = 0
        else:
            cur_fs = frozenset(self.boxes)
            if self._boxes_at_recent == cur_fs:
                self._player_recent.append(self.player)
                if len(self._player_recent) >= 12:
                    if len(set(self._player_recent)) <= 4:
                        self._stale_count += 1
            else:
                self._player_recent.clear()
                self._boxes_at_recent = cur_fs
                self._stale_count = 0

    def _do_restart(self):
        self.restart_count += 1
        self.no_improve = 0
        # self._h_cache.clear() 
        # self._frozen_cache.clear()
        # self._visited_global.clear() 
        # Persist memory to avoid previous traps
        # Early failure: no global improvement across many restarts
        if self._best_global_h < self._h_at_last_restart:
            self._restarts_without_global_improve = 0
            self._h_at_last_restart = self._best_global_h
        else:
            self._restarts_without_global_improve += 1
        if self._restarts_without_global_improve >= self._max_stale_restarts:
            self.failed = True
            return
        if self.restart_count >= self.max_restarts:
            self.failed = True
            return
        if self._best_state and self.restart_count % 3 == 0:
            self._restore_best_state()
        else:
            self._reload_level()

    def ai_step(self):
        if self.failed or all(b in self.targets for b in self.boxes):
            self.ai_mode = False
            return None
       
        if self._planned_path and self._validate_plan():
            dr, dc = self._planned_path.pop(0)
            self._execute_step(dr, dc)
            return (dr, dc)
        self._planned_path = []
        self._plan_goal = None
        node_budget = 1500
        if self.no_improve > 60:
            node_budget = 2500
        result = self._bounded_best_first(max_nodes=node_budget)
        if result:
            path, nbfs, h = result
            self._plan_goal = ("bbf", (0, 0))
            self._planned_path = list(path)
            if h < self.best_h:
                self.best_h = h
                self.no_improve = 0
                if h < self._best_global_h:
                    self._best_global_h = h
                    self._best_state = (self.player, frozenset(self.boxes))
            else:
                self.no_improve += 1
            if self.no_improve >= 100:
                self._do_restart()
                return (0, 0)
            if self._planned_path:
                dr, dc = self._planned_path.pop(0)
                self._execute_step(dr, dc)
                return (dr, dc)
        fb = self._greedy_push()
        if fb:
            _, path, nbfs, h = fb
            self._plan_goal = ("greedy", (0, 0))
            self._planned_path = list(path)
            self._visited_global.add(nbfs)
            if h < self.best_h:
                self.best_h = h
                self.no_improve = 0
                if h < self._best_global_h:
                    self._best_global_h = h
                    self._best_state = (self.player, frozenset(self.boxes))
            else:
                self.no_improve += 1
            if self.no_improve >= 100:
                self._do_restart()
                return (0, 0)
            if self._planned_path:
                dr, dc = self._planned_path.pop(0)
                self._execute_step(dr, dc)
                return (dr, dc)
        self._do_restart()
        return (0, 0)




# ─────────────────────────────────────────────
# Shared helpers (push-only search)
# ─────────────────────────────────────────────



def _reachable_cells(player, walls, boxes_set):
    """BFS: return set of all cells reachable by the player."""
    visited = set()
    queue = collections.deque([player])
    visited.add(player)
    while queue:
        r, c = queue.popleft()
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if (nr, nc) not in walls and (nr, nc) not in boxes_set and (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append((nr, nc))
    return visited


def _find_player_path(start, target, walls, boxes_set):
    """BFS shortest path from start to target, avoiding walls and boxes.
    Returns list of (dr, dc) directions, or None if unreachable."""
    if start == target:
        return []
    visited = {start}
    queue = collections.deque([(start, [])])
    while queue:
        (r, c), path = queue.popleft()
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            npos = (nr, nc)
            if npos in walls or npos in boxes_set or npos in visited:
                continue
            new_path = path + [(dr, dc)]
            if npos == target:
                return new_path
            visited.add(npos)
            queue.append((npos, new_path))
    return None


def _push_only_successors(player, boxes_fs, walls, static_deadlocks, targets):
    """Generate all valid push moves from the player's reachable area.
    Yields (new_player, new_boxes_fs, walk_dirs + push_dir) tuples."""
    boxes_set = set(boxes_fs)
    reachable = _reachable_cells(player, walls, boxes_set)

    for box in list(boxes_set):
        for dr, dc in DIRECTIONS:
            push_from = (box[0] - dr, box[1] - dc)
            push_to = (box[0] + dr, box[1] + dc)

            if push_from not in reachable:
                continue
            if push_to in walls or push_to in boxes_set:
                continue
            if push_to in static_deadlocks:
                continue

            new_boxes = set(boxes_set)
            new_boxes.remove(box)
            new_boxes.add(push_to)
            if _is_2x2_freeze(push_to[0], push_to[1], new_boxes, walls, targets):
                continue
            new_boxes_fs = frozenset(new_boxes)

            walk_path = _find_player_path(player, push_from, walls, boxes_set)
            if walk_path is None:
                continue
            full_dirs = walk_path + [(dr, dc)]
            new_player = box
            yield new_player, new_boxes_fs, full_dirs







# ─────────────────────────────────────────────
# 4) HILL CLIMB (Stochastic + Random Restarts, real-time)
# ─────────────────────────────────────────────

class HillClimbAI:
    """Stochastic Hill Climbing with Random Restarts + Sideways Moves.

    Real-time solver — character moves each frame while searching.

    Algorithm:
    - Heuristic = Hungarian matching (box→target) + player distance to nearest box
    - Each step: evaluate all valid pushes, pick the best (with stochastic noise)
    - Sideways moves: accept equal-heuristic states to escape plateaus
    - Random restarts: when stuck, reload level or restore best-known state
    - Deadlock detection: corner deadlocks, 2×2 freeze, frozen clusters
    """
    LABEL = "Hill Climb"
    DESC = "Leo đồi ngẫu nhiên + khởi động lại. Real-time, trực quan."

    def __init__(self) -> None:
        self.max_restarts = 100
        self._max_stale_restarts = 10
        self.ai_mode = False
        self.failed = False
        self.reset_internal()

    def reset_internal(self) -> None:
        self.walls, self.targets, self.boxes = set(), set(), set()
        self.static_deadlocks = set()
        self.steps = self.no_improve = self.restart_count = 0
        self.best_h = float("inf")
        self.failed = False
        # Do not reset self.ai_mode here as it kills the AI loop on restart
        self.player = (0, 0)
        self.R = self.C = 0
        self.current_idx = 0
        self._level_data = None
        self._solution = None
        self._sol_idx = 0
        self._planned_path = []
        self._plan_goal = None
        self._visited_states = set()
        self._h_cache = {}
        self._bfs_dist_cache = {}
        self._frozen_cache = {}
        self._best_state = None
        self._best_global_h = float("inf")
        self._sideways_count = 0
        self._max_sideways = 200
        self._fresh_start = True
        self._target_ranks = {}
        self._corner_targets = set()
        self._restarts_without_global_improve = 0
        self._h_at_last_restart = float("inf")

    # ── Loading ──

    def load_from_state(self, state: GameState) -> None:
        self.reset_internal()
        self.R, self.C = len(state.rows), len(state.rows[0])
        self.walls = set(state.walls)
        self.targets = set(state.targets)
        self.boxes = set(state.boxes)
        self.player = state.player
        self._rows = state.rows
        self.static_deadlocks = _precompute_deadlocks(self.walls, self.targets, self.R, self.C)
        self._precompute_bfs_distances()
        self._classify_targets()

    def load_from_level_data(self, level_data: list[dict], idx: int) -> None:
        self._level_data = level_data
        self.current_idx = idx
        m = level_data[idx]["map"]
        self.reset_internal()
        self._level_data = level_data
        self.current_idx = idx
        self.R, self.C = len(m), len(m[0])
        self._rows = m
        self.walls, self.targets, self.boxes, self.player, _, _ = _parse_level_map(m)
        self.static_deadlocks = _precompute_deadlocks(self.walls, self.targets, self.R, self.C)
        self._precompute_bfs_distances()
        self._classify_targets()

    # ── Target classification ──

    def _classify_targets(self):
        self._corner_targets = set()
        self._target_ranks = {}
        for t in self.targets:
            r, c = t
            wadj = sum(1 for dr, dc in DIRECTIONS if (r + dr, c + dc) in self.walls)
            self._target_ranks[t] = wadj
            if wadj >= 2:
                self._corner_targets.add(t)

    # ── BFS distance precomputation ──

    def _precompute_bfs_distances(self):
        self._bfs_dist_cache = {}
        for target in self.targets:
            dist = {}
            queue = collections.deque([target])
            dist[target] = 0
            while queue:
                r, c = queue.popleft()
                d = dist[(r, c)]
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if (nr, nc) not in self.walls and (nr, nc) not in dist:
                        dist[(nr, nc)] = d + 1
                        queue.append((nr, nc))
            self._bfs_dist_cache[target] = dist

    def _bfs_distance(self, cell, target):
        td = self._bfs_dist_cache.get(target)
        if td is None:
            return abs(cell[0] - target[0]) + abs(cell[1] - target[1])
        return td.get(cell, 9999)

    # ── Frozen box detection (cached) ──
    def _frozen_on_target(self, boxes_fs):
        if boxes_fs in self._frozen_cache:
            return self._frozen_cache[boxes_fs]
        boxes_set = set(boxes_fs) if isinstance(boxes_fs, frozenset) else boxes_fs
        frozen = set()
        walls_ext = set(self.walls)
        changed = True
        while changed:
            changed = False
            for b in boxes_set:
                if b in frozen or b not in self.targets:
                    continue
                r, c = b
                h_stuck = (r, c - 1) in walls_ext and (r, c + 1) in walls_ext
                v_stuck = (r - 1, c) in walls_ext and (r + 1, c) in walls_ext
                if h_stuck or v_stuck:
                    frozen.add(b)
                    walls_ext.add(b)
                    changed = True
        key = boxes_fs if isinstance(boxes_fs, frozenset) else frozenset(boxes_fs)
        if len(self._frozen_cache) < 300000:
            self._frozen_cache[key] = (frozen, walls_ext)
        return frozen, walls_ext

    # ── Hill Climbing heuristic ──
    # Hungarian matching + player distance + corner priority + penalties

    def _hc_heuristic(self, boxes_fs, player=None):
        if boxes_fs in self._h_cache:
            cached = self._h_cache[boxes_fs]
            if player is None:
                return cached
            # Add player distance component
            boxes = set(boxes_fs)
            active = boxes - self.targets
            if active:
                pdist = min(self._bfs_distance(player, b) for b in active)
            else:
                pdist = 0
            return cached + pdist * 500
        boxes = set(boxes_fs)
        score = 0

        # Reward frozen-on-target boxes
        frozen, _ = self._frozen_on_target(boxes_fs)
        score -= len(frozen) * 300000

        # Reward unfrozen-on-target boxes
        on_target_unfrozen = (boxes & self.targets) - frozen
        score -= len(on_target_unfrozen) * 150000

        # Reward filled corner targets
        corner_filled = len(frozen & self._corner_targets) + len(on_target_unfrozen & self._corner_targets)
        score -= corner_filled * 100000

        # Hungarian matching for active boxes → active targets
        active_boxes = list(boxes - self.targets)
        active_targets = list(self.targets - boxes)
        n = len(active_boxes)
        if n > 0:
            cost = [[self._bfs_distance(b, t) for t in active_targets] for b in active_boxes]
            match_cost = _hungarian_solve(cost)
            score += match_cost * 10000

            # Penalty for unfilled corner targets
            unfilled_corners = self._corner_targets - boxes
            for uc in unfilled_corners:
                nearest = min(self._bfs_distance(b, uc) for b in active_boxes)
                score += nearest * 2000

            # Penalty for box clusters and wall-stuck boxes
            for b in active_boxes:
                br, bc = b
                adj_box = sum(1 for dr, dc in DIRECTIONS
                              if (br + dr, bc + dc) in boxes
                              and (br + dr, bc + dc) not in self.targets)
                if adj_box >= 2:
                    score += 25000
                wall_adj = sum(1 for dr, dc in DIRECTIONS if (br + dr, bc + dc) in self.walls)
                if wall_adj >= 2:
                    score += 18000
                # Frozen non-target box = huge penalty
                can_h = ((br, bc - 1) not in self.walls and (br, bc - 1) not in boxes) or \
                        ((br, bc + 1) not in self.walls and (br, bc + 1) not in boxes)
                can_v = ((br - 1, bc) not in self.walls and (br - 1, bc) not in boxes) or \
                        ((br + 1, bc) not in self.walls and (br + 1, bc) not in boxes)
                if not can_h and not can_v:
                    score += 500000

        self._h_cache[boxes_fs] = score

        # Add player distance if provided
        if player is not None and n > 0:
            pdist = min(self._bfs_distance(player, b) for b in active_boxes)
            return score + pdist * 500

        return score

    # ── Steepest-ascent hill climbing step ──

    def _hill_climb_push(self):
        """Evaluate all pushes, pick the best (with stochastic noise)."""
        boxes_set = set(self.boxes)
        boxes_fs = frozenset(self.boxes)
        frozen, walls_ext = self._frozen_on_target(boxes_fs)
        active_boxes = boxes_set - frozen
        reachable = _reachable_cells(self.player, walls_ext, active_boxes)
        current_h = self._hc_heuristic(boxes_fs, self.player)

        candidates = []
        for box in list(active_boxes):
            for dr, dc in DIRECTIONS:
                pf = (box[0] - dr, box[1] - dc)
                pt = (box[0] + dr, box[1] + dc)
                if pf not in reachable:
                    continue
                if pt in walls_ext or pt in active_boxes or pt in self.static_deadlocks:
                    continue
                nb = set(boxes_set)
                nb.remove(box)
                nb.add(pt)
                if _is_2x2_freeze(pt[0], pt[1], nb, self.walls, self.targets):
                    continue
                nbfs = frozenset(nb)
                if nbfs in self._visited_states:
                    continue
                if _is_freeze_cluster(nb, self.walls, self.targets):
                    continue
                h = self._hc_heuristic(nbfs, box)
                # Bonus for pushing onto target
                target_bonus = 0
                if pt in self.targets:
                    target_bonus = 300000 + self._target_ranks.get(pt, 0) * 60000
                s = h - target_bonus
                candidates.append((s, box, pf, (dr, dc), nbfs, h))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])

        # Stochastic hill climbing: mostly pick the best, sometimes explore
        idx = 0
        # Increased randomness based on restarts to ensure different paths
        chance = 0.15 + min(0.4, self.restart_count * 0.01)
        if random.random() < chance:
            max_idx = min(len(candidates) - 1, 1 + self.restart_count // 5)
            idx = random.randint(0, max_idx)
        elif self._sideways_count > 50:
            idx = random.randint(0, min(3, len(candidates) - 1))
        elif self.no_improve > 60:
            idx = random.randint(0, min(2, len(candidates) - 1))

        chosen_s, box, pf, d, nbfs, h = candidates[idx]

        # Track uphill/sideways moves
        if chosen_s > current_h:
            self._sideways_count += 1
        elif chosen_s == current_h:
            self._sideways_count += 1
        else:
            self._sideways_count = 0

        walk = _find_player_path(self.player, pf, walls_ext, active_boxes)
        if walk is None:
            for i in range(len(candidates)):
                if i == idx:
                    continue
                _, b2, pf2, d2, nbfs2, h2 = candidates[i]
                walk2 = _find_player_path(self.player, pf2, walls_ext, active_boxes)
                if walk2 is not None:
                    return (candidates[i][0], walk2 + [d2], nbfs2, h2)
            return None
        return (chosen_s, walk + [d], nbfs, h)

    # ── Plan validation ──

    def _validate_plan(self):
        if not self._planned_path or self._plan_goal is None:
            return False
        sim_player = self.player
        boxes_set = set(self.boxes)
        for step_dr, step_dc in self._planned_path:
            nr, nc = sim_player[0] + step_dr, sim_player[1] + step_dc
            if (nr, nc) in self.walls:
                return False
            if (nr, nc) in boxes_set:
                nnr, nnc = nr + step_dr, nc + step_dc
                if (nnr, nnc) in self.walls or (nnr, nnc) in boxes_set:
                    return False
                boxes_set.remove((nr, nc))
                boxes_set.add((nnr, nnc))
            sim_player = (nr, nc)
        return True

    # ── Execution ──

    def _execute_step(self, dr, dc):
        nr, nc = self.player[0] + dr, self.player[1] + dc
        pushed = False
        if (nr, nc) in self.boxes:
            nnr, nnc = nr + dr, nc + dc
            self.boxes.remove((nr, nc))
            self.boxes.add((nnr, nnc))
            pushed = True
        self.player = (nr, nc)
        self.steps += 1

    # ── Reload / Restart ──

    def _reload_level(self) -> None:
        if self._level_data is not None:
            saved_visited = self._visited_states
            saved_bfs = self._bfs_dist_cache
            saved_best = self._best_state
            saved_best_h = self._best_global_h
            saved_restarts = self.restart_count
            saved_stale = self._restarts_without_global_improve
            saved_h_last = self._h_at_last_restart
            self.load_from_level_data(self._level_data, self.current_idx)
            self._visited_states = saved_visited
            self._bfs_dist_cache = saved_bfs
            self._best_state = saved_best
            self._best_global_h = saved_best_h
            self.restart_count = saved_restarts
            self._restarts_without_global_improve = saved_stale
            self._h_at_last_restart = saved_h_last

    def _restore_best_state(self):
        if self._best_state and self._level_data:
            self._reload_level()
            player, boxes_fs = self._best_state
            self.player = player
            self.boxes = set(boxes_fs)

    def _do_restart(self):
        self.restart_count += 1
        self.no_improve = 0
        self._sideways_count = 0
        self._fresh_start = True
        # self._h_cache.clear()
        # self._frozen_cache.clear()
        # self._visited_states.clear()
        # Persist memory to avoid previous traps
        # Early failure: no global improvement across many restarts
        if self._best_global_h < self._h_at_last_restart:
            self._restarts_without_global_improve = 0
            self._h_at_last_restart = self._best_global_h
        else:
            self._restarts_without_global_improve += 1
        if self._restarts_without_global_improve >= self._max_stale_restarts:
            self.failed = True
            return
        if self.restart_count >= self.max_restarts:
            self.failed = True
            return
        if self._best_state and self.restart_count % 2 == 0:
            self._restore_best_state()
        else:
            self._reload_level()

    # ── Main AI step (real-time, one move per call) ──
    # ── Bounded best-first search (look-ahead for escaping local optima) ──

    def _bounded_best_first(self, max_nodes=1500):
        """Mini-A* search expanding up to max_nodes, seeking an improving state."""
        boxes_fs = frozenset(self.boxes)
        initial_h = self._hc_heuristic(boxes_fs)
        counter = 0
        open_set = [(initial_h, counter, self.player, boxes_fs, [])]
        closed = {boxes_fs}
        best_h = initial_h
        best_result = None
        nodes_expanded = 0

        while open_set and nodes_expanded < max_nodes:
            score, _, cur_player, cur_boxes_fs, cur_path = heapq.heappop(open_set)
            if score > best_h + 200000:
                continue
            cur_boxes_set = set(cur_boxes_fs)
            frozen, walls_ext = self._frozen_on_target(cur_boxes_fs)
            active = cur_boxes_set - frozen
            reachable = _reachable_cells(cur_player, walls_ext, active)
            nodes_expanded += 1

            for box in list(active):
                br, bc = box
                for dr, dc in DIRECTIONS:
                    pf = (br - dr, bc - dc)
                    pt = (br + dr, bc + dc)
                    if pf not in reachable:
                        continue
                    if pt in walls_ext or pt in active:
                        continue
                    if pt in self.static_deadlocks:
                        continue
                    nb = set(cur_boxes_set)
                    nb.remove(box)
                    nb.add(pt)
                    if _is_2x2_freeze(pt[0], pt[1], nb, self.walls, self.targets):
                        continue
                    nbfs = frozenset(nb)
                    if nbfs in closed or nbfs in self._visited_states:
                        continue
                    closed.add(nbfs)
                    if _is_freeze_cluster(nb, self.walls, self.targets):
                        continue
                    h = self._hc_heuristic(nbfs)
                    if all(b in self.targets for b in nbfs):
                        walk = _find_player_path(cur_player, pf, walls_ext, active)
                        if walk is None:
                            continue
                        return cur_path + walk + [(dr, dc)], nbfs, -999999999
                    walk = _find_player_path(cur_player, pf, walls_ext, active)
                    if walk is None:
                        continue
                    new_path = cur_path + walk + [(dr, dc)]
                    if h < best_h:
                        best_h = h
                        best_result = (new_path, nbfs, h)
                    counter += 1
                    depth_cost = len(new_path) * 200
                    heapq.heappush(open_set, (h + depth_cost, counter, box, nbfs, new_path))

        if best_result:
            self._visited_states.add(best_result[1])
            if len(self._visited_states) > 200000:
                self._visited_states.clear()
        return best_result

    # ── Main AI step  --

    def ai_step(self):
        if self.failed or all(b in self.targets for b in self.boxes):
            self.ai_mode = False
            return None
       

        # Execute planned path if valid
        if self._planned_path and self._validate_plan():
            dr, dc = self._planned_path.pop(0)
            self._execute_step(dr, dc)
            return (dr, dc)

        # Plan exhausted — replan
        self._planned_path = []
        self._plan_goal = None

        # On fresh start or after restart: try bounded best-first (reliable)
        if self._fresh_start:
            self._fresh_start = False
            result = self._bounded_best_first(max_nodes=3000)
            if result:
                path, nbfs, h = result
                self._plan_goal = ("bbf", (0, 0))
                self._planned_path = list(path)
                if h < self.best_h:
                    self.best_h = h
                    self.no_improve = 0
                    if h < self._best_global_h:
                        self._best_global_h = h
                        self._best_state = (self.player, frozenset(self.boxes))
                if self._planned_path:
                    dr, dc = self._planned_path.pop(0)
                    self._execute_step(dr, dc)
                    return (dr, dc)

        # Primary: greedy hill climbing push (fast, exploratory)
        fb = self._hill_climb_push()
        if fb:
            _, path, nbfs, h = fb
            self._plan_goal = ("hc", (0, 0))
            self._planned_path = list(path)
            self._visited_states.add(nbfs)
            if len(self._visited_states) > 200000:
                self._visited_states.clear()

            if h < self.best_h:
                self.best_h = h
                self.no_improve = 0
                if h < self._best_global_h:
                    self._best_global_h = h
                    self._best_state = (self.player, frozenset(self.boxes))
            else:
                self.no_improve += 1

            if self.no_improve >= 60:
                self._do_restart()
                return (0, 0)

            if self._planned_path:
                dr, dc = self._planned_path.pop(0)
                self._execute_step(dr, dc)
                return (dr, dc)

        # Fallback: bounded best-first with larger budget
        node_budget = 2500
        if self.no_improve > 40:
            node_budget = 4000
        result = self._bounded_best_first(max_nodes=node_budget)
        if result:
            path, nbfs, h = result
            self._plan_goal = ("bbf", (0, 0))
            self._planned_path = list(path)
            if h < self.best_h:
                self.best_h = h
                self.no_improve = 0
                if h < self._best_global_h:
                    self._best_global_h = h
                    self._best_state = (self.player, frozenset(self.boxes))
            else:
                self.no_improve += 1
            if self.no_improve >= 60:
                self._do_restart()
                return (0, 0)
            if self._planned_path:
                dr, dc = self._planned_path.pop(0)
                self._execute_step(dr, dc)
                return (dr, dc)

        # No valid push found — restart
        self._do_restart()
        return (0, 0)


AI_SOLVERS = [StrategicProAI, HillClimbAI]
