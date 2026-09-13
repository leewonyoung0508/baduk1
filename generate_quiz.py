"""KataGo 분석을 이용해 SGF 기보로부터 '다음 수 맞히기' 문제 SGF를 자동 생성한다.

기본 동작(threshold=0): 매 수마다 KataGo의 최선수를 정답으로 채택해서 그 수로
대체한다. 대체된 수를 기준으로 다음 수를 이어서 분석하므로(자체 정합적인 한 줄
기보), 결과 SGF는 항상 합법적인 수순이며 기존 '프로 기보 훈련' 화면에 그대로
불러와 복기/퀴즈 모드로 쓸 수 있다.

threshold를 0보다 크게 주면 KataGo 최선수와 실제 수의 승률차가 threshold(%p)
이상 나는 '실수 지점'에서만 대체하고, 그 외에는 실제 수를 그대로 둔다.

사용 예:
    python generate_quiz.py --sgf samples/example.sgf --out samples/example_quiz.sgf
    python generate_quiz.py --sgf my_game.sgf --threshold 3 --color B --visits 400
"""

import argparse
import sys
import time

from go import sgf as sgfmod
from go import sgfwrite
from go.katago import KataGoEngine, KataGoError, xy_to_katago, katago_to_xy

DEFAULT_KATAGO = r"C:\baduk\lizzie\katago_cuda.exe"
DEFAULT_MODEL = r"C:\baduk\lizzie\KataGo28b.gz"
DEFAULT_CONFIG = r"C:\baduk\lizzie\analysis_config.cfg"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sgf", required=True, help="입력 SGF 파일 경로")
    p.add_argument("--out", default=None, help="출력 SGF 경로 (기본: <입력파일>_quiz.sgf)")
    p.add_argument("--katago", default=DEFAULT_KATAGO, help="katago 실행파일 경로")
    p.add_argument("--model", default=DEFAULT_MODEL, help="katago 모델(.gz) 경로")
    p.add_argument("--katago-config", default=DEFAULT_CONFIG, help="katago analysis config(.cfg) 경로")
    p.add_argument("--visits", type=int, default=600, help="수당 분석 방문수(maxVisits), 기본 600")
    p.add_argument("--color", choices=["all", "B", "W"], default="all",
                    help="문제로 만들 대상 색 (기본: all)")
    p.add_argument("--start", type=int, default=1, help="분석 시작 수순 번호(1부터), 기본 1")
    p.add_argument("--end", type=int, default=None, help="분석 종료 수순 번호(포함), 기본: 끝까지")
    p.add_argument("--threshold", type=float, default=0.0,
                    help="AI 최선수로 대체하기 위한 최소 승률차(%%p). 0이면 항상 대체(전체 수순 문제화). 기본 0")
    p.add_argument("--rules", default="chinese", help="katago 규칙 문자열, 기본 chinese")
    p.add_argument("--komi", type=float, default=None, help="덤 (기본: SGF에 기록된 값)")
    p.add_argument("--quiet", action="store_true", help="진행 로그 출력 끄기")
    return p.parse_args()


def main():
    args = parse_args()
    out_path = args.out or (args.sgf.rsplit(".", 1)[0] + "_quiz.sgf")

    game = sgfmod.parse_sgf_file(args.sgf)
    size = game.size
    komi = args.komi if args.komi is not None else game.komi
    end = args.end if args.end is not None else len(game.moves)

    initial_stones = [("B", x, y) for x, y in game.ab] + [("W", x, y) for x, y in game.aw]

    engine = KataGoEngine(args.katago, args.katago_config, args.model).start()
    output_moves = []
    history = []  # 지금까지 채택된(실제 또는 AI 대체) 수순, katago 문의의 context로 사용
    replaced_count = 0
    analyzed_count = 0
    t0 = time.time()

    try:
        for i, mv in enumerate(game.moves):
            move_no = i + 1
            color = mv.color
            in_range = args.start <= move_no <= end
            wants_color = args.color == "all" or args.color == color
            out_x, out_y, note = mv.x, mv.y, None

            if in_range and wants_color and mv.x is not None:
                resp = engine.analyze(initial_stones, history, size, komi,
                                       turn=len(history), max_visits=args.visits,
                                       rules=args.rules)
                analyzed_count += 1
                move_infos = resp.get("moveInfos", [])
                if move_infos:
                    top = move_infos[0]
                    top_x, top_y = katago_to_xy(top["move"], size)
                    actual_str = xy_to_katago(mv.x, mv.y, size)
                    actual_info = next((m for m in move_infos if m["move"] == actual_str), None)
                    top_wr = top.get("winrate", 0.0) * 100
                    top_score = top.get("scoreLead")
                    actual_wr = actual_info.get("winrate", 0.0) * 100 if actual_info else None
                    diff = (top_wr - actual_wr) if actual_wr is not None else 100.0

                    should_replace = diff >= args.threshold and (top_x, top_y) != (mv.x, mv.y)
                    if should_replace:
                        replaced_count += 1
                        note = f"[AI] 실제 수: {actual_str} / AI 추천: {top['move']} (승률 {top_wr:.1f}%"
                        if actual_wr is not None:
                            note += f" vs {actual_wr:.1f}%"
                        note += ")"
                        if top_score is not None:
                            note += f", 예상 집차 {top_score:+.1f}"
                        out_x, out_y = top_x, top_y
                    else:
                        note = f"[AI] 승률 {top_wr:.1f}% (AI와 같거나 근접한 수)"

                if not args.quiet:
                    elapsed = time.time() - t0
                    print(f"[{move_no}/{len(game.moves)}] {color} 분석 완료 "
                          f"(대체 {replaced_count}건, 경과 {elapsed:.0f}s)", flush=True)

            comment_parts = [mv.comment] if mv.comment else []
            if note:
                comment_parts.append(note)
            out_comment = "\n".join(comment_parts) if comment_parts else None

            output_moves.append((color, out_x, out_y, out_comment))
            history.append((color, out_x, out_y))
    except KeyboardInterrupt:
        print("사용자가 중단했습니다. 지금까지 분석한 결과로 저장합니다.", file=sys.stderr)
    except KataGoError as e:
        engine.close()
        print(f"KataGo 오류: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.close()

    sgfwrite.write_sgf(out_path, size, komi, game.handicap, game.player_black,
                        game.player_white, game.result, game.root_comment,
                        game.ab, game.aw, output_moves)

    print(f"완료: {analyzed_count}수 분석, {replaced_count}수 대체 -> {out_path}")


if __name__ == "__main__":
    main()
