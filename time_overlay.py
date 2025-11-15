import tkinter as tk
from datetime import datetime, timedelta  # ✅ fix 23:59→00:00
import ctypes
import os
import configparser
import keyboard  # ✅ for global hotkey
import threading
import winsound  # ✅ for sound

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

CONFIG_FILE = "config.ini"
VERSION = "1.27"  # ✅ version as constant

# ✅ System alarm sound
sound_path = os.path.join(os.environ['WINDIR'], 'Media', 'Alarm03.wav')


class ClockOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.outer_width = 66
        self.outer_height = 24
        self.border_width = 2

        # ✅ Updated colors per request
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
            font=(self.font_name, 11, "normal"),
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

        # ✅ Alarm menu item
        self.context_menu.add_command(label="Alarm…", command=self.show_alarm_dialog)

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
        self.visible = True

        # ✅ Alarm state
        self.alarm_enabled = False
        self.alarm_hour = 12
        self.alarm_minute = 0
        self.alarm_message = "Time to take a break!"

        # ✅ Hotkey (load before setup)
        self.hotkey = "F12"
        self.load_config()
        self.setup_global_hotkey()

        self.update_time()
        self.root.mainloop()

    # ——— F12: Show/Hide (global) —————————————————————————————————————————————
    def toggle_visibility(self):
        self.visible = not self.visible
        if self.visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        else:
            self.root.withdraw()

    def setup_global_hotkey(self):
        try:
            keyboard.remove_hotkey(self.hotkey)
        except:
            pass

        def hotkey_thread():
            try:
                keyboard.add_hotkey(self.hotkey, self.toggle_visibility)
                keyboard.wait()
            except Exception as e:
                print(f"⚠️ Keyboard hook failed (run as Admin?): {e}")

        t = threading.Thread(target=hotkey_thread, daemon=True)
        t.start()

    # ——— Alarm dialog —————————————————————————————————————————————————————
    def show_alarm_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Alarm")
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.configure(bg=self.inner_color)

        # Hour selector
        tk.Label(dialog, text="Time:", bg=self.inner_color, fg=self.fg_color).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        hour_var = tk.StringVar(value=f"{self.alarm_hour:02d}")
        hour_spin = tk.Spinbox(
            dialog, from_=0, to=23, wrap=True, textvariable=hour_var,
            width=3, format="%02.0f", font=(self.font_name, 10)
        )
        hour_spin.grid(row=0, column=1, padx=(0, 2), pady=5, sticky="w")

        # Separator
        tk.Label(dialog, text=":", bg=self.inner_color, fg=self.fg_color, font=(self.font_name, 12)).grid(row=0, column=2, pady=5)

        # Minute selector
        minute_var = tk.StringVar(value=f"{self.alarm_minute:02d}")
        minute_spin = tk.Spinbox(
            dialog, from_=0, to=59, wrap=True, textvariable=minute_var,
            width=3, format="%02.0f", font=(self.font_name, 10)
        )
        minute_spin.grid(row=0, column=3, padx=(2, 10), pady=5, sticky="w")

        # Message
        tk.Label(dialog, text="Message:", bg=self.inner_color, fg=self.fg_color).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        msg_var = tk.StringVar(value=self.alarm_message)
        msg_entry = tk.Entry(dialog, width=30, textvariable=msg_var)
        msg_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5)

        # Enabled checkbox
        enabled_var = tk.BooleanVar(value=self.alarm_enabled)
        enabled_cb = tk.Checkbutton(
            dialog, text="Enable alarm",
            variable=enabled_var,
            bg=self.inner_color,
            fg=self.fg_color,
            selectcolor=self.bg_color,
            activebackground=self.inner_color
        )
        enabled_cb.grid(row=2, column=0, columnspan=4, pady=5)

        def save_and_close():
            try:
                h = int(hour_var.get())
                m = int(minute_var.get())
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except ValueError:
                tk.messagebox.showerror("Error", "Hour: 00–23, Minute: 00–59", parent=dialog)
                return
            msg = msg_var.get().strip() or "Alarm!"
            self.alarm_enabled = enabled_var.get()
            self.alarm_hour = h
            self.alarm_minute = m
            self.alarm_message = msg
            self.save_alarm_config()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg=self.inner_color)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)
        tk.Button(btn_frame, text="OK", command=save_and_close, width=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=cancel, width=8).pack(side="left", padx=5)

        # ✅ Center dialog on screen
        dialog.update_idletasks()
        dw = dialog.winfo_reqwidth()
        dh = dialog.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        dx = (sw - dw) // 2
        dy = (sh - dh) // 2
        dialog.geometry(f"+{dx}+{dy}")

        hour_spin.focus_set()
        dialog.bind("<Return>", lambda e: save_and_close())
        dialog.bind("<Escape>", lambda e: cancel())

    def save_alarm_config(self):
        config = self._read_config()
        if "alarm" not in config:
            config["alarm"] = {}
        config["alarm"]["enabled"] = str(int(self.alarm_enabled))
        config["alarm"]["hour"] = str(self.alarm_hour)
        config["alarm"]["minute"] = str(self.alarm_minute)
        config["alarm"]["message"] = self.alarm_message
        self._write_config(config)

    # ——— Alarm trigger —————————————————————————————————————————————————————
    def trigger_alarm(self):
        # ✅ Play system sound Alarm03.wav, fallback to Beep
        if os.path.isfile(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        else:
            winsound.Beep(1000, 300)  # fallback

        # Notification window
        alert = tk.Toplevel(self.root)
        alert.overrideredirect(True)
        alert.attributes("-topmost", True)
        alert.attributes("-alpha", 0.95)
        alert.configure(bg=self.bg_color)

        frame = tk.Frame(alert, bg=self.inner_color, padx=12, pady=8)
        frame.pack()

        tk.Label(frame, text="⏰ Alarm!", font=(self.font_name, 14, "normal"), fg=self.fg_color, bg=self.inner_color).pack()
        tk.Frame(frame, height=1, bg=self.fg_color).pack(fill="x", pady=(4, 6))
        tk.Label(frame, text=self.alarm_message, font=(self.font_name, 12, "normal"), fg=self.fg_color, bg=self.inner_color,
                 wraplength=250, justify="center").pack(pady=(0, 8))
        ok_btn = tk.Button(frame, text="OK", command=alert.destroy, font=(self.font_name, 10),
                           bg=self.fg_color, fg=self.inner_color, relief="flat", padx=12, pady=4)
        ok_btn.pack()

        # ✅ Auto height + anchor to bottom-right of clock (like About)
        alert.update_idletasks()
        w = alert.winfo_reqwidth()
        h = alert.winfo_reqheight()
        timer_x = self.root.winfo_x()
        timer_y = self.root.winfo_y()
        timer_w = self.outer_width
        timer_h = self.outer_height
        alert_x = timer_x + timer_w - w
        alert_y = timer_y + timer_h - h
        alert.geometry(f"{w}x{h}+{alert_x}+{alert_y}")

        alert.bind("<Button-1>", lambda e: alert.destroy())
        alert.bind("<Escape>", lambda e: alert.destroy())

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
        config["window"]["hotkey"] = self.hotkey
        self._write_config(config)

    def _save_colors(self):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["bg_color"] = self.bg_color
        config["window"]["inner_color"] = self.inner_color
        config["window"]["fg_color"] = self.fg_color
        config["window"]["hotkey"] = self.hotkey
        self._write_config(config)

    def _save_alpha(self, alpha_percent):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["alpha"] = str(alpha_percent)
        config["window"]["hotkey"] = self.hotkey
        self._write_config(config)

    def _save_font_size_only(self, size):
        config = self._read_config()
        if "window" not in config:
            config["window"] = {}
        config["window"]["font_size"] = str(size)
        config["window"]["hotkey"] = self.hotkey
        self._write_config(config)

    def load_config(self):
        config = self._read_config()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - self.outer_width - 42
        y = screen_height - self.outer_height - 260

        font_size = 11
        alpha_percent = 100
        bg_color = self.default_bg
        inner_color = self.default_inner
        fg_color = self.default_fg
        locked = False
        hotkey = "F12"

        # ✅ Load alarm defaults
        alarm_enabled = False
        alarm_hour = 12
        alarm_minute = 0
        alarm_msg = "Time to take a break!"

        if "window" in config:
            x = config.getint("window", "x", fallback=x)
            y = config.getint("window", "y", fallback=y)
            font_size = max(10, min(20, config.getint("window", "font_size", fallback=font_size)))
            alpha_percent = max(0, min(100, config.getint("window", "alpha", fallback=alpha_percent)))
            bg_color = config.get("window", "bg_color", fallback=bg_color)
            inner_color = config.get("window", "inner_color", fallback=inner_color)
            fg_color = config.get("window", "fg_color", fallback=fg_color)
            locked = bool(int(config.get("window", "locked", fallback="0")))
            hotkey = config.get("window", "hotkey", fallback="F12").strip()

        if "alarm" in config:
            alarm_enabled = bool(int(config.get("alarm", "enabled", fallback="0")))
            alarm_hour = config.getint("alarm", "hour", fallback=12)
            alarm_minute = config.getint("alarm", "minute", fallback=0)
            alarm_msg = config.get("alarm", "message", fallback="Time to take a break!").strip()

        # Apply
        self.bg_color = bg_color
        self.inner_color = inner_color
        self.fg_color = fg_color
        self.locked = locked
        self.font_size = font_size
        self.alpha_percent = alpha_percent
        self.hotkey = hotkey
        self.alarm_enabled = alarm_enabled
        self.alarm_hour = alarm_hour
        self.alarm_minute = alarm_minute
        self.alarm_message = alarm_msg

        self.canvas.config(bg=self.bg_color)
        self.canvas.itemconfig(self.rect_id, fill=self.inner_color)
        self.canvas.itemconfig(self.text_id, fill=self.fg_color)
        self.set_position(x, y)
        self.set_font_size(font_size)
        self.set_alpha(alpha_percent, save=False)
        self.update_font_menu()
        self.update_alpha_menu()
        self.update_lock_menu()

        # Save full config
        self._save_colors()
        self._save_font_size_only(font_size)
        self._save_alpha(alpha_percent)
        self.save_position()
        self.save_lock_state()
        self.save_alarm_config()

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
        # ✅ Changed: "Local Timer" → "Local Time"
        title_label = tk.Label(
            frame,
            text="Local Time for Albion Online",
            font=(self.font_name, 14, "normal"),
            fg=self.fg_color,
            bg=self.inner_color
        )
        title_label.pack()
        separator = tk.Frame(frame, height=1, bg=self.fg_color)
        separator.pack(fill="x", pady=(2, 4))
        # ✅ Dynamic hotkey + VERSION constant
        about_text = (
            f"{self.hotkey} - show/hide window\n"
            "By TeslaWizard (Europe)\n"
            f"Ver. {VERSION}\n"
            "©2025 Free"
        )
        credit_label = tk.Label(
            frame,
            text=about_text,
            font=(self.font_name, 14, "normal"),
            fg=self.fg_color,
            bg=self.inner_color,
            justify="center"
        )
        credit_label.pack()
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
        about.bind("<Button-1>", lambda e: about.destroy())
        about.bind("<Escape>", lambda e: about.destroy())

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

        # ✅ FIXED: safe next-minute boundary (23:59→00:00 safe!)
        next_min = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        delay_ms = int((next_min - now).total_seconds() * 1000)
        delay_ms = max(50, min(60_000, delay_ms))

        # ✅ Check alarm once per minute
        if self.alarm_enabled and now.hour == self.alarm_hour and now.minute == self.alarm_minute:
            self.trigger_alarm()
            # Optional: auto-disable — uncomment to make one-time
            # self.alarm_enabled = False
            # self.save_alarm_config()

        if self.update_job:
            try:
                self.root.after_cancel(self.update_job)
            except Exception:
                pass
        self.update_job = self.root.after(delay_ms, self.update_time)


if __name__ == "__main__":
    ClockOverlay()
