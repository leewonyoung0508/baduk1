"""quiz_config.ini 설정 파일을 편집하고 문제 생성을 실행하는 GUI 창.

메모장으로 ini 파일을 직접 고치는 대신, 이 창에서 값을 입력/선택하고
"저장" 또는 "저장 후 생성 실행"을 누르면 된다.
"""

import configparser
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import generate_random_quiz as gq
import make_quiz

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quiz_config.ini")

COLOR_VALUES = ["전체", "흑", "백"]
YESNO_VALUES = ["예", "아니오"]

CONFIG_TEMPLATE = """; ============================================================
;  AI 문제 자동 생성 설정 파일
;  이 파일을 수정하고 "python make_quiz.py"를 실행하면
;  여기 적은 대로 문제 SGF가 자동으로 만들어집니다.
;  ';'로 시작하는 줄은 설명이라 프로그램이 무시합니다.
; ============================================================

[문제생성]

; 기보 파일 하나의 경로, 또는 기보들이 여러 개 들어있는 폴더 경로
; (폴더를 주면 그 안의 모든 SGF 중에서 무작위로 뽑습니다)
기보경로 = {기보경로}

; 문제 SGF들을 저장할 폴더
출력폴더 = {출력폴더}

; 만들 문제 개수
문제개수 = {문제개수}

; 난이도: AI 1등수와 2등수의 승률차(%p) 기준을 숫자로 입력합니다.
;   숫자가 작을수록 1등과 2등의 차이가 적어 헷갈리는(어려운) 문제가 되고,
;   숫자가 클수록 차이가 뚜렷한(쉬운) 문제가 됩니다.
;   예: 1 = 어려움 / 5 = 보통 / 15 = 쉬움  (원하는 숫자로 자유롭게 조절 가능)
난이도 = {난이도}

; 정답 포함 여부: 예 / 아니오
;   예     = SGF에 정답(AI 추천수)까지 포함. 우리 바둑 프로그램에서 열면
;            바로 그 장면으로 이동해서 퀴즈 모드로 풀 수 있음.
;   아니오 = 정답을 담지 않고 실전 마지막 수까지만 저장.
;            LizzieYzy 등 다른 프로그램에서 직접 풀어보고 싶을 때 사용.
정답포함 = {정답포함}

; 어느 색 차례의 장면만 뽑을지: 전체 / 흑 / 백
색 = {색}

; 장면을 뽑을 수순 범위 (1부터). 비워두면 전체 범위에서 뽑습니다.
최소수순 = {최소수순}
최대수순 = {최대수순}

; 분석 강도(방문수). 클수록 정확하지만 문제 하나당 시간이 더 걸립니다.
분석강도 = {분석강도}

; 같은 숫자를 주면 항상 같은 장면들이 뽑힙니다. 비워두면 매번 다르게 뽑힘.
시드 = {시드}

; ---------------- 아래는 웬만하면 안 건드려도 됩니다 ----------------

; KataGo 실행 파일 / 모델 / 분석 설정 파일 경로
카타고실행파일 = {카타고실행파일}
카타고모델 = {카타고모델}
카타고설정파일 = {카타고설정파일}
"""

FIELDS = [
    "기보경로", "출력폴더", "문제개수", "난이도", "정답포함", "색",
    "최소수순", "최대수순", "분석강도", "시드",
    "카타고실행파일", "카타고모델", "카타고설정파일",
]

DEFAULTS = {
    "기보경로": "",
    "출력폴더": "quiz_output",
    "문제개수": "10",
    "난이도": "5",
    "정답포함": "아니오",
    "색": "전체",
    "최소수순": "",
    "최대수순": "",
    "분석강도": "600",
    "시드": "",
    "카타고실행파일": gq.DEFAULT_KATAGO,
    "카타고모델": gq.DEFAULT_MODEL,
    "카타고설정파일": gq.DEFAULT_CONFIG,
}


