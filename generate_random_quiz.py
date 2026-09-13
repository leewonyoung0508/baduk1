"""기보(SGF) 하나 또는 폴더 전체에서 장면을 무작위로 뽑아, 각 장면마다 'KataGo
추천 1위 수'를 맞히는 문제 SGF를 하나씩 만든다.

generate_quiz.py와 다르게, 각 문제는 서로 독립적이다: 실제 기보의 처음부터 그
장면 직전까지의 실제 수순을 그대로 담아두고(그래서 기존 화면에서 수순 번호가
정상적으로 보이고 이전/다음으로 복기할 수 있다), 그 다음에 KataGo가 1등으로
추천하는 수 딱 하나만 마지막 수(정답)로 덧붙인다. 실전 수순 자체는 전혀 바꾸지
않으므로 기보가 왜곡되지 않는다.

--min-gap 옵션을 주면, KataGo 추천 1위와 2위 수의 승률 차이가 그 값(%p) 이상
나는(=답이 뚜렷한) 장면만 채택한다. 조건을 만족하는 장면이 나올 때까지 무작위로
계속 뽑아서 시도하므로 시간이 더 걸릴 수 있다.

생성된 각 문제 SGF는 기존 '프로 기보 훈련' 화면에서 그대로 불러와 퀴즈 모드로
풀 수 있다 (문제당 파일 하나, 첫 클릭이 곧 정답 확인).

--hide-answer를 주면 정답(AI 추천수)을 SGF에 아예 담지 않는다. 실전 마지막 수까지만
저장되므로 LizzieYzy 같은 다른 SGF/분석 뷰어로 열어도 답이 미리 보이지 않고, 그 국면에서
직접 최선수를 생각해본 뒤 그 프로그램 자체 분석으로 확인하는 용도로 쓸 수 있다.

사용 예:
    python generate_random_quiz.py --sgf samples/example.sgf --out-dir samples/example_scenes --count 5
    python generate_random_quiz.py --sgf-dir "C:\\기보폴더" --out-dir quiz_out --count 20 --min-gap 5
    python generate_random_quiz.py --sgf-dir "C:\\기보폴더" --out-dir quiz_out --count 20 --min-gap 5 --hide-answer
"""

import argparse
import glob
import os
import random
import re

from go import sgf as sgfmod
from go import sgfwrite
from go.katago import KataGoEngine, KataGoError, katago_to_xy

DEFAULT_KATAGO = r"C:\baduk\lizzie\katago_cuda.exe"
DEFAULT_MODEL = r"C:\baduk\lizzie\KataGo28b.gz"
DEFAULT_CONFIG = r"C:\baduk\lizzie\analysis_config.cfg"

COLOR_NAME = {"B": "흑", "W": "백"}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--sgf", help="입력 SGF 파일 경로 (한 기보에서만 뽑을 때)")
    src.add_argument("--sgf-dir", help="SGF 파일들이 들어있는 폴더 (여러 기보 중에서 무작위로 뽑을 때)")
    p.add_argument("--out-dir", default=None, help="문제 SGF들을 저장할 폴더 (기본: <이름>_scenes)")
    p.add_argument("--count", type=int, default=10, help="만들 문제 개수, 기본 10")
    p.add_argument("--katago", default=DEFAULT_KATAGO, help="katago 실행파일 경로")
    p.add_argument("--model", default=DEFAULT_MODEL, help="katago 모델(.gz) 경로")
    p.add_argument("--katago-config", default=DEFAULT_CONFIG, help="katago analysis config(.cfg) 경로")
    p.add_argument("--visits", type=int, default=600, help="문제당 분석 방문수(maxVisits), 기본 600")
    p.add_argument("--color", choices=["all", "B", "W"], default="all",
                    help="어느 색 차례의 장면만 뽑을지 (기본: all)")
    p.add_argument("--min-move", type=int, default=1, help="장면을 뽑을 최소 수순 번호(1부터), 기본 1")
    p.add_argument("--max-move", type=int, default=None, help="장면을 뽑을 최대 수순 번호, 기본: 끝까지")
    p.add_argument("--min-gap", type=float, default=0.0,
                    help="AI 추천 1위와 2위 수의 승률차(%%p)가 이 값 이상인 장면만 채택. 기본 0(필터 없음)")
    p.add_argument("--rules", default="chinese", help="katago 규칙 문자열, 기본 chinese")
    p.add_argument("--komi", type=float, default=None, help="덤 (기본: 각 SGF에 기록된 값)")
    p.add_argument("--seed", type=int, default=None, help="난수 시드 (같은 값이면 항상 같은 장면 선택)")
    p.add_argument("--max-attempts", type=int, default=None,
                    help="min-gap 조건을 만족하는 장면을 찾기 위한 최대 시도 횟수 (기본: count * 40)")
    p.add_argument("--hide-answer", action="store_true",
                    help="정답(AI 추천수)을 SGF에 아예 안 담는다. 문제 국면까지만 저장하므로 "
                         "LizzieYzy 등 다른 SGF 뷰어로 봐도 답이 미리 보이지 않는다.")
    p.add_argument("--quiet", action="store_true", help="진행 로그 출력 끄기")
    return p.parse_args()


def candidate_move_indices(game, args):
    max_move = args.max_move if args.max_move is not None else len(game.moves)
    return [
        i for i, m in enumerate(game.moves)
        if m.x is not None
        and args.min_move <= i + 1 <= max_move
        and (args.color == "all" or args.color == m.color)
    ]


