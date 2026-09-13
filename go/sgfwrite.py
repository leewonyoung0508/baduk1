"""SGF 직렬화(쓰기) 유틸. quizgen에서 생성한 문제 기보를 저장할 때 사용."""


def _coord(x, y):
    return chr(ord("a") + x) + chr(ord("a") + y)


def _escape(text):
    return text.replace("\\", "\\\\").replace("]", "\\]")


def write_sgf(path, size, komi, handicap, player_black, player_white,
              result, root_comment, ab, aw, moves, quiz_scene=False):
    """moves: [(color 'B'/'W', x, y 또는 None, comment 또는 None), ...]

    quiz_scene=True면 루트에 QZ[1] 속성을 붙인다: '이 기보의 마지막 수가 곧
    문제(정답)'라는 표시로, 프로 기보 훈련 화면이 불러오자마자 그 장면으로
    점프해서 퀴즈 모드를 켜는 데 쓰인다.
    """
    parts = ["(;GM[1]FF[4]CA[UTF-8]"]
    parts.append(f"SZ[{size}]")
    parts.append(f"KM[{komi}]")
    if handicap:
        parts.append(f"HA[{handicap}]")
    if quiz_scene:
        parts.append("QZ[1]")
    if player_black:
        parts.append(f"PB[{_escape(player_black)}]")
    if player_white:
        parts.append(f"PW[{_escape(player_white)}]")
    if result:
        parts.append(f"RE[{_escape(result)}]")
    if root_comment:
        parts.append(f"C[{_escape(root_comment)}]")
    for x, y in ab:
        parts.append(f"AB[{_coord(x, y)}]")
    for x, y in aw:
        parts.append(f"AW[{_coord(x, y)}]")
    parts.append("\n")

    for color, x, y, comment in moves:
        coord = "" if x is None else _coord(x, y)
        parts.append(f";{color}[{coord}]")
        if comment:
            parts.append(f"C[{_escape(comment)}]")
        parts.append("\n")

    parts.append(")")

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