class _QueueWriter:
    """print() 출력을 쓰레드 밖 Text 위젯으로 넘기기 위한 stdout 대체 객체."""

    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


class QuizConfigGUI:
    def __init__(self, root, config_path=CONFIG_PATH):
        self.root = root
        self.config_path = config_path
        self.root.title("문제 생성 설정")
        self.root.resizable(False, False)

        self.vars = {name: tk.StringVar() for name in FIELDS}
        self.running = False
        self.log_queue = queue.Queue()

        self._build_widgets()
        self._load()

    # ---------- 위젯 구성 ----------
    def _build_widgets(self):
        pad = {"padx": 8, "pady": 4}
        frame = tk.Frame(self.root, padx=14, pady=14)
        frame.pack()

        row = 0
        row = self._add_path_row(frame, row, "기보경로", "기보 파일/폴더 경로", browse="any")
        row = self._add_path_row(frame, row, "출력폴더", "문제 SGF 저장 폴더", browse="dir")
        row = self._add_entry_row(frame, row, "문제개수", "만들 문제 개수")
        row = self._add_entry_row(frame, row, "난이도", "난이도 (승률차 %p, 작을수록 어려움)")
        row = self._add_combo_row(frame, row, "정답포함", "정답 포함 여부", YESNO_VALUES)
        row = self._add_combo_row(frame, row, "색", "어느 색 차례만 뽑을지", COLOR_VALUES)
        row = self._add_entry_row(frame, row, "최소수순", "최소 수순 (비우면 전체)")
        row = self._add_entry_row(frame, row, "최대수순", "최대 수순 (비우면 전체)")
        row = self._add_entry_row(frame, row, "분석강도", "KataGo 분석 방문수")
        row = self._add_entry_row(frame, row, "시드", "난수 시드 (비우면 매번 다름)")

        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 6))
        row += 1
        tk.Label(frame, text="고급 설정 (웬만하면 안 건드려도 됨)", font=("Malgun Gothic", 9)).grid(
            row=row, column=0, columnspan=3, sticky="w", **pad)
        row += 1
        row = self._add_path_row(frame, row, "카타고실행파일", "KataGo 실행 파일", browse="file")
        row = self._add_path_row(frame, row, "카타고모델", "KataGo 모델(.gz)", browse="file")
        row = self._add_path_row(frame, row, "카타고설정파일", "KataGo 분석 설정(.cfg)", browse="file")

        btns = tk.Frame(frame)
        btns.grid(row=row, column=0, columnspan=3, pady=(14, 4))
        tk.Button(btns, text="저장", width=14, command=self.save).pack(side="left", padx=4)
        self.run_btn = tk.Button(btns, text="저장 후 생성 실행", width=16, command=self.save_and_run)
        self.run_btn.pack(side="left", padx=4)
        tk.Button(btns, text="닫기", width=10, command=self.root.destroy).pack(side="left", padx=4)
        row += 1

        self.status_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.status_var, font=("Malgun Gothic", 9)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8)
        row += 1

        self.log_text = tk.Text(frame, width=70, height=10, state="disabled", wrap="word")
        self.log_text.grid(row=row, column=0, columnspan=3, padx=8, pady=(4, 0))

    def _add_entry_row(self, frame, row, key, label):
        tk.Label(frame, text=label, font=("Malgun Gothic", 10)).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        tk.Entry(frame, textvariable=self.vars[key], width=46).grid(row=row, column=1, columnspan=2, sticky="w", pady=4)
        return row + 1

    def _add_combo_row(self, frame, row, key, label, values):
        tk.Label(frame, text=label, font=("Malgun Gothic", 10)).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(frame, textvariable=self.vars[key], values=values, width=43, state="normal").grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4)
        return row + 1

    def _add_path_row(self, frame, row, key, label, browse):
        tk.Label(frame, text=label, font=("Malgun Gothic", 10)).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        tk.Entry(frame, textvariable=self.vars[key], width=36).grid(row=row, column=1, sticky="w", pady=4)

        def browse_file():
            path = filedialog.askopenfilename()
            if path:
                self.vars[key].set(path)

        def browse_dir():
            path = filedialog.askdirectory()
            if path:
                self.vars[key].set(path)

        def browse_any():
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="파일 선택", command=browse_file)
            menu.add_command(label="폴더 선택", command=browse_dir)
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

        action = {"file": browse_file, "dir": browse_dir, "any": browse_any}[browse]
        tk.Button(frame, text="찾기...", command=action).grid(row=row, column=2, sticky="w", padx=(4, 0), pady=4)
        return row + 1

    # ---------- 설정 불러오기/저장 ----------
    def _load(self):
        if not os.path.exists(self.config_path):
            for key, default in DEFAULTS.items():
                self.vars[key].set(default)
            self.status_var.set(f"설정 파일이 없어 기본값을 채웠습니다: {self.config_path}")
            return

        cfg = configparser.ConfigParser()
        cfg.read(self.config_path, encoding="utf-8")
        for key, default in DEFAULTS.items():
            self.vars[key].set(cfg.get("문제생성", key, fallback=default).strip())
        self.status_var.set(f"불러옴: {self.config_path}")

    def _collect(self):
        return {key: self.vars[key].get().strip() for key in FIELDS}

    def _validate(self, values):
        if not values["기보경로"]:
            messagebox.showerror("설정 오류", "'기보경로'를 입력해주세요.")
            return False
        if not os.path.exists(values["기보경로"]):
            messagebox.showerror("설정 오류", f"'기보경로'에 해당하는 경로가 없습니다:\n{values['기보경로']}")
            return False
        for key in ("문제개수", "분석강도"):
            if not values[key].isdigit():
                messagebox.showerror("설정 오류", f"'{key}'는 숫자여야 합니다: {values[key]!r}")
                return False
        try:
            float(values["난이도"])
        except ValueError:
            messagebox.showerror("설정 오류", f"'난이도'는 숫자여야 합니다 (승률차 %p, 예: 5): {values['난이도']!r}")
            return False
        for key in ("최소수순", "최대수순", "시드"):
            v = values[key]
            if v and not v.lstrip("-").isdigit():
                messagebox.showerror("설정 오류", f"'{key}'는 숫자이거나 빈칸이어야 합니다: {v!r}")
                return False
        if values["색"] not in COLOR_VALUES:
            messagebox.showerror("설정 오류", f"'색'은 전체/흑/백 중 하나여야 합니다: {values['색']!r}")
            return False
        if values["정답포함"] not in YESNO_VALUES:
            messagebox.showerror("설정 오류", f"'정답포함'은 예/아니오 중 하나여야 합니다: {values['정답포함']!r}")
            return False
        return True

    def save(self):
        values = self._collect()
        if not self._validate(values):
            return False
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE.format(**values))
        self.status_var.set(f"저장했습니다: {self.config_path}")
        return True

    # ---------- 생성 실행 ----------
    def save_and_run(self):
        if self.running:
            return
        if not self.save():
            return

        self.running = True
        self.run_btn.config(state="disabled", text="실행 중...")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()
        self.root.after(200, self._poll_log)

    def _run_worker(self):
        old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self.log_queue)
        try:
            args = make_quiz.load_config(self.config_path)
            gq.run(args)
        except SystemExit:
            pass
        except Exception as e:
            self.log_queue.put(f"\n오류 발생: {e}\n")
        finally:
            sys.stdout = old_stdout
            self.log_queue.put(None)

    def _poll_log(self):
        done = False
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item is None:
                    done = True
                    break
                self.log_text.config(state="normal")
                self.log_text.insert("end", item)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass

        if done:
            self.running = False
            self.run_btn.config(state="normal", text="저장 후 생성 실행")
            self.status_var.set("생성이 끝났습니다.")
        else:
            self.root.after(200, self._poll_log)
