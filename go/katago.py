"""KataGo 분석 엔진(Analysis Engine) 연동 유틸.

KataGo를 `analysis` 모드로 서브프로세스로 띄우고, stdin/stdout으로 JSON 한 줄씩
주고받는다. (프로토콜: https://github.com/lightvector/KataGo/blob/master/docs/Analysis_Engine.md)
"""

import json
import subprocess

COL_LETTERS = "ABCDEFGHJKLMNOPQRST"  # I는 관례상 제외 (go/render.py와 동일 규칙)


class KataGoError(Exception):
    pass


def xy_to_katago(x, y, size):
    """보드 좌표(x, y, 좌상단이 0,0)를 KataGo 좌표 문자열(예: 'Q16')로 변환."""
    if x is None or y is None:
        return "pass"
    return f"{COL_LETTERS[x]}{size - y}"


def katago_to_xy(move, size):
    """KataGo 좌표 문자열을 (x, y)로 변환. pass/resign이면 (None, None)."""
    if move is None:
        return None, None
    m = move.strip().lower()
    if m in ("pass", "resign"):
        return None, None
    col = COL_LETTERS.index(move[0].upper())
    row = int(move[1:])
    return col, size - row


class KataGoEngine:
    """KataGo analysis 엔진 프로세스를 감싸는 래퍼."""

    def __init__(self, katago_exe, config_path, model_path):
        self.katago_exe = katago_exe
        self.config_path = config_path
        self.model_path = model_path
        self.proc = None
        self._next_id = 0

    def start(self):
        cmd = [
            self.katago_exe, "analysis",
            "-config", self.config_path,
            "-model", self.model_path,
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
        )
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        if self.proc is None:
            return
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def _check_alive(self):
        if self.proc is None or self.proc.poll() is not None:
            stderr = ""
            if self.proc is not None:
                try:
                    stderr = self.proc.stderr.read()
                except Exception:
                    stderr = ""
            raise KataGoError(f"KataGo 프로세스가 실행 중이 아닙니다.\n{stderr}")

    def analyze(self, initial_stones, moves, size, komi, turn, max_visits,
                rules="chinese", initial_player=None):
        """단일 위치를 분석한다.

        initial_stones: [(color 'B'/'W', x, y), ...] (AB/AW 배석, 또는 정적 국면 전체 돌)
        moves: [(color 'B'/'W', x, y 또는 None), ...] (turn 이전까지 실제로 둔 수)
        turn: moves 리스트 중 몇 수까지 두었을 때의 국면을 분석할지 (turn == len(moves)면
              moves를 전부 둔 뒤, 다음 둘 사람 차례의 국면)
        initial_player: moves가 비어 있을 때(정적 국면만 줄 때) 누구 차례인지 'B'/'W'로 지정.
        반환: 응답 JSON(dict). 실패 시 KataGoError.
        """
        self._check_alive()
        self._next_id += 1
        query_id = f"q{self._next_id}"

        query = {
            "id": query_id,
            "initialStones": [[c, xy_to_katago(x, y, size)] for c, x, y in initial_stones],
            "moves": [[c, xy_to_katago(x, y, size)] for c, x, y in moves],
            "rules": rules,
            "komi": komi,
            "boardXSize": size,
            "boardYSize": size,
            "analyzeTurns": [turn],
            "maxVisits": max_visits,
        }
        if initial_player is not None:
            query["initialPlayer"] = initial_player

        self.proc.stdin.write(json.dumps(query) + "\n")
        self.proc.stdin.flush()

        while True:
            self._check_alive()
            line = self.proc.stdout.readline()
            if not line:
                stderr = ""
                try:
                    stderr = self.proc.stderr.read()
                except Exception:
                    pass
                raise KataGoError(f"KataGo가 응답 없이 종료되었습니다.\n{stderr}")
            line = line.strip()
            if not line:
                continue
            resp = json.loads(line)
            if resp.get("id") != query_id:
                continue
            if "error" in resp:
                raise KataGoError(f"KataGo 오류: {resp['error']}")
            if resp.get("isDuringSearch"):
                continue
            return resp
