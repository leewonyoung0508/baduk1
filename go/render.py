"""바둑판 렌더링 공통 유틸 (대국 화면과 기보 복기 화면에서 공유)."""

from .board import BLACK, WHITE, EMPTY

MARGIN = 34
CELL = 30
STONE_R = 13
COL_LETTERS = "ABCDEFGHJKLMNOPQRST"  # I는 관례상 제외

BOARD_BG = "#e3b063"
LINE_COLOR = "#3a2a14"
BLACK_STONE = "#111111"
WHITE_STONE = "#f5f5f5"


def board_pixel_size(size):
    return MARGIN * 2 + (size - 1) * CELL


def px(x):
    return MARGIN + x * CELL


def py(y):
    return MARGIN + y * CELL


def nearest_point(ex, ey, size):
    x = round((ex - MARGIN) / CELL)
    y = round((ey - MARGIN) / CELL)
    if 0 <= x < size and 0 <= y < size:
        return x, y
    return None


def _hoshi_points(size):
    if size == 19:
        pts = [3, 9, 15]
    elif size == 13:
        pts = [3, 6, 9]
    elif size == 9:
        pts = [2, 4, 6]
    else:
        pts = []
    return pts


def draw_board(canvas, size, grid, dead_stones=None, ko_point=None,
                move_numbers=None, guess_marker=None):
    """바둑판, 돌, 좌표, 표시(사석/패/수순/추측)을 캔버스에 그린다.

    dead_stones: {(x,y), ...} 계가 단계에서 죽은 돌로 표시할 좌표
    ko_point: (x,y) 또는 None, 패로 인해 착수 금지된 자리
    move_numbers: {(x,y): int} 돌 위에 표시할 수순 번호
    guess_marker: (x, y, 'correct'|'wrong') 퀴즈 정답/오답 클릭 지점 표시
    """
    dead_stones = dead_stones or set()
    move_numbers = move_numbers or {}

    canvas.delete("all")

    for i in range(size):
        canvas.create_line(px(0), py(i), px(size - 1), py(i), fill=LINE_COLOR)
        canvas.create_line(px(i), py(0), px(i), py(size - 1), fill=LINE_COLOR)

    for hx in _hoshi_points(size):
        for hy in _hoshi_points(size):
            canvas.create_oval(
                px(hx) - 3, py(hy) - 3, px(hx) + 3, py(hy) + 3,
                fill=LINE_COLOR, outline=""
            )

    for x in range(size):
        canvas.create_text(px(x), MARGIN - 18, text=COL_LETTERS[x], font=("Consolas", 9))
    for y in range(size):
        canvas.create_text(MARGIN - 20, py(y), text=str(size - y), font=("Consolas", 9))

    for y in range(size):
        for x in range(size):
            v = grid[y][x]
            if v == EMPTY:
                continue
            color = BLACK_STONE if v == BLACK else WHITE_STONE
            canvas.create_oval(
                px(x) - STONE_R, py(y) - STONE_R,
                px(x) + STONE_R, py(y) + STONE_R,
                fill=color, outline="#000000"
            )
            if (x, y) in dead_stones:
                canvas.create_line(px(x) - STONE_R, py(y) - STONE_R,
                                    px(x) + STONE_R, py(y) + STONE_R, fill="red", width=2)
                canvas.create_line(px(x) - STONE_R, py(y) + STONE_R,
                                    px(x) + STONE_R, py(y) - STONE_R, fill="red", width=2)
            if (x, y) in move_numbers:
                text_color = WHITE_STONE if v == BLACK else BLACK_STONE
                canvas.create_text(px(x), py(y), text=str(move_numbers[(x, y)]),
                                    fill=text_color, font=("Consolas", 8, "bold"))

    if ko_point is not None:
        kx, ky = ko_point
        canvas.create_oval(px(kx) - 4, py(ky) - 4, px(kx) + 4, py(ky) + 4,
                            outline="red", width=2)

    if guess_marker is not None:
        gx, gy, kind = guess_marker
        color = "#2e7d32" if kind == "correct" else "#c62828"
        canvas.create_rectangle(px(gx) - STONE_R - 3, py(gy) - STONE_R - 3,
                                 px(gx) + STONE_R + 3, py(gy) + STONE_R + 3,
                                 outline=color, width=3)
