"""quiz_config.ini 설정 파일을 읽어서 그대로 문제 SGF를 생성한다.

명령줄 옵션을 직접 안 외워도 되도록 만든 진입점이다. quiz_config.ini를
열어서 원하는 값으로 고친 뒤 아래처럼 실행하면 된다.

    python make_quiz.py
    python make_quiz.py 다른설정.ini   (다른 설정 파일을 쓰고 싶을 때)
"""

import configparser
import os
import sys
import types

import generate_random_quiz as gq

YES_VALUES = {"예", "y", "yes", "true", "1"}


def _get(cfg, key, default=""):
    return cfg.get("문제생성", key, fallback=default).strip()


def _get_int_or_none(cfg, key):
    v = _get(cfg, key)
    return int(v) if v else None


def load_config(path):
    if not os.path.exists(path):
        print(f"설정 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")

    source = _get(cfg, "기보경로")
    if not source:
        print("설정 파일의 '기보경로'를 채워주세요.")
        sys.exit(1)
    if not os.path.exists(source):
        print(f"'기보경로'에 해당하는 경로가 없습니다: {source}")
        sys.exit(1)

    difficulty_raw = _get(cfg, "난이도", "5")
    try:
        min_gap = float(difficulty_raw)
    except ValueError:
        print(f"'난이도' 값을 이해할 수 없습니다: {difficulty_raw!r} "
              f"(승률차 %p를 숫자로 입력하세요, 예: 5)")
        sys.exit(1)

    color_kr = _get(cfg, "색", "전체")
    color_map = {"전체": "all", "흑": "B", "백": "W"}
    if color_kr not in color_map:
        print(f"'색' 값을 이해할 수 없습니다: {color_kr!r} (전체/흑/백)")
        sys.exit(1)

    args = types.SimpleNamespace(
        sgf=source if os.path.isfile(source) else None,
        sgf_dir=source if os.path.isdir(source) else None,
        out_dir=_get(cfg, "출력폴더", "quiz_output"),
        count=int(_get(cfg, "문제개수", "10")),
        katago=_get(cfg, "카타고실행파일", gq.DEFAULT_KATAGO),
        model=_get(cfg, "카타고모델", gq.DEFAULT_MODEL),
        katago_config=_get(cfg, "카타고설정파일", gq.DEFAULT_CONFIG),
        visits=int(_get(cfg, "분석강도", "600")),
        color=color_map[color_kr],
        min_move=_get_int_or_none(cfg, "최소수순") or 1,
        max_move=_get_int_or_none(cfg, "최대수순"),
        min_gap=min_gap,
        rules="chinese",
        komi=None,
        seed=_get_int_or_none(cfg, "시드"),
        max_attempts=None,
        hide_answer=_get(cfg, "정답포함", "아니오") not in YES_VALUES,
        quiet=False,
    )
    return args


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "quiz_config.ini"
    args = load_config(config_path)
    print(f"설정 파일: {config_path}")
    print(f"기보: {args.sgf or args.sgf_dir}")
    print(f"문제 {args.count}개, 난이도(승률차) {args.min_gap}%p 이상, "
          f"정답 {'미포함' if args.hide_answer else '포함'}")
    gq.run(args)


if __name__ == "__main__":
    main()
