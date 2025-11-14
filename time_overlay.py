import tkinter as tk
from datetime import datetime, timedelta  # timedelta для корректного переноса минут/часов/дней
import ctypes
import os
import configparser

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

CONFIG_FILE = "config.ini"


class ClockOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.outer_width = 66
        self.outer_height = 24
        self.border_width = 2

        # Цвета по вашим предпочтениям
        self.default_bg = "#f9c289"
        self.default_inner = "#fcd5ac"
        self.default_fg = "#85674e"
        self.bg_color = self.default_bg
        self.inner_color = self.default_inner
        self.fg_color = self.default_fg

        self.canvas = tk.Canvas(
            self.root,
            width=self.outer_width,
            height=self.outer_height,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.canvas.pack()

        self.rect_id = self.canvas.create_rectangle(
            self.border_width, self.border_width,
            self.outer_width - self.border_width,
            self.outer_height - self.border_width,
            fill=self.inner_color,
            outline=""
        )

        sans_fonts = ['Segoe UI', 'Helvetica', 'Arial', 'DejaVu Sans', 'Noto Sans']
        self.font_name = 'TkDefaultFont'
        for name in sans_fonts:
            try:
                test = tk.font.Font(family=name, size=8)
                if name.lower() in test.actual()['family'].lower():
                    self.font_name = name
                    break
            except:
                pass

        self.text_id = self.canvas.create_text(
            self.outer_width // 2,
            self.outer_height // 2,
            text="00:00",
            font=(self.font_name, 11, "normal"),  # non-bold
            fill=self.fg_color,
            anchor="center"
        )

        # ——— Context menu —————————————————————————————————————————————————————
        self.context_menu = tk.Menu(self.root, tearoff=0)

        # Font size: 20 (top) → 10 (bottom), with checkmark
        self.font_size = 11
        self.font_menu = tk.Menu(self.context_menu, tearoff=0)
        for size in reversed(range(10, 21)):
            label = f"{'✓ ' if size == self.font_size else '  '}{size}"
            self.font_menu.add_command(
                label=label,
                command=lambda s=size: self.set_font_size(s)
            )
        self.context_menu.add_cascade(label="Font size", menu=self.font_menu)

        # Alpha: 100% (top) → 0% (bottom), with checkmark
        self.alpha_percent = 100
        self.alpha_menu = tk.Menu(self.context_menu, tearoff=0)
        for alpha in reversed(range(0, 101, 5)):
            label = f"{'✓ ' if alpha == self.alpha_percent else '  '}{alpha}%"
            self.alpha_menu.add_command(
                label=label,
                command=lambda a=alpha: self.set_alpha(a)
            )
        self.context_menu.add_cascade(label="Alpha", menu=self.alpha_menu)

        # Lock / Unlock
        self.locked = False
        self.lock_menu = tk.Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label="Lock / Unlock", menu=self.lock_menu)
        self.update_lock_menu()

        # ✅ About + separator + Exit
        self.context_menu.add_separator()
        self.context_menu.add_command(label="About", command=self.show_about)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exit", command=self.exit_app)

        # Bindings
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_move_release)

        self.update_job = None
        self.dragging = False

        self.load_config()
        self.update_time()
        self.root.mainloop()

    # ——— Context menu —————————————————————————————————————————————————————
    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # ——— Lock / Unlock ————————————————————————————————————————————————
    def toggle_lock(self):
        self.locked = not self.locked
        self.update_lock_menu()
        self.save_lock_state()

    def update_lock_menu(self):
        self.lock_menu.delete(0, "end")
        if self.locked:
            self.lock_menu.add_command(label="✓ Lock", command=self.toggle_lock)
            self.lock_menu.add_command(label="  Unlock", command=self.toggle_lock)
        else:
            self.lock_menu.add_command(label="  Lock", command=self.toggle_lock)
            self.lock_menu.add_command(label="✓ Unlock", command=self.toggle_lock)

    def save_lock_state(self):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["locked"] = str(int(self.locked))
        self._write_config(config)

    # ——— Movement & auto-save —————————————————————————————————————————————
    def start_move(self, event):
        if self.locked:
            return
        self.dragging = True
        self.start_x = event.x
        self.start_y = event.y

    def do_move(self, event):
        if not self.dragging or self.locked:
            return
        x = self.root.winfo_x() + (event.x - self.start_x)
        y = self.root.winfo_y() + (event.y - self.start_y)
        self.set_position(x, y)

    def on_move_release(self, event=None):
        if self.dragging:
            self.dragging = False
            self.save_position()

    def set_position(self, x, y):
        self.root.geometry(f"+{int(x)}+{int(y)}")

    # ——— Config I/O ———————————————————————————————————————————————————————
    def _read_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            try:
                config.read(CONFIG_FILE, encoding="utf-8")
            except Exception as e:
                print(f"⚠️ Config read error: {e}")
        return config

    def _write_config(self, config):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            print(f"⚠️ Config write error: {e}")

    def save_position(self):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["x"] = str(x)
        config["window"]["y"] = str(y)
        self._write_config(config)

    def _save_colors(self):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["bg_color"] = self.bg_color
        config["window"]["inner_color"] = self.inner_color
        config["window"]["fg_color"] = self.fg_color
        self._write_config(config)

    def _save_alpha(self, alpha_percent):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["alpha"] = str(alpha_percent)
        self._write_config(config)

    def _save_font_size_only(self, size):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["font_size"] = str(size)
        self._write_config(config)

    def load_config(self):
        config = self._read_config()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # ✅ Position: 42px from right, 260px from bottom
        x = screen_width - self.outer_width - 42
        y = screen_height - self.outer_height - 260

        font_size = 11
        alpha_percent = 100
        bg_color = self.default_bg
        inner_color = self.default_inner
        fg_color = self.default_fg
        locked = False

        if "window" in config:
            x = config.getint("window", "x", fallback=x)
            y = config.getint("window", "y", fallback=y)
            font_size = max(10, min(20, config.getint("window", "font_size", fallback=font_size)))
            alpha_percent = max(0, min(100, config.getint("window", "alpha", fallback=alpha_percent)))
            bg_color = config.get("window", "bg_color", fallback=bg_color)
            inner_color = config.get("window", "inner_color", fallback=inner_color)
            fg_color = config.get("window", "fg_color", fallback=fg_color)
            locked = bool(int(config.get("window", "locked", fallback="0")))

        # Apply
        self.bg_color = bg_color
        self.inner_color = inner_color
        self.fg_color = fg_color
        self.locked = locked
        self.font_size = font_size
        self.alpha_percent = alpha_percent

        self.canvas.config(bg=self.bg_color)
        self.canvas.itemconfig(self.rect_id, fill=self.inner_color)
        self.canvas.itemconfig(self.text_id, fill=self.fg_color)
        self.set_position(x, y)
        self.set_font_size(font_size)
        self.set_alpha(alpha_percent, save=False)
        self.update_font_menu()
        self.update_alpha_menu()
        self.update_lock_menu()

        # Save full state on first launch
        self._save_colors()
        self._save_font_size_only(font_size)
        self._save_alpha(alpha_percent)
        self.save_position()
        self.save_lock_state()

    # ——— Font & Alpha ————————————————————————————————————————————————
    def set_font_size(self, size):
        self.font_size = size
        self.canvas.itemconfig(self.text_id, font=(self.font_name, size, "normal"))
        self._save_font_size_only(size)
        self.update_font_menu()

    def set_alpha(self, alpha_percent, save=True):
        alpha = max(0, min(100, alpha_percent)) / 100.0
        self.root.attributes("-alpha", alpha)
        self.alpha_percent = alpha_percent
        if save:
            self._save_alpha(alpha_percent)
        self.update_alpha_menu()

    def update_font_menu(self):
        self.font_menu.delete(0, "end")
        for size in reversed(range(10, 21)):
            label = f"{'✓ ' if size == self.font_size else '  '}{size}"
            self.font_menu.add_command(
                label=label,
                command=lambda s=size: self.set_font_size(s)
            )

    def update_alpha_menu(self):
        self.alpha_menu.delete(0, "end")
        for alpha in reversed(range(0, 101, 5)):
            label = f"{'✓ ' if alpha == self.alpha_percent else '  '}{alpha}%"
            self.alpha_menu.add_command(
                label=label,
                command=lambda a=alpha: self.set_alpha(a)
            )

    # ——— About window —————————————————————————————————————————————————————
    def show_about(self):
        about = tk.Toplevel(self.root)
        about.overrideredirect(True)
        about.attributes("-topmost", True)
        about.configure(bg=self.bg_color)

        frame = tk.Frame(about, bg=self.inner_color, padx=10, pady=6)
        frame.pack()

        title_label = tk.Label(
            frame,
            text="Local Timer for Albion Online",
            font=(self.font_name, 14, "normal"),  # ✅ font size 14, non-bold
            fg=self.fg_color,
            bg=self.inner_color
        )
        title_label.pack()

        # ✅ Horizontal line after title
        separator = tk.Frame(frame, height=1, bg=self.fg_color)
        separator.pack(fill="x", pady=(2, 4))

        # ✅ Ver. 1.25 before ©2025 Free
        credit_label = tk.Label(
            frame,
            text="By TeslaWizard (Europe)\nVer. 1.25\n©2025 Free",
            font=(self.font_name, 14, "normal"),
            fg=self.fg_color,
            bg=self.inner_color,
            justify="center"
        )
        credit_label.pack()

        # ✅ Anchored to bottom-right corner of timer
        about.update_idletasks()
        w = about.winfo_reqwidth()
        h = about.winfo_reqheight()
        timer_x = self.root.winfo_x()
        timer_y = self.root.winfo_y()
        timer_w = self.outer_width
        timer_h = self.outer_height
        about_x = timer_x + timer_w - w
        about_y = timer_y + timer_h - h
        about.geometry(f"{w}x{h}+{about_x}+{about_y}")

        def close_about(event=None):
            about.destroy()

        about.bind("<Button-1>", close_about)
        about.bind("<Escape>", close_about)

    # ——— Exit (robust) ———————————————————————————————————————————————————
    def exit_app(self):
        if self.update_job:
            try:
                self.root.after_cancel(self.update_job)
            except Exception:
                pass
        self.root.quit()
        self.root.after(50, self.root.destroy)

    # ——— Time update —————————————————————————————————————————————————————
    def update_time(self):
        now = datetime.now()
        display_time = now.strftime("%H:%M")
        self.canvas.itemconfig(self.text_id, text=display_time)

        # ✅ FIXED: robust next-minute calculation (23:59→00:00 safe!)
        next_min = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        delay_ms = int((next_min - now).total_seconds() * 1000)
        delay_ms = max(50, min(60_000, delay_ms))

        if self.update_job:
            try:
                self.root.after_cancel(self.update_job)
            except Exception:
                pass
        self.update_job = self.root.after(delay_ms, self.update_time)


if __name__ == "__main__":
    ClockOverlay()
