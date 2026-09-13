"""프로 기보(SGF) 복기/훈련 GUI."""

import tkinter as tk
from tkinter import filedialog, messagebox

from . import sgf as sgfmod
from . import replay
from . import render
from .board import GoBoard, BLACK, WHITE

COLOR_NAME = {BLACK: "흑", WHITE: "백"}


class KifuGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("프로 기보 훈련 (SGF 복기)")
        self.root.resizable(False, False)

        self.game = None          # sgfmod.SGFGame
        self.index = 0            # 지금까지 재생한 수 개수 (0 = 시작 전)
        self.board = GoBoard()
        self.move_numbers = {}
        self.guess_marker = None

        self.quiz_mode = tk.BooleanVar(value=False)
        self.quiz_color = tk.StringVar(value="전체")
        self.quiz_correct = 0
        self.quiz_attempts = 0

        self._build_widgets()
        self._render_empty()

    # ---------- 위젯 구성 ----------
    def _build_widgets(self):
        top = tk.Frame(self.root)
        top.grid(row=0, column=0, columnspan=6, sticky="w", padx=10, pady=(10, 0))
        tk.Button(top, text="SGF 불러오기", command=self.load_sgf).pack(side="left")
        self.info_var = tk.StringVar(value="불러온 기보가 없습니다.")
        tk.Label(top, textvariable=self.info_var, font=("Malgun Gothic", 10)).pack(side="left", padx=10)

        dim = render.board_pixel_size(19)
        self.canvas = tk.Canvas(self.root, width=dim, height=dim, bg=render.BOARD_BG, highlightthickness=0)
        self.canvas.grid(row=1, column=0, columnspan=6, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var, font=("Malgun Gothic", 11)).grid(
            row=2, column=0, columnspan=6, pady=(0, 4)
        )

        self.comment_text = tk.Text(self.root, height=3, width=60, wrap="word", state="disabled")
        self.comment_text.grid(row=3, column=0, columnspan=6, padx=10, pady=(0, 6))

        nav = tk.Frame(self.root)
        nav.grid(row=4, column=0, columnspan=6, pady=4)
        self.first_btn = tk.Button(nav, text="|< 처음", command=self.go_first)
        self.prev_btn = tk.Button(nav, text="< 이전", command=self.go_prev)
        self.next_btn = tk.Button(nav, text="다음 >", command=self.go_next)
        self.last_btn = tk.Button(nav, text="끝 >|", command=self.go_last)
        for b in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            b.pack(side="left", padx=4)

        self.slider = tk.Scale(self.root, from_=0, to=0, orient="horizontal", length=520,
                                showvalue=True, command=self.on_slider)
        self.slider.grid(row=5, column=0, columnspan=6, padx=10)

        quiz = tk.Frame(self.root)
        quiz.grid(row=6, column=0, columnspan=6, pady=(6, 10))
        tk.Checkbutton(quiz, text="퀴즈 모드 (다음 수 맞히기)", variable=self.quiz_mode,
                        command=self.on_toggle_quiz).pack(side="left")
        tk.Label(quiz, text="  대상:").pack(side="left")
        tk.OptionMenu(quiz, self.quiz_color, "전체", "흑", "백",
                      command=lambda _=None: self.on_toggle_quiz()).pack(side="left")
        self.quiz_stat_var = tk.StringVar(value="")
        tk.Label(quiz, textvariable=self.quiz_stat_var, font=("Malgun Gothic", 10)).pack(side="left", padx=12)

    # ---------- 파일 불러오기 ----------
    def load_sgf(self):
        path = filedialog.askopenfilename(
            title="SGF 파일 선택",
            filetypes=[("SGF 파일", "*.sgf"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        try:
            game = sgfmod.parse_sgf_file(path)
        except Exception as e:
            messagebox.showerror("SGF 불러오기 실패", str(e))
            return

        self.game = game
        self.index = 0
        self.guess_marker = None
        self.quiz_correct = 0
        self.quiz_attempts = 0

        dim = render.board_pixel_size(game.size)
        self.canvas.config(width=dim, height=dim)
        self.slider.config(to=len(game.moves))

        info = f"{game.player_black}(흑) vs {game.player_white}(백)"
        if game.result:
            info += f"  |  결과: {game.result}"
        info += f"  |  {game.size}줄  |  덤 {game.komi}"
        self.info_var.set(info)

        if getattr(game, "quiz_scene", False) and game.moves:
            # AI 문제 SGF: 마지막 수가 곧 문제이므로 그 직전으로 바로 이동하고
            # 퀴즈 모드를 자동으로 켠다.
            self.index = len(game.moves) - 1
            self.quiz_color.set("전체")
            self.quiz_mode.set(True)
        else:
            self._maybe_auto_advance()
        self.refresh()

    # ---------- 네비게이션 ----------
    def go_first(self):
        if not self.game:
            return
        self.index = 0
        self.guess_marker = None
        self._maybe_auto_advance()
        self.refresh()

    def go_prev(self):
        if not self.game or self.index <= 0:
            return
        self.index -= 1
        self.guess_marker = None
        self.refresh()

    def go_next(self):
        if not self.game or self.index >= len(self.game.moves):
            return
        self.index += 1
        self.guess_marker = None
        self._maybe_auto_advance()
        self.refresh()

    def go_last(self):
        if not self.game:
            return
        self.index = len(self.game.moves)
        self.guess_marker = None
        self.refresh()

    def on_slider(self, value):
        if not self.game:
            return
        v = int(value)
        if v == self.index:
            return
        self.index = v
        self.guess_marker = None
        self.refresh(update_slider=False)

    def on_toggle_quiz(self):
        self.guess_marker = None
        if self.game:
            self._maybe_auto_advance()
        self.refresh()

    def _maybe_auto_advance(self):
        """퀴즈 대상 색이 아닌 수(및 패스)는 자동으로 넘긴다."""
        if not self.quiz_mode.get() or not self.game:
            return
        filt = self.quiz_color.get()
        moves = self.game.moves
        while self.index < len(moves):
            m = moves[self.index]
            if m.x is None:
                self.index += 1
                continue
            name = COLOR_NAME[BLACK if m.color == "B" else WHITE]
            if filt != "전체" and filt != name:
                self.index += 1
                continue
            break

    # ---------- 클릭(퀴즈 응답) ----------
    def on_click(self, event):
        if not self.game or not self.quiz_mode.get():
            return
        if self.index >= len(self.game.moves):
            return
        size = self.game.size
        pt = render.nearest_point(event.x, event.y, size)
        if pt is None:
            return
        x, y = pt

        nxt = self.game.moves[self.index]
        if nxt.x is None:
            self.go_next()
            return
        name = COLOR_NAME[BLACK if nxt.color == "B" else WHITE]
        filt = self.quiz_color.get()
        if filt != "전체" and filt != name:
            self.status_var.set(f"지금은 퀴즈 대상이 아닌 {name} 차례입니다. '다음'으로 넘어가세요.")
            return

        self.quiz_attempts += 1
        correct = (x, y) == (nxt.x, nxt.y)
        if correct:
            self.quiz_correct += 1
            self.guess_marker = (x, y, "correct")
        else:
            self.guess_marker = (nxt.x, nxt.y, "wrong")

        self.index += 1
        self._maybe_auto_advance()
        self.refresh(keep_guess_marker=True)

        acc = (self.quiz_correct / self.quiz_attempts * 100) if self.quiz_attempts else 0
        self.quiz_stat_var.set(f"정답 {self.quiz_correct} / 시도 {self.quiz_attempts} ({acc:.0f}%)")
        self.status_var.set("정답입니다!" if correct else f"오답입니다. 실제 수: 수 {self.index}")

    # ---------- 렌더링 ----------
    def _render_empty(self):
        render.draw_board(self.canvas, 19, GoBoard(size=19).grid)
        self.status_var.set("SGF 파일을 불러와 주세요.")
        self._set_comment("")
        self._update_nav_state()

    def refresh(self, update_slider=True, keep_guess_marker=False):
        if not self.game:
            self._render_empty()
            return

        self.board, self.move_numbers = replay.build_board_with_numbers(self.game, self.index)
        marker = self.guess_marker if keep_guess_marker else None
        render.draw_board(self.canvas, self.game.size, self.board.grid,
                           move_numbers=self.move_numbers, guess_marker=marker)

        if update_slider:
            self.slider.set(self.index)

        total = len(self.game.moves)
        if self.index == 0:
            turn_desc = "대국 시작"
        elif self.index >= total:
            turn_desc = "마지막 수"
        else:
            nxt = self.game.moves[self.index]
            turn_desc = f"다음 수: {COLOR_NAME[BLACK if nxt.color == 'B' else WHITE]}"
        if not keep_guess_marker:
            self.status_var.set(f"수 {self.index} / {total}  |  {turn_desc}")

        if self.index > 0:
            last = self.game.moves[self.index - 1]
            self._set_comment(last.comment or "")
        else:
            self._set_comment(self.game.root_comment or "")

        self._update_nav_state()

    def _set_comment(self, text):
        self.comment_text.config(state="normal")
        self.comment_text.delete("1.0", "end")
        if text:
            self.comment_text.insert("1.0", text)
        self.comment_text.config(state="disabled")

    def _update_nav_state(self):
        has_game = self.game is not None
        total = len(self.game.moves) if has_game else 0
        self.first_btn.config(state=tk.NORMAL if has_game and self.index > 0 else tk.DISABLED)
        self.prev_btn.config(state=tk.NORMAL if has_game and self.index > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if has_game and self.index < total else tk.DISABLED)
        self.last_btn.config(state=tk.NORMAL if has_game and self.index < total else tk.DISABLED)