def sanitize(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def run(args):
    """args: parse_args()가 만드는 것과 같은 속성을 가진 객체 (Namespace 등)."""

    if args.sgf:
        files = [args.sgf]
        default_base = os.path.splitext(os.path.basename(args.sgf))[0]
    else:
        files = sorted(glob.glob(os.path.join(args.sgf_dir, "**", "*.sgf"), recursive=True))
        default_base = sanitize(os.path.basename(os.path.normpath(args.sgf_dir)))
        if not files:
            print(f"'{args.sgf_dir}'에서 SGF 파일을 찾지 못했습니다.")
            return
        print(f"기보 {len(files)}개 중에서 무작위로 장면을 뽑습니다.")

    out_dir = args.out_dir or f"{default_base}_scenes"
    os.makedirs(out_dir, exist_ok=True)

    max_attempts = args.max_attempts or max(200, args.count * 40)
    rng = random.Random(args.seed)

    game_cache = {}
    candidate_cache = {}
    visited = set()

    def get_game(path):
        if path not in game_cache:
            try:
                game_cache[path] = sgfmod.parse_sgf_file(path)
            except Exception as e:
                print(f"SGF 파싱 실패, 건너뜀: {path} ({e})")
                game_cache[path] = None
        return game_cache[path]

    engine = KataGoEngine(args.katago, args.katago_config, args.model).start()
    made = 0
    attempts = 0
    rejected_gap = 0
    try:
        while made < args.count and attempts < max_attempts and files:
            attempts += 1
            path = rng.choice(files)
            game = get_game(path)
            if game is None:
                continue

            if path not in candidate_cache:
                candidate_cache[path] = candidate_move_indices(game, args)
            candidates = [i for i in candidate_cache[path] if (path, i) not in visited]
            if not candidates:
                continue
            i = rng.choice(candidates)
            visited.add((path, i))

            size = game.size
            komi = args.komi if args.komi is not None else game.komi
            history = [(m.color, m.x, m.y) for m in game.moves[:i]]
            color = game.moves[i].color
            initial_stones = [("B", x, y) for x, y in game.ab] + \
                              [("W", x, y) for x, y in game.aw]
            initial_player = "W" if (game.handicap and game.handicap > 0) else "B"

            try:
                resp = engine.analyze(initial_stones, history, size, komi, turn=i,
                                       max_visits=args.visits, rules=args.rules,
                                       initial_player=initial_player)
            except KataGoError as e:
                print(f"분석 실패, 건너뜀 ({os.path.basename(path)} {i + 1}수): {e}")
                continue

            move_infos = resp.get("moveInfos", [])
            if not move_infos:
                continue

            top = move_infos[0]
            top_wr = top.get("winrate", 0.0) * 100
            if len(move_infos) >= 2:
                second_wr = move_infos[1].get("winrate", 0.0) * 100
                gap = top_wr - second_wr
            else:
                gap = 100.0  # 후보가 하나뿐 = 답이 명확한 장면으로 취급

            if gap < args.min_gap:
                rejected_gap += 1
                continue

            top_x, top_y = katago_to_xy(top["move"], size)
            top_score = top.get("scoreLead")

            game_stem = sanitize(os.path.splitext(os.path.basename(path))[0])
            made += 1
            fname = f"{game_stem}_scene{made:02d}_move{i + 1:03d}_{color}.sgf"
            out_path = os.path.join(out_dir, fname)
            output_moves = [(m.color, m.x, m.y, m.comment) for m in game.moves[:i]]

            if args.hide_answer:
                # 정답을 SGF에 담지 않는다: 문제 국면(마지막 실전 수)까지만 저장.
                sgfwrite.write_sgf(
                    out_path, size, komi, game.handicap, game.player_black, game.player_white,
                    "", game.root_comment, game.ab, game.aw, output_moves,
                    quiz_scene=False,
                )
            else:
                comment = (f"[AI 문제] {os.path.basename(path)}의 실전 {i + 1}수 국면 "
                           f"(다음 둘 색: {COLOR_NAME[color]}) - AI 추천 1위, 승률 {top_wr:.1f}%")
                if len(move_infos) >= 2:
                    comment += f" (2위와 {gap:.1f}%p 차이)"
                if top_score is not None:
                    comment += f", 예상 집차 {top_score:+.1f}"
                output_moves.append((color, top_x, top_y, comment))
                sgfwrite.write_sgf(
                    out_path, size, komi, game.handicap, game.player_black, game.player_white,
                    "", game.root_comment, game.ab, game.aw, output_moves,
                    quiz_scene=True,
                )
            if not args.quiet:
                print(f"[{made}/{args.count}] {os.path.basename(path)} {i + 1}수 -> "
                      f"{fname} (승률 {top_wr:.1f}%, 격차 {gap:.1f}%p)")
    finally:
        engine.close()

    print(f"완료: {made}개 문제 생성 (시도 {attempts}회, gap 미달로 제외 {rejected_gap}건) -> {out_dir}")
    if made < args.count:
        print("목표 개수를 못 채웠습니다. --max-attempts를 늘리거나 --min-gap을 낮춰보세요.")
    return made


def main():
    run(parse_args())


if __name__ == "__main__":
    main()
