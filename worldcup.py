# -*- coding: utf-8 -*-
"""
이상형 월드컵 (Ideal Type World Cup)

- 시작 화면에서 폴더 경로를 입력하면 그 폴더의 이미지들로 토너먼트를 진행한다.
- 두 장을 좌우에 놓고 비교, 좌/우 방향키로 선택 (왼쪽키=왼쪽 승, 오른쪽키=오른쪽 승).
- 선택한 이미지는 화면 중앙으로 꽉 차게 이동한 뒤 2초 홀드하고 다음 대결로 넘어간다.
- 탈락한 이미지는 탈락한 라운드 이름(512강/256강/.../4강/결승) 폴더로 정리된다.
- 대진은 매 라운드 무작위, 인원이 홀수면 한 명은 무작위로 부전승 진출.
"""

import os
import sys
import time
import random
import shutil
import threading
from collections import OrderedDict

import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk, ImageOps

EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
RESULT_DIR = "_결과"
WINNER_DIR = "우승"

HOLD_MS = 2000      # 선택한 이미지를 중앙에 띄우고 유지하는 시간
ANIM_MS = 380       # 중앙으로 이동하는 애니메이션 시간

BG = "#0f1116"
PANEL = "#171a22"
FG = "#f2f4f8"
SUB = "#8b93a7"
ACCENT = "#ffd23f"


