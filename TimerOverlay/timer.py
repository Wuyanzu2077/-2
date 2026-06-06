# -*- coding: utf-8 -*-
"""
替身计时器 - Windows 悬浮窗版本
- 全局热键触发（不抢游戏焦点）
- 置顶半透明圆形悬浮窗
- 可自定义触发键、倒计时秒数
"""

import tkinter as tk
import ctypes
from ctypes import wintypes
import threading
import sys
import json
import os

# ============ 可自定义配置 ============
# 配置文件会自动生成在 exe 同目录下的 config.json
# 你可以编辑那个文件来改键位和秒数，不用重新编译

DEFAULT_CONFIG = {
    "hotkey": "F8",          # 触发键，支持 F1-F12、字母、数字
    "countdown": 14,         # 倒计时秒数
    "window_x": 100,         # 悬浮窗初始 X 坐标
    "window_y": 100,         # 悬浮窗初始 Y 坐标
    "circle_size": 80,       # 圆圈大小（像素）
    "font_size": 34          # 数字字体大小
}

# 虚拟键码映射表
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
HOTKEY_ID = 1


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

        self.root = tk.Tk()
        self.root.title("TimerOverlay")
        self.root.overrideredirect(True)          # 无边框
        self.root.attributes("-topmost", True)     # 置顶
        self.root.attributes("-transparentcolor", "#010101")  # 把这个颜色变透明

        x = config["window_x"]
        y = config["window_y"]
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.root.config(bg="#010101")

        self.canvas = tk.Canvas(
            self.root, width=self.size, height=self.size,
            bg="#010101", highlightthickness=0
        )
        self.canvas.pack()

        # 允许鼠标拖动悬浮窗
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)

        self.draw(self.total, "#FF3333")

        # 设置窗口不抢焦点
        self.root.after(50, self.set_no_activate)

        # 启动全局热键监听线程
        self.hotkey_thread = threading.Thread(target=self.hotkey_loop, daemon=True)
        self.hotkey_thread.start()

    def set_no_activate(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def draw(self, number, color):
        self.canvas.delete("all")
        pad = 4
        # 半透明深色底圆（用接近透明色描边模拟）
        self.canvas.create_oval(
            pad, pad, self.size - pad, self.size - pad,
            fill="#1a1a1a", outline=color, width=3
        )
        self.canvas.create_text(
            self.size // 2, self.size // 2,
            text=str(number), fill=color,
            font=("Consolas", self.config["font_size"], "bold")
        )

    def start_move(self, event):
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
        # 由热键线程调用，切回主线程执行
        self.root.after(0, self._start_countdown)

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
            self.draw(self.total, "#FF3333")  # 恢复待机
            return
        self.remaining -= 1
        self.root.after(1000, self._tick)

    def hotkey_loop(self):
        user32 = ctypes.windll.user32
        vk = VK_MAP.get(self.config["hotkey"].upper(), 0x77)  # 默认 F8
        # 无修饰键注册全局热键
        if not user32.RegisterHotKey(None, HOTKEY_ID, 0, vk):
            return
        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.trigger()

    def run(self):
        self.root.mainloop()


def main():
    config = load_config()
    app = TimerOverlay(config)
    app.run()


if __name__ == "__main__":
    main()
