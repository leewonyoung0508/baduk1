"""아주 단순한 SGF(Smart Game Format) 파서. 기보 훈련 모드에서 사용."""


class SGFParseError(Exception):
    pass


class Move:
    def __init__(self, color, x, y, comment=None):
        self.color = color          # 'B' 또는 'W'
        self.x = x                  # None이면 착수 포기(pass)
        self.y = y
        self.comment = comment


class SGFGame:
    def __init__(self, size, komi, handicap, player_black, player_white,
                 result, root_comment, ab, aw, moves, quiz_scene=False):
        self.size = size
        self.komi = komi
        self.handicap = handicap
        self.player_black = player_black
        self.player_white = player_white
        self.result = result
        self.root_comment = root_comment
        self.ab = ab   # 흑 배석(핸디캡/세팅) 좌표 리스트
        self.aw = aw   # 백 배석 좌표 리스트
        self.moves = moves  # Move 객체 리스트 (본선/main line만)
        # True면 '이 기보의 마지막 수가 곧 문제(정답)'라는 표시
        # (generate_random_quiz.py가 만든 AI 문제 SGF에만 붙는다)
        self.quiz_scene = quiz_scene


def _coord(value, size):
    """SGF 좌표 문자열('pd' 등)을 (x, y) 정수로 변환. 빈 값/'tt'는 패스(None, None)."""
    if value == "" or value.lower() == "tt":
        return None, None
    if len(value) < 2:
        raise SGFParseError(f"잘못된 좌표: {value!r}")
    x = ord(value[0]) - ord("a")
    y = ord(value[1]) - ord("a")
    if not (0 <= x < size and 0 <= y < size):
        return None, None
    return x, y


def _parse_tree(text, pos):
    if pos >= len(text) or text[pos] != "(":
        raise SGFParseError("'(' 로 시작해야 합니다.")
    pos += 1
    sequence = []
    while pos < len(text) and text[pos] == ";":
        node, pos = _parse_node(text, pos)
        sequence.append(node)
    children = []
    while pos < len(text) and text[pos] == "(":
        child, pos = _parse_tree(text, pos)
        children.append(child)
    if pos >= len(text) or text[pos] != ")":
        raise SGFParseError("')' 가 필요합니다.")
    pos += 1
    return {"sequence": sequence, "children": children}, pos


def _parse_node(text, pos):
    assert text[pos] == ";"
    pos += 1
    props = {}
    while pos < len(text) and text[pos].isalpha():
        key_start = pos
        while pos < len(text) and text[pos].isalpha():
            pos += 1
        key = text[key_start:pos]
        values = []
        while pos < len(text) and text[pos] == "[":
            pos += 1
            chars = []
            while pos < len(text) and text[pos] != "]":
                if text[pos] == "\\" and pos + 1 < len(text):
                    chars.append(text[pos + 1])
                    pos += 2
                else:
                    chars.append(text[pos])
                    pos += 1
            pos += 1  # skip ']'
            values.append("".join(chars))
            while pos < len(text) and text[pos] in " \t\r\n":
                pos += 1
        props[key] = values
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1
    return {"props": props}, pos


def _main_line_nodes(tree):
    nodes = list(tree["sequence"])
    children = tree["children"]
    while children:
        first = children[0]
        nodes.extend(first["sequence"])
        children = first["children"]
    return nodes


def parse_sgf(text):
    """SGF 텍스트를 SGFGame으로 변환한다 (본선만 사용, 변화도는 무시)."""
    text = text.strip()
    if not text:
        raise SGFParseError("빈 SGF 파일입니다.")
    tree, _ = _parse_tree(text, 0)
    nodes = _main_line_nodes(tree)
    if not nodes:
        raise SGFParseError("SGF에 착수 정보가 없습니다.")

    root_props = nodes[0]["props"]

    def first(key, default=None):
        vals = root_props.get(key)
        return vals[0] if vals else default

    size = int(first("SZ", "19").split(":")[0])
    komi = float(first("KM", "0") or "0")
    handicap = int(first("HA", "0") or "0")
    player_black = first("PB", "흑")
    player_white = first("PW", "백")
    result = first("RE", "")
    root_comment = first("C", None)
    quiz_scene = first("QZ", None) is not None

    ab = [_coord(v, size) for v in root_props.get("AB", [])]
    aw = [_coord(v, size) for v in root_props.get("AW", [])]
    ab = [(x, y) for x, y in ab if x is not None]
    aw = [(x, y) for x, y in aw if x is not None]

    moves = []
    for node in nodes:
        props = node["props"]
        if "B" in props:
            x, y = _coord(props["B"][0], size)
            comment = props.get("C", [None])[0]
            moves.append(Move("B", x, y, comment))
        elif "W" in props:
            x, y = _coord(props["W"][0], size)
            comment = props.get("C", [None])[0]
            moves.append(Move("W", x, y, comment))

    return SGFGame(size, komi, handicap, player_black, player_white,
                    result, root_comment, ab, aw, moves, quiz_scene=quiz_scene)


def parse_sgf_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = None
    for encoding in ("utf-8", "cp949", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SGFParseError(f"SGF 파일의 인코딩을 인식할 수 없습니다: {path}")
    return parse_sgf(text)
