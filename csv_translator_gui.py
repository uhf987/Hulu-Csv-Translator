"""
CSV Translator GUI - TranslateGemma:12b
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests

import csv_translator
from csv_translator import translate_csv, LANGUAGES, PROTECT_PATTERNS


def check_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


LANG_LIST = sorted(LANGUAGES.keys())
PATTERN_NAMES = list(PROTECT_PATTERNS.keys())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV Translator - TranslateGemma:12b")
        self.resizable(True, True)
        self.configure(padx=16, pady=16, bg="#f5f5f5")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._thread = None

        # ── Files ─────────────────────────────────────────────────
        file_frame = tk.LabelFrame(self, text=" Files ", bg="#f5f5f5", font=("Segoe UI", 9, "bold"))
        file_frame.pack(fill="x", pady=(0, 10))

        tk.Label(file_frame, text="Input CSV:", bg="#f5f5f5", width=10, anchor="w").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.input_var = tk.StringVar()
        tk.Entry(file_frame, textvariable=self.input_var, width=52).grid(row=0, column=1, padx=4)
        tk.Button(file_frame, text="Browse...", command=self.pick_input, width=8).grid(row=0, column=2, padx=6)

        tk.Label(file_frame, text="Output CSV:", bg="#f5f5f5", width=10, anchor="w").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.output_var = tk.StringVar()
        tk.Entry(file_frame, textvariable=self.output_var, width=52).grid(row=1, column=1, padx=4)
        tk.Button(file_frame, text="Browse...", command=self.pick_output, width=8).grid(row=1, column=2, padx=6)

        # ── Language ──────────────────────────────────────────────
        lang_frame = tk.LabelFrame(self, text=" Language ", bg="#f5f5f5", font=("Segoe UI", 9, "bold"))
        lang_frame.pack(fill="x", pady=(0, 10))

        tk.Label(lang_frame, text="Source:", bg="#f5f5f5").grid(row=0, column=0, padx=8, pady=10, sticky="w")
        self.source_var = tk.StringVar(value="English")
        ttk.Combobox(lang_frame, textvariable=self.source_var, values=LANG_LIST, width=30, state="readonly").grid(row=0, column=1, padx=4)

        tk.Label(lang_frame, text="  →  ", bg="#f5f5f5", font=("Segoe UI", 13, "bold"), fg="#0e7a4e").grid(row=0, column=2)

        tk.Label(lang_frame, text="Target:", bg="#f5f5f5").grid(row=0, column=3, padx=8, sticky="w")
        self.target_var = tk.StringVar(value="Turkish")
        ttk.Combobox(lang_frame, textvariable=self.target_var, values=LANG_LIST, width=30, state="readonly").grid(row=0, column=4, padx=4)

        tk.Button(
            lang_frame, text="⇄ Swap", command=self.swap_langs,
            bg="#e8e8e8", relief="flat", padx=10, pady=4, cursor="hand2"
        ).grid(row=0, column=5, padx=(12, 8))

        # ── Protect Patterns ──────────────────────────────────────
        prot_frame = tk.LabelFrame(self, text=" Protect Patterns (preserved, not translated) ", bg="#f5f5f5", font=("Segoe UI", 9, "bold"))
        prot_frame.pack(fill="x", pady=(0, 10))

        self.pattern_vars = {}
        for i, name in enumerate(PATTERN_NAMES):
            regex, example = PROTECT_PATTERNS[name]
            var = tk.BooleanVar(value=(name == "Pipe"))
            self.pattern_vars[name] = var
            col = i % 4
            row = i // 4
            cb = tk.Checkbutton(
                prot_frame,
                text=name + "  " + example,
                variable=var,
                bg="#f5f5f5",
                font=("Consolas", 9),
                anchor="w",
            )
            cb.grid(row=row, column=col, sticky="w", padx=12, pady=4)

        # ── Settings ──────────────────────────────────────────────
        opt_frame = tk.LabelFrame(self, text=" Settings ", bg="#f5f5f5", font=("Segoe UI", 9, "bold"))
        opt_frame.pack(fill="x", pady=(0, 10))

        tk.Label(opt_frame, text="Columns to translate:", bg="#f5f5f5").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.cols_var = tk.StringVar(value="")
        tk.Entry(opt_frame, textvariable=self.cols_var, width=18).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(opt_frame, text="(e.g. 2  or  1 3 5  |  empty = all columns)", bg="#f5f5f5", fg="#666").grid(row=0, column=2, sticky="w", padx=6)

        tk.Label(opt_frame, text="Ollama model:", bg="#f5f5f5").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.model_var = tk.StringVar(value=csv_translator.MODEL)
        tk.Entry(opt_frame, textvariable=self.model_var, width=28).grid(row=1, column=1, sticky="w", padx=4)

        tk.Label(opt_frame, text="Delimiter:", bg="#f5f5f5").grid(row=1, column=2, sticky="w", padx=(20, 4))
        self.delim_var = tk.StringVar(value=",")
        tk.Entry(opt_frame, textvariable=self.delim_var, width=5).grid(row=1, column=3, sticky="w")

        self.header_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="First row is header (skip translation)", variable=self.header_var, bg="#f5f5f5").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8)
        )

        # ── Progress ──────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg="#f5f5f5")
        prog_frame.pack(fill="x", pady=(0, 6))

        self.progress = ttk.Progressbar(prog_frame, mode="determinate", length=560, maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)

        self.pct_label = tk.Label(prog_frame, text="  0%", bg="#f5f5f5", width=5, font=("Segoe UI", 9, "bold"))
        self.pct_label.pack(side="left")

        self.eta_label = tk.Label(self, text="", bg="#f5f5f5", fg="#555", font=("Segoe UI", 9))
        self.eta_label.pack(anchor="w")

        # ── Live log ──────────────────────────────────────────────
        log_frame = tk.LabelFrame(self, text=" Live Translation Log ", bg="#f5f5f5", font=("Segoe UI", 9, "bold"))
        log_frame.pack(fill="both", expand=True, pady=(6, 10))

        self.log = scrolledtext.ScrolledText(
            log_frame, height=14, width=80, state="disabled",
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        self.log.tag_config("info",   foreground="#9cdcfe")
        self.log.tag_config("result", foreground="#4ec9b0")
        self.log.tag_config("ok",     foreground="#6a9955")
        self.log.tag_config("err",    foreground="#f44747")

        # ── Buttons ───────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg="#f5f5f5")
        btn_frame.pack(fill="x")

        self.start_btn = tk.Button(
            btn_frame, text="▶  Start Translation",
            bg="#0e7a4e", fg="white", font=("Segoe UI", 10, "bold"),
            padx=16, pady=8, relief="flat", cursor="hand2",
            command=self.start
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = tk.Button(
            btn_frame, text="■  Stop",
            bg="#c0392b", fg="white", font=("Segoe UI", 10, "bold"),
            padx=16, pady=8, relief="flat", cursor="hand2",
            command=self.stop, state="disabled"
        )
        self.stop_btn.pack(side="left")

        self.status_label = tk.Label(btn_frame, text="", bg="#f5f5f5", fg="#555", font=("Segoe UI", 9))
        self.status_label.pack(side="right")

        self.after(500, self.check_ollama_status)

    def swap_langs(self):
        src = self.source_var.get()
        tgt = self.target_var.get()
        self.source_var.set(tgt)
        self.target_var.set(src)

    def check_ollama_status(self):
        if check_ollama():
            self.status_label.config(text="● Ollama Connected", fg="#0e7a4e")
        else:
            self.status_label.config(text="● Ollama NOT Connected", fg="#c0392b")

    def pick_input(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(path.replace(".csv", "_translated.csv"))

    def pick_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            self.output_var.set(path)

    def log_write(self, msg, tag=None):
        def _write():
            self.log.configure(state="normal")
            if tag:
                self.log.insert("end", msg + "\n", tag)
            else:
                self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, _write)

    def log_callback(self, msg):
        if msg.startswith("  ->"):
            self.log_write(msg, "result")
        elif "DONE" in msg or "Time:" in msg:
            self.log_write(msg, "ok")
        elif "ERROR" in msg or "STOPPED" in msg:
            self.log_write(msg, "err")
        else:
            self.log_write(msg, "info")

    def update_progress(self, current, total, remaining_sec):
        def _update():
            pct = int(current / total * 100)
            self.progress["value"] = pct
            self.pct_label.config(text=str(pct) + "%")
            if remaining_sec > 60:
                eta = str(remaining_sec // 60) + "m " + str(remaining_sec % 60) + "s left"
            else:
                eta = str(remaining_sec) + "s left"
            self.eta_label.config(text=eta + "  (" + str(current) + "/" + str(total) + " rows)")
        self.after(0, _update)

    def start(self):
        inp = self.input_var.get().strip()
        out = self.output_var.get().strip()

        if not inp or not out:
            messagebox.showerror("Error", "Please select input and output files.")
            return

        if not check_ollama():
            messagebox.showerror("Error", "Cannot connect to Ollama!\nIs 'ollama serve' running?")
            return

        cols_raw = self.cols_var.get().strip()
        try:
            columns = [int(c) for c in cols_raw.split()] if cols_raw else None
        except ValueError:
            messagebox.showerror("Error", "Column numbers must be integers (e.g. 2 or 1 3 5)")
            return

        active_patterns = [name for name, var in self.pattern_vars.items() if var.get()]
        if not active_patterns:
            if not messagebox.askyesno("No protection", "No protect patterns selected.\nAll text will be translated. Continue?"):
                return

        csv_translator.MODEL = self.model_var.get().strip()
        src = self.source_var.get()
        tgt = self.target_var.get()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress["value"] = 0
        self.pct_label.config(text="0%")
        self.eta_label.config(text="Starting...")

        src_info = LANGUAGES.get(src, ("?", "?"))
        tgt_info = LANGUAGES.get(tgt, ("?", "?"))

        self.log_write("=" * 60)
        self.log_write("File:     " + inp)
        self.log_write("Lang:     " + src + " (" + src_info[1] + ")  ->  " + tgt + " (" + tgt_info[1] + ")")
        self.log_write("Model:    " + csv_translator.MODEL)
        self.log_write("Cols:     " + (str(columns) if columns else "all"))
        self.log_write("Protect:  " + (", ".join(active_patterns) if active_patterns else "none"))
        self.log_write("=" * 60)

        def run():
            try:
                translate_csv(
                    input_path=inp,
                    output_path=out,
                    skip_header=self.header_var.get(),
                    columns=columns,
                    verbose=False,
                    delimiter=self.delim_var.get() or ",",
                    source_lang=src,
                    target_lang=tgt,
                    active_pattern_names=active_patterns,
                    progress_callback=self.update_progress,
                    log_callback=self.log_callback,
                )
                if not csv_translator._stop_flag:
                    self.after(0, lambda: messagebox.showinfo("Done!", "Translation complete!\n" + out))
            except Exception as e:
                self.log_write("[ERROR] " + str(e), "err")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, self.on_done)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        csv_translator.set_stop()
        self.log_write("[STOP] Signal sent, will stop after current cell...", "err")
        self.stop_btn.configure(state="disabled")

    def on_done(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.eta_label.config(text="")
        self.check_ollama_status()

    def on_close(self):
        if self._thread and self._thread.is_alive():
            csv_translator.set_stop()
            self.after(1500, self.destroy)
        else:
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
