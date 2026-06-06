# -*- coding: utf-8 -*-
"""
替身计时器 - Windows 悬浮窗版本
- 全局热键触发（不抢游戏焦点）
- 置顶透明背景悬浮窗
- 鼠标悬停显示关闭按钮
- 可自定义配置 config.json
"""

import tkinter as tk
import ctypes
from ctypes import wintypes
import threading
import sys
import json
import os

DEFAULT_CONFIG = {
    "hotkey": "F8",
    "quit_hotkey": "F12",
    "countdown": 14,
    "window_x": 100,
    "window_y": 100,
    "circle_size": 80,
    "font_size": 34
}

VK_MAP = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "SPACE": 0x20, "TAB": 0x09, "INSERT": 0x2D, "HOME": 0x24,
    "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "NUM0": 0x60, "NUM1": 0x61, "NUM2": 0x62, "NUM3": 0x63,
    "NUM4": 0x64, "NUM5": 0x65, "NUM6": 0x66, "NUM7": 0x67,
    "NUM8": 0x68, "NUM9": 0x69,
}

WM_HOTKEY = 0x0312
HOTKEY_TRIGGER = 1
HOTKEY_QUIT = 2

user32 = ctypes.windll.user32

# Win32 常量
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002


def get_config_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def load_config():
    path = get_config_path()
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
                config.update(user)
        except Exception:
            pass
    else:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
    return config


class TimerOverlay:
    def __init__(self, config):
        self.config = config
        self.total = config["countdown"]
        self.size = config["circle_size"]
        self.remaining = self.total
        self.counting = False
        self.hover = False

        self.root = tk.Tk()
        self.root.title("TimerOverlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # 用一个特定颜色作为透明色
        self.TRANSPARENT_COLOR = "#01FF01"
        self.root.config(bg=self.TRANSPARENT_COLOR)

        x = config["window_x"]
        y = config["window_y"]
        margin = 20  # 给关闭按钮留空间
        total_w = self.size + margin
        total_h = self.size + margin
        self.root.geometry(f"{total_w}x{total_h}+{x}+{y}")

        # 主画布
        self.canvas = tk.Canvas(
            self.root, width=total_w, height=total_h,
            bg=self.TRANSPARENT_COLOR, highlightthickness=0
        )
        self.canvas.pack()

        # 关闭按钮（右上角），默认隐藏
        self.close_btn = None

        # 鼠标事件
        self.canvas.bind("<Enter>", self.on_enter)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.do_move)

        self.draw(self.total, "#FF3333")

        # 设置窗口透明 + 不抢焦点
        self.root.after(50, self.setup_window)

        # 启动全局热键监听线程
        self.hotkey_thread = threading.Thread(target=self.hotkey_loop, daemon=True)
        self.hotkey_thread.start()

    def setup_window(self):
        self.root.update_idletasks()
        hwnd = user32.GetParent(self.root.winfo_id())
        if not hwnd:
            hwnd = self.root.winfo_id()
        self.hwnd = hwnd

        # 设置扩展样式
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = style | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # 把 TRANSPARENT_COLOR 设为透明色
        # RGB: #01FF01 -> 0x0001FF01 (COLORREF is BGR: 0x0001FF01)
        color_ref = 0x01 | (0xFF << 8) | (0x01 << 16)  # BGR format
        ctypes.windll.user32.SetLayeredWindowAttributes(
            hwnd, color_ref, 0, LWA_COLORKEY
        )

    def draw(self, number, color):
        self.canvas.delete("circle")
        self.canvas.delete("number")
        pad = 4
        ox = 0  # 圆形偏移
        oy = 10  # 给关闭按钮上方留点空间
        # 半透明深色底圆
        self.canvas.create_oval(
            ox + pad, oy + pad,
            ox + self.size - pad, oy + self.size - pad,
            fill="#1a1a1a", outline=color, width=3,
            tags="circle"
        )
        self.canvas.create_text(
            ox + self.size // 2, oy + self.size // 2,
            text=str(number), fill=color,
            font=("Consolas", self.config["font_size"], "bold"),
            tags="number"
        )

    def show_close_btn(self):
        if self.close_btn is None:
            self.close_btn = self.canvas.create_text(
                self.size - 2, 10,
                text="✕", fill="#FF4444",
                font=("Arial", 12, "bold"),
                tags="close_btn"
            )
            self.canvas.tag_bind("close_btn", "<Button-1>", self.on_close)

    def hide_close_btn(self):
        if self.close_btn is not None:
            self.canvas.delete("close_btn")
            self.close_btn = None

    def on_enter(self, event):
        self.hover = True
        self.show_close_btn()

    def on_leave(self, event):
        self.hover = False
        self.root.after(300, self._check_leave)

    def _check_leave(self):
        if not self.hover:
            self.hide_close_btn()

    def on_close(self, event):
        self.root.quit()
        self.root.destroy()
        os._exit(0)

    def on_click(self, event):
        self._mx = event.x
        self._my = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + event.x - self._mx
        y = self.root.winfo_y() + event.y - self._my
        self.root.geometry(f"+{x}+{y}")

    def color_for(self, sec):
        if sec > 10:
            return "#FF3333"
        elif sec > 5:
            return "#FF8800"
        else:
            return "#FFFF00"

    def trigger(self):
        self.root.after(0, self._start_countdown)

    def quit_app(self):
        self.root.after(0, self.on_close, None)

    def _start_countdown(self):
        self.remaining = self.total
        self.counting = True
        self._tick()

    def _tick(self):
        if not self.counting:
            return
        self.draw(self.remaining, self.color_for(self.remaining))
        if self.remaining <= 0:
            self.counting = False
            self.draw(self.total, "#FF3333")
            return
        self.remaining -= 1
        self.root.after(1000, self._tick)

    def hotkey_loop(self):
        vk_trigger = VK_MAP.get(self.config["hotkey"].upper(), 0x77)
        vk_quit = VK_MAP.get(self.config["quit_hotkey"].upper(), 0x7B)

        user32.RegisterHotKey(None, HOTKEY_TRIGGER, 0, vk_trigger)
        user32.RegisterHotKey(None, HOTKEY_QUIT, 0, vk_quit)

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_TRIGGER:
                    self.trigger()
                elif msg.wParam == HOTKEY_QUIT:
                    self.quit_app()

    def run(self):
        self.root.mainloop()


def main():
    config = load_config()
    app = TimerOverlay(config)
    app.run()


if __name__ == "__main__":
    main()
