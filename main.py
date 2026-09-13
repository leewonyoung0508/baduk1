"""바둑 프로그램 실행 진입점."""

import tkinter as tk

from go.gui import GoGUI
from go.kifu_gui import KifuGUI
from go.quiz_config_gui import QuizConfigGUI


def open_play(parent):
    win = tk.Toplevel(parent)
    GoGUI(win, size=19, komi=6.5)


def open_kifu(parent):
    win = tk.Toplevel(parent)
    KifuGUI(win)


def open_quiz_settings(parent):
    win = tk.Toplevel(parent)
    QuizConfigGUI(win)


def main():
    root = tk.Tk()
    root.title("바둑 프로그램")
    root.resizable(False, False)

    frame = tk.Frame(root, padx=40, pady=40)
    frame.pack()

    tk.Label(frame, text="바둑 프로그램", font=("Malgun Gothic", 16, "bold")).pack(pady=(0, 20))
    tk.Button(frame, text="2인 로컬 대국", width=26, height=2,
              command=lambda: open_play(root)).pack(pady=6)
    tk.Button(frame, text="프로 기보 훈련 (SGF 복기)", width=26, height=2,
              command=lambda: open_kifu(root)).pack(pady=6)
    tk.Button(frame, text="문제 생성 설정", width=26, height=2,
              command=lambda: open_quiz_settings(root)).pack(pady=6)

    root.mainloop()


if __name__ == "__main__":
    main()