def resource_path(name):
    """개발 실행/exe(onefile) 양쪽에서 동봉 리소스 경로를 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def round_label(n):
    """참가 인원 n명인 라운드의 이름. 2명이면 결승, 그 외엔 2의 거듭제곱으로 올림한 '<N>강'."""
    if n <= 2:
        return "결승"
    p = 2
    while p < n:
        p *= 2
    return "%d강" % p


def unique_path(dest_dir, name):
    base, ext = os.path.splitext(name)
    p = os.path.join(dest_dir, name)
    i = 1
    while os.path.exists(p):
        p = os.path.join(dest_dir, "%s_%d%s" % (base, i, ext))
        i += 1
    return p


def fit_rect(img_size, box):
    """box(x, y, w, h) 안에 비율 유지로 채워 넣은 사각형(x, y, w, h)을 돌려준다."""
    bx, by, bw, bh = box
    iw, ih = img_size
    if iw <= 0 or ih <= 0 or bw <= 0 or bh <= 0:
        return (bx, by, max(bw, 1), max(bh, 1))
    scale = min(bw / iw, bh / ih)
    scale = min(scale, 4.0)  # 너무 작은 이미지를 과하게 늘리지 않도록
    w = max(1, int(iw * scale))
    h = max(1, int(ih * scale))
    return (bx + (bw - w) // 2, by + (bh - h) // 2, w, h)


class ImageStore:
    """원본 로딩 결과를 캐시하고, 다음 대결 이미지를 백그라운드로 미리 읽어둔다."""

    def __init__(self, max_items=12):
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.max_items = max_items

    def get(self, path):
        with self.lock:
            if path in self.cache:
                self.cache.move_to_end(path)
                return self.cache[path]
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((2560, 1600), Image.LANCZOS)
        except Exception:
            img = Image.new("RGB", (800, 600), (40, 42, 50))
        with self.lock:
            self.cache[path] = img
            self.cache.move_to_end(path)
            while len(self.cache) > self.max_items:
                self.cache.popitem(last=False)
        return img

    def prefetch(self, paths):
        def work():
            for p in paths:
                try:
                    self.get(p)
                except Exception:
                    pass
        threading.Thread(target=work, daemon=True).start()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("이상형 월드컵")
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        self.configure(bg=BG)
        self.geometry("1280x820")
        self.minsize(900, 600)
        try:
            self.state("zoomed")
        except Exception:
            pass

        self.store = ImageStore()
        self.fullscreen = False
        self.busy = False
        self.hold_job = None
        self.stage = "start"
        self.errors = []
        self._refs = {}

        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.on_escape)
        self.bind("<Configure>", self.on_resize)

        self.build_start()

    # ------------------------------------------------------------------ 시작 화면
    def build_start(self):
        self.stage = "start"
        for w in self.winfo_children():
            w.destroy()

        f = tk.Frame(self, bg=BG)
        f.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(f, text="이상형 월드컵", bg=BG, fg=FG,
                 font=("Malgun Gothic", 34, "bold")).pack(pady=(0, 6))
        tk.Label(f, text="이미지가 들어있는 폴더 경로를 입력하세요", bg=BG, fg=SUB,
                 font=("Malgun Gothic", 12)).pack(pady=(0, 22))

        row = tk.Frame(f, bg=BG)
        row.pack()
        self.path_var = tk.StringVar()
        e = tk.Entry(row, textvariable=self.path_var, width=52, bg=PANEL, fg=FG,
                     insertbackground=FG, relief="flat", font=("Malgun Gothic", 12))
        e.pack(side="left", ipady=8, ipadx=8)
        e.focus_set()
        e.bind("<Return>", lambda ev: self.on_start())
        tk.Button(row, text="찾아보기", command=self.browse, bg=PANEL, fg=FG,
                  activebackground="#232735", activeforeground=FG, relief="flat",
                  font=("Malgun Gothic", 11), padx=16, pady=7).pack(side="left", padx=(10, 0))

        opt = tk.Frame(f, bg=BG)
        opt.pack(pady=(20, 0))

        self.mode_var = tk.StringVar(value="copy")
        tk.Label(opt, text="탈락 이미지 처리", bg=BG, fg=SUB,
                 font=("Malgun Gothic", 11)).grid(row=0, column=0, sticky="w", padx=(0, 14))
        for i, (txt, val) in enumerate((("복사 (원본 유지)", "copy"), ("이동 (원본에서 빼냄)", "move"))):
            tk.Radiobutton(opt, text=txt, variable=self.mode_var, value=val, bg=BG, fg=FG,
                           selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                           font=("Malgun Gothic", 11)).grid(row=0, column=1 + i, sticky="w")

        self.recursive_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="하위 폴더까지 포함", variable=self.recursive_var, bg=BG, fg=FG,
                       selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       font=("Malgun Gothic", 11)).grid(row=1, column=0, columnspan=3,
                                                        sticky="w", pady=(10, 0))

        tk.Button(f, text="시작하기", command=self.on_start, bg=ACCENT, fg="#1a1a1a",
                  activebackground="#ffe375", relief="flat", font=("Malgun Gothic", 14, "bold"),
                  padx=40, pady=11).pack(pady=(26, 0))

        tk.Label(f, text="선택: ← 왼쪽 이미지 / → 오른쪽 이미지  ·  F11 전체화면  ·  ESC 종료",
                 bg=BG, fg=SUB, font=("Malgun Gothic", 10)).pack(pady=(24, 0))

    def browse(self):
        d = filedialog.askdirectory(title="이미지 폴더 선택")
        if d:
            self.path_var.set(os.path.normpath(d))

    def collect_images(self, root, recursive):
        result_root = os.path.join(root, RESULT_DIR)
        files = []
        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                if os.path.normcase(dirpath).startswith(os.path.normcase(result_root)):
                    dirnames[:] = []
                    continue
                for fn in filenames:
                    if os.path.splitext(fn)[1].lower() in EXTS:
                        files.append(os.path.join(dirpath, fn))
        else:
            for fn in os.listdir(root):
                p = os.path.join(root, fn)
                if os.path.isfile(p) and os.path.splitext(fn)[1].lower() in EXTS:
                    files.append(p)
        return sorted(files)

    def on_start(self):
        root = self.path_var.get().strip().strip('"')
        if not root:
            messagebox.showwarning("이상형 월드컵", "폴더 경로를 입력해 주세요.")
            return
        root = os.path.normpath(os.path.expanduser(root))
        if not os.path.isdir(root):
            messagebox.showerror("이상형 월드컵", "폴더를 찾을 수 없습니다.\n%s" % root)
            return

        images = self.collect_images(root, self.recursive_var.get())
        if len(images) < 2:
            messagebox.showerror("이상형 월드컵",
                                 "이미지가 %d개뿐입니다. 최소 2개가 필요합니다." % len(images))
            return

        self.root_dir = root
        self.mode = self.mode_var.get()
        self.errors = []
        self.participants = images[:]
        random.shuffle(self.participants)
        self.build_game()
        self.start_round()

    # ------------------------------------------------------------------ 게임 화면
    def build_game(self):
        self.stage = "game"
        for w in self.winfo_children():
            w.destroy()
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.bind("<Left>", lambda ev: self.choose("left"))
        self.bind("<Right>", lambda ev: self.choose("right"))
        self.bind("<space>", lambda ev: self.skip_hold())
        self.bind("<Return>", lambda ev: self.skip_hold())
        self.update_idletasks()

    def start_round(self):
        n = len(self.participants)
        if n <= 1:
            self.finish()
            return

        self.label = round_label(n)
        random.shuffle(self.participants)
        lst = self.participants[:]

        self.bye = None
        if len(lst) % 2 == 1:
            self.bye = lst.pop(random.randrange(len(lst)))

        self.queue = [(lst[i], lst[i + 1]) for i in range(0, len(lst), 2)]
        self.winners = [] if self.bye is None else [self.bye]
        self.match_idx = 0
        self.match_total = len(self.queue)
        self.next_match()

    def next_match(self):
        if self.match_idx >= len(self.queue):
            self.participants = self.winners
            self.start_round()
            return

        self.left_path, self.right_path = self.queue[self.match_idx]
        self.match_idx += 1
        self.busy = False
        self.subtext = "%d / %d 경기%s" % (
            self.match_idx, self.match_total,
            ("  ·  부전승 1장 자동 진출" if self.bye else ""))
        self.draw_match()

        if self.match_idx < len(self.queue):
            self.store.prefetch(list(self.queue[self.match_idx]))

    # ------------------------------------------------------------------ 그리기
    def layout(self):
        W = max(self.canvas.winfo_width(), 400)
        H = max(self.canvas.winfo_height(), 300)
        top, bottom, gap, side = 104, 56, 20, 26
        mid = W // 2
        ph = H - top - bottom
        left = (side, top, mid - gap - side, ph)
        right = (mid + gap, top, W - side - (mid + gap), ph)
        full = (20, 86, W - 40, H - 86 - 26)
        return W, H, left, right, full

    def draw_header(self, W, sub=None):
        self.canvas.create_text(W // 2, 40, text=self.label, fill=ACCENT,
                                font=("Malgun Gothic", 30, "bold"), tags="hdr")
        self.canvas.create_text(W // 2, 72, text=sub if sub is not None else self.subtext,
                                fill=SUB, font=("Malgun Gothic", 12), tags="hdr")

    def place_image(self, path, box, tag, border=True):
        img = self.store.get(path)
        x, y, w, h = fit_rect(img.size, box)
        photo = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        self._refs[tag] = photo
        if border:
            self.canvas.create_rectangle(x - 4, y - 4, x + w + 4, y + h + 4,
                                         outline="#2a2f3d", width=2, tags=tag)
        self.canvas.create_image(x, y, image=photo, anchor="nw", tags=tag)
        return (x, y, w, h)

    def draw_match(self):
        self.canvas.delete("all")
        self._refs.clear()
        W, H, lbox, rbox, _ = self.layout()
        self.draw_header(W)
        self.left_rect = self.place_image(self.left_path, lbox, "left")
        self.right_rect = self.place_image(self.right_path, rbox, "right")
        self.canvas.create_text(W // 2, H - 26, text="←  방향키로 선택  →",
                                fill=SUB, font=("Malgun Gothic", 12), tags="hint")

    def on_resize(self, ev):
        if self.stage == "game" and not self.busy and getattr(self, "left_path", None):
            self.draw_match()

    def on_click(self, ev):
        if self.busy:
            self.skip_hold()
            return
        W = self.canvas.winfo_width()
        self.choose("left" if ev.x < W // 2 else "right")

    # ------------------------------------------------------------------ 선택 처리
    def choose(self, side):
        if self.stage != "game" or self.busy:
            return
        self.busy = True
        if side == "left":
            winner, loser, wrect = self.left_path, self.right_path, self.left_rect
        else:
            winner, loser, wrect = self.right_path, self.left_path, self.right_rect
        # 승자 원본 아이템까지 지운다. 남겨두면 확대되는 이미지와 겹쳐 복제된 것처럼 보인다.
        self.canvas.delete("left")
        self.canvas.delete("right")
        self.canvas.delete("hint")
        self._refs.pop("left", None)
        self._refs.pop("right", None)

        self.winners.append(winner)
        self.eliminate(loser, self.label)
        self.animate_to_center(winner, wrect)

    def eliminate(self, path, label):
        dest_dir = os.path.join(self.root_dir, RESULT_DIR, label)
        self.move_or_copy(path, dest_dir)

    def move_or_copy(self, path, dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest = unique_path(dest_dir, os.path.basename(path))
            if self.mode == "move":
                shutil.move(path, dest)
            else:
                shutil.copy2(path, dest)
        except Exception as e:
            self.errors.append("%s → %s" % (os.path.basename(path), e))

    def animate_to_center(self, winner, r0):
        W, H, _, _, full = self.layout()
        img = self.store.get(winner)
        r1 = fit_rect(img.size, full)
        base = img.resize((max(r1[2], 1), max(r1[3], 1)), Image.LANCZOS)
        name = os.path.basename(winner)
        start = time.perf_counter()

        def step():
            t = min(1.0, (time.perf_counter() - start) / (ANIM_MS / 1000.0))
            e = 1 - (1 - t) ** 3
            x = r0[0] + (r1[0] - r0[0]) * e
            y = r0[1] + (r1[1] - r0[1]) * e
            w = max(1, int(r0[2] + (r1[2] - r0[2]) * e))
            h = max(1, int(r0[3] + (r1[3] - r0[3]) * e))
            self.canvas.delete("win")
            photo = ImageTk.PhotoImage(base.resize((w, h), Image.BILINEAR))
            self._refs["win"] = photo
            self.canvas.create_image(int(x), int(y), image=photo, anchor="nw", tags="win")
            if t < 1.0:
                self.after(16, step)
            else:
                self.canvas.delete("win")
                photo2 = ImageTk.PhotoImage(base)
                self._refs["win"] = photo2
                self.canvas.create_rectangle(r1[0] - 4, r1[1] - 4, r1[0] + r1[2] + 4,
                                             r1[1] + r1[3] + 4, outline=ACCENT, width=3,
                                             tags="win")
                self.canvas.create_image(r1[0], r1[1], image=photo2, anchor="nw", tags="win")
                self.canvas.delete("hdr")
                self.draw_header(W, sub="✓  %s" % name)
                self.hold_job = self.after(HOLD_MS, self.after_hold)

        step()

    def after_hold(self):
        self.hold_job = None
        self.next_match()

    def skip_hold(self):
        if self.hold_job is not None:
            self.after_cancel(self.hold_job)
            self.after_hold()

    # ------------------------------------------------------------------ 결과
    def finish(self):
        self.stage = "done"
        winner = self.participants[0]
        self.move_or_copy(winner, os.path.join(self.root_dir, RESULT_DIR, WINNER_DIR))

        self.canvas.delete("all")
        self._refs.clear()
        W = max(self.canvas.winfo_width(), 400)
        H = max(self.canvas.winfo_height(), 300)
        self.canvas.create_text(W // 2, 44, text="🏆  우승", fill=ACCENT,
                                font=("Malgun Gothic", 30, "bold"))
        self.canvas.create_text(W // 2, 78, text=os.path.basename(winner), fill=FG,
                                font=("Malgun Gothic", 13))
        box = (30, 104, W - 60, H - 104 - 88)
        self.place_image(winner, box, "champ", border=True)
        self.canvas.create_text(W // 2, H - 62,
                                text="결과 폴더: %s" % os.path.join(self.root_dir, RESULT_DIR),
                                fill=SUB, font=("Malgun Gothic", 11))

        bar = tk.Frame(self, bg=BG)
        bar.place(relx=0.5, rely=1.0, y=-34, anchor="center")
        tk.Button(bar, text="결과 폴더 열기", command=self.open_result, bg=PANEL, fg=FG,
                  relief="flat", font=("Malgun Gothic", 11), padx=18, pady=6).pack(side="left", padx=6)
        tk.Button(bar, text="처음으로", command=self.build_start, bg=PANEL, fg=FG,
                  relief="flat", font=("Malgun Gothic", 11), padx=18, pady=6).pack(side="left", padx=6)
        tk.Button(bar, text="종료", command=self.destroy, bg=PANEL, fg=FG,
                  relief="flat", font=("Malgun Gothic", 11), padx=18, pady=6).pack(side="left", padx=6)

        if self.errors:
            messagebox.showwarning("이상형 월드컵",
                                   "일부 파일 정리에 실패했습니다:\n\n" + "\n".join(self.errors[:10]))

    def open_result(self):
        d = os.path.join(self.root_dir, RESULT_DIR)
        if os.path.isdir(d):
            os.startfile(d)

    # ------------------------------------------------------------------ 기타
    def toggle_fullscreen(self, ev=None):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)

    def on_escape(self, ev=None):
        if self.fullscreen:
            self.toggle_fullscreen()
            return
        if self.stage == "game":
            if not messagebox.askyesno("이상형 월드컵", "진행 중인 월드컵을 종료할까요?"):
                return
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
