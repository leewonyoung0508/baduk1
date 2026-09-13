"""Tkinter 기반 바둑 GUI (2인 로컬 대국)."""

import tkinter as tk
from tkinter import messagebox

from .board import GoBoard, BLACK, WHITE, EMPTY
from . import render
from .render import MARGIN, CELL, BOARD_BG


class GoGUI:
    def __init__(self, root, size=19, komi=6.5):
        self.root = root
        self.size = size
        self.komi = komi
        self.board = GoBoard(size=size, komi=komi)
        self.mode = "play"  # "play" or "scoring"
        self.dead_stones = set()

        self.root.title("바둑 (Baduk)")
        self.root.resizable(False, False)

        dim = MARGIN * 2 + (size - 1) * CELL
        self.canvas = tk.Canvas(root, width=dim, height=dim, bg=BOARD_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, columnspan=6, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(root, textvariable=self.status_var, font=("Malgun Gothic", 11))
        self.status_label.grid(row=1, column=0, columnspan=6, pady=(0, 6))

        self.pass_btn = tk.Button(root, text="착수 포기 (Pass)", command=self.on_pass)
        self.pass_btn.grid(row=2, column=0, padx=4, pady=6)

        self.undo_btn = tk.Button(root, text="한 수 무르기", command=self.on_undo)
        self.undo_btn.grid(row=2, column=1, padx=4, pady=6)

        self.resign_btn = tk.Button(root, text="기권", command=self.on_resign)
        self.resign_btn.grid(row=2, column=2, padx=4, pady=6)

        self.new_btn = tk.Button(root, text="새 게임", command=self.on_new_game)
        self.new_btn.grid(row=2, column=3, padx=4, pady=6)

        self.confirm_btn = tk.Button(root, text="계가 확정", command=self.on_confirm_score)
        self.confirm_btn.grid(row=2, column=4, padx=4, pady=6)
        self.resume_btn = tk.Button(root, text="대국 재개", command=self.on_resume)
        self.resume_btn.grid(row=2, column=5, padx=4, pady=6)

        self.redraw()

    # ---------- 이벤트 ----------
    def on_click(self, event):
        pt = render.nearest_point(event.x, event.y, self.size)
        if pt is None:
            return
        x, y = pt

        if self.mode == "scoring":
            if self.board.grid[y][x] == EMPTY:
                return
            group = self.board.group_stones(x, y)
            if group & self.dead_stones:
                self.dead_stones -= group
            else:
                self.dead_stones |= group
            self.redraw()
            return

        ok, reason = self.board.play(x, y)
        if not ok:
            self.flash_status(reason)
        self.after_move()

    def on_pass(self):
        if self.mode != "play":
            return
        self.board.pass_turn()
        self.after_move()

    def on_undo(self):
        if self.mode == "scoring":
            return
        if self.board.undo():
            self.redraw()
        else:
            self.flash_status("더 이상 무를 수 없습니다.")

    def on_resign(self):
        if self.mode != "play":
            return
        if not messagebox.askyesno("기권 확인", "정말 기권하시겠습니까?"):
            return
        self.board.resign()
        self.after_move()

    def on_new_game(self):
        if not messagebox.askyesno("새 게임", "현재 대국을 종료하고 새 게임을 시작할까요?"):
            return
        self.board = GoBoard(size=self.size, komi=self.komi)
        self.mode = "play"
        self.dead_stones = set()
        self.redraw()

    def on_confirm_score(self):
        result = self.board.area_score(self.dead_stones)
        b, w = result["black_total"], result["white_total"]
        if b > w:
            msg = f"흑 {b:.1f} : 백 {w:.1f}\n\n흑 {b - w:.1f}집 승"
        elif w > b:
            msg = f"흑 {b:.1f} : 백 {w:.1f}\n\n백 {w - b:.1f}집 승"
        else:
            msg = f"흑 {b:.1f} : 백 {w:.1f}\n\n무승부"
        messagebox.showinfo("계가 결과", msg)

    def on_resume(self):
        if self.mode != "scoring":
            return
        self.board.resume_from_scoring()
        self.mode = "play"
        self.dead_stones = set()
        self.redraw()

    def after_move(self):
        if self.board.game_over and self.mode == "play":
            if self.board.resigned_by is not None:
                winner = "백" if self.board.resigned_by == BLACK else "흑"
                self.redraw()
                messagebox.showinfo("대국 종료", f"{winner} 승 (기권)")
                return
            self.mode = "scoring"
        self.redraw()

    def flash_status(self, text):
        self.status_var.set(text)
        self.root.after(1500, self.update_status_text)

    # ---------- 렌더링 ----------
    def redraw(self):
        dead = self.dead_stones if self.mode == "scoring" else None
        ko = self.board.ko_point if (self.mode == "play" and not self.board.game_over) else None
        render.draw_board(self.canvas, self.size, self.board.grid, dead_stones=dead, ko_point=ko)
        self.update_status_text()
        self.update_buttons()

    def update_status_text(self):
        b = self.board
        if self.mode == "scoring":
            self.status_var.set(
                "계가 단계: 죽은 돌을 클릭해 표시한 뒤 '계가 확정'을 누르세요. "
                f"(흑 따낸 돌 {b.captures[BLACK]}, 백 따낸 돌 {b.captures[WHITE]})"
            )
            return
        if b.game_over:
            self.status_var.set("게임 종료")
            return
        turn = "흑" if b.current == BLACK else "백"
        self.status_var.set(
            f"{turn} 차례  |  수: {b.move_count}  |  흑 따낸 돌: {b.captures[BLACK]}  백 따낸 돌: {b.captures[WHITE]}"
        )

    def update_buttons(self):
        scoring = self.mode == "scoring"
        state_play = tk.DISABLED if scoring else tk.NORMAL
        self.pass_btn.config(state=state_play)
        self.undo_btn.config(state=state_play)
        self.resign_btn.config(state=state_play)
        self.confirm_btn.config(state=(tk.NORMAL if scoring else tk.DISABLED))
        self.resume_btn.config(state=(tk.NORMAL if scoring else tk.DISABLED))
