"""바둑 규칙 엔진: 착수, 따내기, 자살수 금지, 패(ko) 규칙, 집계산."""

EMPTY, BLACK, WHITE = 0, 1, 2


def opponent(color):
    return WHITE if color == BLACK else BLACK


class IllegalMove(Exception):
    pass


class GoBoard:
    def __init__(self, size=19, komi=6.5):
        self.size = size
        self.komi = komi
        self.grid = [[EMPTY] * size for _ in range(size)]
        self.current = BLACK
        self.captures = {BLACK: 0, WHITE: 0}
        self.pass_count = 0
        self.ko_point = None
        self.game_over = False
        self.resigned_by = None
        self._undo_stack = []
        self.move_count = 0

    def in_bounds(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def neighbors(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny

    def _group_and_liberties(self, x, y):
        color = self.grid[y][x]
        stack = [(x, y)]
        visited = {(x, y)}
        liberties = set()
        while stack:
            cx, cy = stack.pop()
            for nx, ny in self.neighbors(cx, cy):
                v = self.grid[ny][nx]
                if v == EMPTY:
                    liberties.add((nx, ny))
                elif v == color and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    stack.append((nx, ny))
        return visited, liberties

    def group_stones(self, x, y):
        """돌이 놓인 (x,y)와 연결된 같은 색 돌 전체 좌표 집합."""
        if self.grid[y][x] == EMPTY:
            return set()
        group, _ = self._group_and_liberties(x, y)
        return group

    def _snapshot(self):
        return {
            "grid": [row[:] for row in self.grid],
            "current": self.current,
            "captures": dict(self.captures),
            "pass_count": self.pass_count,
            "ko_point": self.ko_point,
            "game_over": self.game_over,
            "resigned_by": self.resigned_by,
            "move_count": self.move_count,
        }

    def _restore(self, snap):
        self.grid = snap["grid"]
        self.current = snap["current"]
        self.captures = snap["captures"]
        self.pass_count = snap["pass_count"]
        self.ko_point = snap["ko_point"]
        self.game_over = snap["game_over"]
        self.resigned_by = snap["resigned_by"]
        self.move_count = snap["move_count"]

    def setup_stone(self, x, y, color):
        """대국 규칙(순서, 착수 검증)을 거치지 않고 돌을 직접 배치한다.

        핸디캡/기보의 초기 배석(AB/AW)을 놓을 때만 사용한다.
        """
        self.grid[y][x] = color

    def play(self, x, y):
        """(x, y)에 착수를 시도한다. 성공 시 (True, None), 실패 시 (False, 이유)."""
        if self.game_over:
            return False, "게임이 이미 종료되었습니다."
        if not self.in_bounds(x, y):
            return False, "판 밖입니다."
        if self.grid[y][x] != EMPTY:
            return False, "이미 돌이 놓여 있습니다."
        if (x, y) == self.ko_point:
            return False, "패(ko) 규칙: 지금은 이 자리에 둘 수 없습니다."

        before = self._snapshot()
        color = self.current
        opp = opponent(color)
        self.grid[y][x] = color

        captured = set()
        for nx, ny in self.neighbors(x, y):
            if self.grid[ny][nx] == opp:
                group, libs = self._group_and_liberties(nx, ny)
                if not libs:
                    captured |= group

        for cx, cy in captured:
            self.grid[cy][cx] = EMPTY

        own_group, own_libs = self._group_and_liberties(x, y)
        if not own_libs:
            self._restore(before)
            return False, "자살수는 둘 수 없습니다."

        self.captures[color] += len(captured)

        if len(captured) == 1 and len(own_group) == 1 and len(own_libs) == 1:
            self.ko_point = next(iter(captured))
        else:
            self.ko_point = None

        self.pass_count = 0
        self.current = opp
        self.move_count += 1
        self._undo_stack.append(before)
        return True, None

    def pass_turn(self):
        if self.game_over:
            return
        before = self._snapshot()
        self._undo_stack.append(before)
        self.pass_count += 1
        self.ko_point = None
        self.current = opponent(self.current)
        self.move_count += 1
        if self.pass_count >= 2:
            self.game_over = True

    def resign(self):
        if self.game_over:
            return
        before = self._snapshot()
        self._undo_stack.append(before)
        self.resigned_by = self.current
        self.game_over = True

    def resume_from_scoring(self):
        """계가 단계에서 실수로 넘어온 경우 대국을 재개한다."""
        self.game_over = False
        self.pass_count = 0

    def can_undo(self):
        return len(self._undo_stack) > 0

    def undo(self):
        if not self._undo_stack:
            return False
        snap = self._undo_stack.pop()
        self._restore(snap)
        return True

    def area_score(self, dead_stones=frozenset()):
        """중국식 면적 계산(집 + 살아있는 돌 수), dead_stones는 제거하고 계산."""
        size = self.size
        board = [row[:] for row in self.grid]
        for (dx, dy) in dead_stones:
            board[dy][dx] = EMPTY

        stones = {BLACK: 0, WHITE: 0}
        for row in board:
            for v in row:
                if v in (BLACK, WHITE):
                    stones[v] += 1

        territory = {BLACK: 0, WHITE: 0}
        visited = set()
        for y in range(size):
            for x in range(size):
                if board[y][x] != EMPTY or (x, y) in visited:
                    continue
                stack = [(x, y)]
                visited.add((x, y))
                region = [(x, y)]
                borders = set()
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in self.neighbors(cx, cy):
                        v = board[ny][nx]
                        if v == EMPTY:
                            if (nx, ny) not in visited:
                                visited.add((nx, ny))
                                stack.append((nx, ny))
                                region.append((nx, ny))
                        else:
                            borders.add(v)
                if borders == {BLACK}:
                    territory[BLACK] += len(region)
                elif borders == {WHITE}:
                    territory[WHITE] += len(region)

        black_area = stones[BLACK] + territory[BLACK]
        white_area = stones[WHITE] + territory[WHITE]
        return {
            "black_area": black_area,
            "white_area": white_area,
            "black_total": black_area,
            "white_total": white_area + self.komi,
        }
