"""SGFGame을 GoBoard 규칙 엔진 위에서 재생(replay)하는 유틸."""

from .board import GoBoard, BLACK, WHITE, EMPTY


def _color_const(sgf_color):
    return BLACK if sgf_color == "B" else WHITE


def build_board_with_numbers(sgf_game, upto_index):
    """sgf_game.moves[0:upto_index]까지 재생한 GoBoard와 수순 번호 dict를 반환.

    move_numbers는 {(x, y): 수번호} 형태이며, 따내진 돌의 번호는 제거된다.
    """
    board = GoBoard(size=sgf_game.size, komi=sgf_game.komi)

    for (x, y) in sgf_game.ab:
        board.setup_stone(x, y, BLACK)
    for (x, y) in sgf_game.aw:
        board.setup_stone(x, y, WHITE)

    board.current = WHITE if sgf_game.handicap and sgf_game.handicap > 0 else BLACK

    move_numbers = {}
    for i in range(min(upto_index, len(sgf_game.moves))):
        m = sgf_game.moves[i]
        color = _color_const(m.color)
        board.current = color
        if m.x is None:
            board.pass_turn()
            continue
        ok, _ = board.play(m.x, m.y)
        if not ok:
            # 기보 상 이상 착수(중복 등)는 무시하고 넘어간다.
            continue
        for p in list(move_numbers.keys()):
            px_, py_ = p
            if board.grid[py_][px_] == EMPTY:
                del move_numbers[p]
        move_numbers[(m.x, m.y)] = i + 1

    return board, move_numbers
