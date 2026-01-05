import threading
import time
from datetime import datetime
import pandas as pd
import queue
import json
import paho.mqtt.client as mqtt
import ssl

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox

# user modules
from defFunc import now_txt, logSave, find_nearest_time_row, clamp, bias_scale, jitter_mul, jitter_add, load_env_vars

import sys, os

def exe_dir() -> str:
    # pyinstaller로 빌드된 경우 exe 위치, 개발환경이면 소스 폴더
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(exe_dir(), "data")
POWER_CSV  = os.path.join(DATA_DIR, "power_data.csv")
WATER_CSV  = os.path.join(DATA_DIR, "water_data.csv")
ENERGY_CSV = os.path.join(DATA_DIR, "energy_data.csv")
CONFIG_ENV = os.path.join(exe_dir(), "config.env")

sensor_dict = {
    "F1": {"power": ["A", "B"], "water": ["A"], "energy": ['1209', '1221', '1225', '1128']},
    "F2": {"power": ["A", "B"], "water": ["A"], "energy": ['2210', '2221']},
    "F3": {"power": ["A", "B"], "water": ["A"], "energy": ['3203', '3208', '3210', '3120']},
    "F4": {"power": ["A", "B"], "water": ["A"], "energy": ['4204', '4218']},
    "F5": {"power": ["A", "B"], "water": ["A"], "energy": []},
    "F6": {"power": ["A", "B"], "water": ["A"], "energy": ['6203', '6210', '6221', '6225']},
    "F7": {"power": ["A", "B"], "water": ["A"], "energy": ['7208', '7210', '7117', '7122', '7221', '7225']},
    "F8": {"power": ["A", "B"], "water": ["A"], "energy": ['8206', '8221', '8123', '8128']},
    "F9": {"power": ["A", "B"], "water": ["A"], "energy": ['9210', '9221']},
    "F10": {"power": ["A", "B"], "water": ["A"], "energy": ['10206', '10210', '10114', '10117', '10221', '10225']}
}

FLOORS = [f"F{i}" for i in range(1, 11)]


def parse_float(var, name):
    s = var.get().strip()
    try:
        return float(s)
    except Exception:
        raise ValueError(f"{name}은(는) 숫자여야 합니다: '{s}'")

class ScrollFrame(ttk.Frame):
    def __init__(self, parent, height=460, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # 실제 컨텐츠가 들어갈 내부 프레임
        self.content = ttk.Frame(self.canvas)
        self.content_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        # 사이즈 변화에 따른 스크롤 영역 갱신
        self.content.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 마우스 휠 (Win/mac), Linux(버튼4/5)
        self.content.bind_all("<MouseWheel>", self._on_mousewheel)      # Win/mac
        self.content.bind_all("<Button-4>", self._on_mousewheel_linux)  # Linux up
        self.content.bind_all("<Button-5>", self._on_mousewheel_linux)  # Linux down

        self.canvas.config(height=height)

    def _on_frame_configure(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, evt):
        self.canvas.itemconfigure(self.content_id, width=evt.width)

    def _on_mousewheel(self, evt):
        # Windows: ±120 / macOS: 작은 값; 둘 다 정상 동작
        self.canvas.yview_scroll(int(-1*(evt.delta/120)), "units")

    def _on_mousewheel_linux(self, evt):
        self.canvas.yview_scroll(-1 if evt.num == 4 else 1, "units")


class BaseTab:
    def __init__(self, parent, app, dtype):
        self.app = app
        self.dtype = dtype
        self.frame = ttk.Frame(parent, padding=10)
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.sent = 0
        try:
            self.logger = logSave("logs", f"{dtype}_sensor")
        except Exception:
            self.logger = None

        self.build_common_top()

    def build_common_top(self):
        top = ttk.Frame(self.frame)
        top.pack(fill="x", pady=(0, 8))

        # floor select or "all floors"
        ttk.Label(top, text="층").grid(row=0, column=0, sticky="w")
        self.floor_var = tk.StringVar(value="F1")
        self.floor_cbo = ttk.Combobox(top, state="readonly", values=FLOORS, textvariable=self.floor_var, width=6)
        self.floor_cbo.grid(row=0, column=1, padx=6)

        self.all_floors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="모든 층", variable=self.all_floors_var, bootstyle=SECONDARY).grid(row=0, column=2,
                                                                                                  padx=(0, 10))

        # period
        ttk.Label(top, text="주기(ms)").grid(row=0, column=3, sticky="w")
        self.period_var = tk.StringVar(value="1000")
        ttk.Entry(top, textvariable=self.period_var, width=8).grid(row=0, column=4, padx=6)

        # start/stop
        self.toggle_btn = ttk.Button(top, text="시작", bootstyle=SUCCESS, command=self.toggle)
        self.toggle_btn.grid(row=0, column=5, padx=(10, 0))

        # status
        self.status_var = tk.StringVar(value="대기 중")
        self.count_var = tk.StringVar(value="0")
        stat = ttk.Frame(self.frame)
        stat.pack(fill="x", pady=(6, 8))
        ttk.Label(stat, text="상태:").pack(side="left")
        ttk.Label(stat, textvariable=self.status_var).pack(side="left", padx=(4, 12))
        ttk.Label(stat, text="누적 건수:").pack(side="left")
        ttk.Label(stat, textvariable=self.count_var).pack(side="left", padx=(4, 0))

    def validate_period(self):
        try:
            v = int(float(self.period_var.get().strip()))
            if v <= 0: raise ValueError
            return v
        except Exception:
            raise ValueError("주기(ms)는 1 이상의 정수여야 합니다.")

    def floors_target(self):
        if self.all_floors_var.get():
            return list(range(1, 11))
        return [int(self.floor_var.get().replace("F", ""))]

    def toggle(self):
        if not self.running:
            try:
                self.validate_entries()
                period = self.validate_period()
            except Exception as e:
                messagebox.showerror("오류", str(e))
                return
            self.running = True
            self.stop_event.clear()
            self.sent = 0
            self.count_var.set("0")
            self.toggle_btn.configure(text="중지", bootstyle=DANGER)
            self.status_var.set("전송 중...")
            self.thread = threading.Thread(target=self.loop, args=(period,), daemon=True)
            self.thread.start()
        else:
            self.stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            self.running = False
            self.toggle_btn.configure(text="시작", bootstyle=SUCCESS)
            self.status_var.set("중지됨")

    def loop(self, period):
        while not self.stop_event.is_set():
            try:
                n = self.emit_once()
                self.sent += n
                self.count_var.set(str(self.sent))
                msg = f"[{datetime.now().replace(microsecond=0)}] {self.dtype} {n}건 전송"
                self.app.log(msg)
                if self.logger:
                    try:
                        self.logger.LogTextOut(msg)
                    except Exception:
                        pass
            except Exception as e:
                self.app.log(f"{self.dtype} 오류: {e}")
            time.sleep(max(0.001, period / 1000.0))

    # Implement in child
    def validate_entries(self):
        ...

    def emit_once(self):
        ...


# -------------------- Power Tab --------------------
class PowerTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app, "power")
        self.override_keys = set()
        frm = ttk.Labelframe(self.frame, text="입력값", padding=10)
        frm.pack(fill="x")

        # section choice
        row = 0
        ttk.Label(frm, text="섹션").grid(row=row, column=0, sticky="w")
        self.section_var = tk.StringVar(value="A")
        self.section_cbo = ttk.Combobox(frm, state="readonly", values=["A", "B"], textvariable=self.section_var,
                                        width=6)
        self.section_cbo.grid(row=row, column=1, padx=6)
        self.all_sections_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="A/B 모두", variable=self.all_sections_var, bootstyle=SECONDARY).grid(row=row, column=2,
                                                                                                      padx=(0, 10))
        row += 1

        # numeric fields
        self.p_vars = {}
        fields = [
            # ("humi", "습도(%)"), ("temp", "온도(°C)"),
            # ("active_electric_energy", "유효전력 에너지(Wh)"),
            ("total_active_power", "유효전력(W)"),
            # ("total_reactive_power", "무효전력(var)"),
            # ("total_apparent_power", "피상전력(VA)"),
            # ("total_power_factor", "역률"),
        ]

        col = 0
        for key, label in fields:
            ttk.Label(frm, text=label).grid(row=row, column=col * 2, sticky="w", pady=4)
            var = tk.StringVar(value="0")
            ttk.Entry(frm, textvariable=var, width=12).grid(row=row, column=col * 2 + 1, padx=6, pady=4)
            self.p_vars[key] = var
            col += 1
            if col == 3:
                row += 1
                col = 0

    def validate_entries(self):
        # ensure floats
        for k, v in self.p_vars.items():
            parse_float(v, k)
        # section ok
        if not self.all_sections_var.get():
            if self.section_var.get() not in ("A", "B"):
                raise ValueError("섹션은 A 또는 B 여야 합니다.")

    def emit_once(self):
        floors = self.floors_target()
        sections = ["A", "B"] if self.all_sections_var.get() else [self.section_var.get()]
        vals = {k: parse_float(v, k) for k, v in self.p_vars.items()}

        count = 0
        for floor in floors:
            for section in sections:
                payload = {
                    "date": now_txt(),
                    "floor": int(floor),
                    "section": section,
                    # 수동 UI 스펙에 맞춰 최소 필드만 전송
                    "active_electric_energy": float(vals["total_active_power"]),
                    "total_active_power": float(vals["total_active_power"]),
                    # 필요시 0/고정값 유지
                    "total_reactive_power": 0,
                    "total_apparent_power": 0,
                    "total_power_factor": 0,
                    "temp": 0,
                    "humi": 0,
                }
                topic = f"{self.app.mqtt_base}/power/F{floor}/{section}"
                self.app._mqtt_publish(topic, payload)
                count += 1
        return count

    def toggle(self):
        if not self.running:
            floors = self.floors_target()
            sections = ["A", "B"] if self.all_sections_var.get() else [self.section_var.get()]
            keys = {(f, s) for f in floors for s in sections}

            try:
                self.validate_entries()
                period = self.validate_period()
            except Exception as e:
                messagebox.showerror("오류", str(e))
                return

            try:
                self.app.register_override('power', keys)
                self.override_keys = keys  # 중지 시 동일 키로 해제

                self.running = True
                self.stop_event.clear()
                self.sent = 0
                self.count_var.set("0")
                self.toggle_btn.configure(text="중지", bootstyle=DANGER)
                self.status_var.set("전송 중...")
                self.thread = threading.Thread(target=self.loop, args=(period,), daemon=True)
                self.thread.start()
            except Exception as e:
                self.app.unregister_override('power', keys)
                self.override_keys = set()
                self.running = False
                messagebox.showerror("오류", f"시작 실패: {e}")
                return

        else:
            self.stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)

            if self.override_keys:
                self.app.unregister_override('power', self.override_keys)
                self.override_keys = set()

            self.running = False
            self.toggle_btn.configure(text="시작", bootstyle=SUCCESS)
            self.status_var.set("중지됨")


# -------------------- Water Tab --------------------
class WaterTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app, "water")
        self.override_keys = set()
        frm = ttk.Labelframe(self.frame, text="입력값", padding=10)
        frm.pack(fill="x")

        ttk.Label(frm, text="섹션").grid(row=0, column=0, sticky="w")
        self.section_fixed = ttk.Label(frm, text="A (고정)")
        self.section_fixed.grid(row=0, column=1, padx=6)

        self.w_vars = {}
        fields = [
            ("inst_flow", "순간유량"),
            # ("neg_dec_data", "역감산"),
            # ("neg_sum_data", "역누적"),
            # ("pos_dec_data", "정감산"),
            # ("pos_sum_data", "정누적"),
            # ("plain_dec_data", "플레인감산"),
            # ("plain_sum_data", "플레인누적"),
            # ("today_value", "금일값"),
        ]
        r, c = 1, 0
        for key, label in fields:
            ttk.Label(frm, text=label).grid(row=r, column=c * 2, sticky="w", pady=4)
            var = tk.StringVar(value="0")
            ttk.Entry(frm, textvariable=var, width=12).grid(row=r, column=c * 2 + 1, padx=6, pady=4)
            self.w_vars[key] = var
            c += 1
            if c == 3:
                r += 1
                c = 0

    def validate_entries(self):
        for k, v in self.w_vars.items():
            parse_float(v, k)

    def emit_once(self):
        floors = self.floors_target()
        vals = {k: parse_float(v, k) for k, v in self.w_vars.items()}

        count = 0
        for floor in floors:
            payload = {
                "date": now_txt(),
                "floor": int(floor),
                "section": "A",
                "inst_flow": float(vals["inst_flow"]),
                # 누적/감산류는 수동 UI에서 미사용 → 0으로 고정
                "neg_dec_data": 0,
                "neg_sum_data": 0,
                "pos_dec_data": 0,
                "pos_sum_data": 0,
                "plain_dec_data": 0,
                "plain_sum_data": 0,
                "today_value": 0,
            }
            topic = f"{self.app.mqtt_base}/water/F{floor}"
            self.app._mqtt_publish(topic, payload)
            count += 1
        return count

    def toggle(self):
        if not self.running:
            floors = self.floors_target()
            keys = {(f,) for f in floors}

            try:
                self.validate_entries()
                period = self.validate_period()
            except Exception as e:
                messagebox.showerror("오류", str(e))
                return

            try:
                self.app.register_override('water', keys)
                self.override_keys = keys

                self.running = True
                self.stop_event.clear()
                self.sent = 0
                self.count_var.set("0")
                self.toggle_btn.configure(text="중지", bootstyle=DANGER)
                self.status_var.set("전송 중...")
                self.thread = threading.Thread(target=self.loop, args=(period,), daemon=True)
                self.thread.start()
            except Exception as e:
                self.app.unregister_override('water', keys)
                self.override_keys = set()
                self.running = False
                messagebox.showerror("오류", f"시작 실패 : {e}")
                return
        else:
            self.stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            if self.override_keys:
                self.app.unregister_override('water', self.override_keys)
                self.override_keys = set()

            self.running = False
            self.toggle_btn.configure(text="시작", bootstyle=SUCCESS)
            self.status_var.set("중지됨")


# -------------------- Energy Tab --------------------
class EnergyTab(BaseTab):
    def __init__(self, parent, app):
        super().__init__(parent, app, "energy")
        self.override_keys = set()

        cfg = ttk.Frame(self.frame)
        cfg.pack(fill="x", pady=(0, 8))

        # energy id list depends on floor
        ttk.Label(cfg, text="에너지 ID").grid(row=0, column=0, sticky="w")
        self.energy_var = tk.StringVar()
        self.energy_cbo = ttk.Combobox(cfg, state="readonly", textvariable=self.energy_var, width=10)
        self.energy_cbo.grid(row=0, column=1, padx=6)
        self.all_energy_ids_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="해당 층의 모든 ID",
                        variable=self.all_energy_ids_var,
                        command=self._on_all_ids_toggle,
                        bootstyle=SECONDARY).grid(row=0,column=2,padx=(0, 10))
        self.floor_var.trace_add('write', lambda *args: self.refresh_energy_ids())
        self.refresh_energy_ids()
        self._on_all_ids_toggle()
        frm = ttk.Labelframe(self.frame, text="입력값", padding=10)
        frm.pack(fill="x")

        self.e_vars = {}
        fields = [
            ("co2", "CO₂(ppm)"),
            ("temp", "온도(°C) → temperature"),
            ("humi", "습도(%) → humidity"),
            # ("pm1", "PM1.0(µg/m³) → pm1_0"),
            # ("pm2_5", "PM2.5(µg/m³)"),
            # ("pm10", "PM10(µg/m³)"),
            # ("voc", "VOC(ppb)"),
        ]
        r, c = 0, 0
        for key, label in fields:
            ttk.Label(frm, text=label).grid(row=r, column=c * 2, sticky="w", pady=4)
            var = tk.StringVar(value="0")
            ttk.Entry(frm, textvariable=var, width=12).grid(row=r, column=c * 2 + 1, padx=6, pady=4)
            self.e_vars[key] = var
            c += 1
            if c == 3:
                r += 1
                c = 0

    def _on_all_ids_toggle(self):
        state = "disabled" if self.all_energy_ids_var.get() else "readonly"
        self.energy_cbo.configure(state=state)

    def refresh_energy_ids(self):
        floor = self.floor_var.get() or "F1"
        ids = sensor_dict.get(floor, {}).get("energy", [])
        self.energy_cbo.configure(values=ids)
        if ids:
            self.energy_var.set(ids[0])
        else:
            self.energy_var.set("")
        self._on_all_ids_toggle()

    def validate_entries(self):
        for k, v in self.e_vars.items():
            parse_float(v, k)
        # energy id
        if not self.all_energy_ids_var.get():
            floor = self.floor_var.get()
            ids = sensor_dict.get(floor, {}).get("energy", [])
            if self.energy_var.get() not in ids:
                raise ValueError("해당 층에 유효한 에너지 ID를 선택하세요.")

    def emit_once(self):
        floors = self.floors_target()
        vals = {k: parse_float(v, k) for k, v in self.e_vars.items()}

        count = 0
        for floor in floors:
            floor_key = f"F{floor}"
            ids = sensor_dict.get(floor_key, {}).get("energy", [])
            target_ids = ids if self.all_energy_ids_var.get() else [self.energy_var.get()]
            for section in target_ids:
                if not section:
                    continue
                payload = {
                    "date": now_txt(),
                    "floor": int(floor),
                    "section": section,
                    # 수동 UI 스펙에 맞춰 정수/스케일 그대로 적용
                    "co2": int(vals["co2"]),
                    "temperature": int(float(vals["temp"]) * 10),
                    "humidity": int(float(vals["humi"]) * 10),
                    "pm1_0": 0,
                    "pm2_5": 0,
                    "pm10": 0,
                    "voc": 0,
                    "tempimage" : 0,
                    "errcode" : 123456,
                }
                topic = f"{self.app.mqtt_base}/energy/F{floor}/{section}"
                self.app._mqtt_publish(topic, payload)
                count += 1
        return count

    def toggle(self):
        if not self.running:
            keys = {
                (floor, eid)
                for floor in self.floors_target()
                for eid in (
                    sensor_dict.get(f"F{floor}", {}).get("energy", [])
                    if self.all_energy_ids_var.get()
                    else [self.energy_var.get()]
                )
                if eid
            }

            try:
                self.validate_entries()
                period = self.validate_period()
            except Exception as e:
                messagebox.showerror("오류", str(e))
                return

            if not keys:
                messagebox.showerror("오류", "선택한 층에 전송할 에너지 ID가 없습니다.")
                return

            try:
                self.app.register_override('energy', keys)
                self.override_keys = keys

                self.running = True
                self.stop_event.clear()
                self.sent = 0
                self.count_var.set("0")
                self.toggle_btn.configure(text="중지", bootstyle=DANGER)
                self.status_var.set("전송 중...")
                self.thread = threading.Thread(target=self.loop, args=(period,), daemon=True)
                self.thread.start()
            except Exception as e:
                self.app.unregister_override('energy', keys)
                self.override_keys = set()
                self.running = False
                messagebox.showerror("오류", f"시작실패: {e}")
                return

        else:
            self.stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)

            if self.override_keys:
                self.app.unregister_override('energy', self.override_keys)
                self.override_keys = set()

            self.running = False
            self.toggle_btn.configure(text="시작", bootstyle=SUCCESS)
            self.status_var.set("중지됨")


#     """선택된 위치만 CSV 기본 발행되도록 허용 목록을 설정하는 탭"""
class DefaultSelectTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent, padding=10)

        # 스크롤 가능한 영역
        sf = ScrollFrame(self.frame, height=460)
        sf.pack(fill="both", expand=True)
        root = sf.content   # 이후 컨트롤은 전부 root에 붙인다

        # --- POWER (층/섹션)
        pbox = ttk.Labelframe(root, text="Power - 발행할 위치(체크=발행)", padding=10)
        pbox.pack(fill="x", pady=(0,10))

        self.p_vars = {}  # {(floor,'A'|'B'): BooleanVar}
        grid = ttk.Frame(pbox); grid.pack()
        ttk.Label(grid, text="층").grid(row=0, column=0, padx=6)
        ttk.Label(grid, text="A").grid(row=0, column=1, padx=6)
        ttk.Label(grid, text="B").grid(row=0, column=2, padx=6)

        for i, floor in enumerate(range(1,11), start=1):
            ttk.Label(grid, text=f"F{floor}").grid(row=i, column=0)
            for j, sec in enumerate(['A','B'], start=1):
                var = tk.BooleanVar(value=False)
                self.p_vars[(floor, sec)] = var
                ttk.Checkbutton(grid, variable=var, bootstyle=SECONDARY).grid(row=i, column=j)

        pbtns = ttk.Frame(pbox); pbtns.pack(fill="x", pady=(8,0))
        ttk.Button(pbtns, text="적용", bootstyle=PRIMARY, command=self.apply_power).pack(side="left")
        ttk.Button(pbtns, text="모두 해제", command=self.clear_power).pack(side="left", padx=6)
        ttk.Button(pbtns, text="모두 선택", command=self.select_all_power).pack(side="left", padx=6)

        # --- WATER (층)
        wbox = ttk.Labelframe(root, text="Water - 발행할 층(체크=발행)", padding=10)
        wbox.pack(fill="x", pady=(0,10))

        self.w_vars = {}  # {(floor,): BooleanVar}
        wgrid = ttk.Frame(wbox); wgrid.pack()
        for i, floor in enumerate(range(1,11)):
            var = tk.BooleanVar(value=False)
            self.w_vars[(floor,)] = var
            ttk.Checkbutton(wgrid, text=f"F{floor}", variable=var, bootstyle=SECONDARY).grid(
                row=i//5, column=i%5, sticky="w", padx=8, pady=4
            )
        wbtns = ttk.Frame(wbox); wbtns.pack(fill="x", pady=(8,0))
        ttk.Button(wbtns, text="적용", bootstyle=PRIMARY, command=self.apply_water).pack(side="left")
        ttk.Button(wbtns, text="모두 해제", command=self.clear_water).pack(side="left", padx=6)
        ttk.Button(wbtns, text="모두 선택", command=self.select_all_water).pack(side="left", padx=6)

        # --- ENERGY (층/ID)
        ebox = ttk.Labelframe(root, text="Energy - 발행할 (층/ID) 선택(체크=발행)", padding=10)
        ebox.pack(fill="x")

        # 1) 층 다중 선택(체크박스)
        floors_bar = ttk.Frame(ebox);
        floors_bar.pack(fill="x")
        ttk.Label(floors_bar, text="층 선택").pack(side="left", padx=(0, 8))

        self.e_floor_vars = {}  # {int_floor: BooleanVar}
        for i in range(1, 11):
            var = tk.BooleanVar(value=False)
            self.e_floor_vars[i] = var
            ttk.Checkbutton(floors_bar, text=f"F{i}", variable=var, bootstyle=SECONDARY) \
                .pack(side="left", padx=2)

        btn_row = ttk.Frame(ebox)
        btn_row.pack(fill="x", pady=(8, 8))
        ttk.Button(btn_row, text="선택 층의 ID 불러오기",
                   command=self.load_energy_ids).pack(side="left", padx=(10, 0))
        ttk.Button(btn_row, text="층 전체 선택",
                   command=lambda: [v.set(True) for v in self.e_floor_vars.values()]).pack(side="left", padx=6)
        ttk.Button(btn_row, text="층 모두 해제",
                   command=lambda: [v.set(False) for v in self.e_floor_vars.values()]).pack(side="left", padx=6)

        # 2) 선택된 층들의 ID 체크박스들 (층 별 그룹)
        self.e_vars = {}  # {(floor:int, energy_id:str): BooleanVar}
        self.e_ids_box = ttk.Frame(ebox)  # 여러 층의 그룹을 담는 컨테이너
        self.e_ids_box.pack(fill="x")

        # 하단 버튼들
        ebtns = ttk.Frame(ebox);
        ebtns.pack(fill="x", pady=(8, 0))
        ttk.Button(ebtns, text="적용", bootstyle=PRIMARY, command=self.apply_energy).pack(side="left")
        ttk.Button(ebtns, text="모두 해제", command=self.clear_energy).pack(side="left", padx=6)
        ttk.Button(ebtns, text="현재 표시된 ID 모두 선택", command=self.select_all_energy_ids).pack(side="left", padx=6)

        self.load_energy_ids()

    # ----- POWER -----
    def apply_power(self):
        keys = {(f,s) for (f,s), v in self.p_vars.items() if v.get()}
        self.app.replace_default_select('power', keys)
        self.app.log(f"[기본 발행] POWER 허용 적용: {sorted(keys)}")

    def clear_power(self):
        for v in self.p_vars.values(): v.set(False)
        self.app.clear_default_select('power')
        self.app.log("[기본 발행] POWER 허용 모두 해제")

    def select_all_power(self):
        for v in self.p_vars.values(): v.set(True)

    # ----- WATER -----
    def apply_water(self):
        keys = {(f,) for (f,), v in self.w_vars.items() if v.get()}
        self.app.replace_default_select('water', keys)
        self.app.log(f"[기본 발행] WATER 허용 적용: {sorted(keys)}")

    def clear_water(self):
        for v in self.w_vars.values(): v.set(False)
        self.app.clear_default_select('water')
        self.app.log("[기본 발행] WATER 허용 모두 해제")

    def select_all_water(self):
        for v in self.w_vars.values(): v.set(True)

    # ----- ENERGY -----
    def _selected_energy_floors(self):
        """체크된 층 번호 리스트 반환 (예: [1,3,7])"""
        return [f for f, var in self.e_floor_vars.items() if var.get()]

    def load_energy_ids(self):
        """선택된 층들의 에너지 ID 체크박스를 층별 그룹으로 다시 그리기"""
        # 기존 위젯 정리
        for child in list(self.e_ids_box.children.values()):
            child.destroy()

        sel_floors = self._selected_energy_floors()
        if not sel_floors:
            ttk.Label(self.e_ids_box, text="(선택된 층이 없습니다)").pack(anchor="w")
            return

        for floor in sel_floors:
            floor_key = f"F{floor}"
            ids = sensor_dict.get(floor_key, {}).get("energy", [])

            group = ttk.Labelframe(self.e_ids_box, text=f"F{floor} - 에너지 ID", padding=8)
            group.pack(fill="x", pady=(0, 6))

            if not ids:
                ttk.Label(group, text="(이 층에는 에너지 ID가 없습니다)").grid(row=0, column=0, sticky="w")
                continue

            row, col = 0, 0
            for eid in ids:
                key = (floor, eid)
                var = self.e_vars.get(key)
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.e_vars[key] = var
                ttk.Checkbutton(group, text=eid, variable=var, bootstyle=SECONDARY) \
                    .grid(row=row, column=col, padx=8, pady=4, sticky="w")
                col += 1
                if col >= 5:
                    col = 0
                    row += 1

    def apply_energy(self):
        """체크된 (층,ID)만 허용 목록으로 반영"""
        keys = {(f, eid) for (f, eid), v in self.e_vars.items() if v.get()}
        self.app.replace_default_select('energy', keys)
        self.app.log(f"[기본 발행] ENERGY 허용 적용: {sorted(keys)}")

    def clear_energy(self):
        """모든 ID 체크 해제 + 허용 목록 비움"""
        for v in self.e_vars.values():
            v.set(False)
        self.app.clear_default_select('energy')
        self.app.log("[기본 발행] ENERGY 허용 모두 해제")

    def select_all_energy_ids(self):
        """현재 표시된 층들에 나타난 ID 체크 전부 ON"""
        shown_floors = set(self._selected_energy_floors())
        for (f, eid), v in self.e_vars.items():
            if f in shown_floors:
                v.set(True)

def to_bool(s: str) -> bool:
    return str(s).lower() in ("1","true","yes","y","on")

# -------------------- App --------------------
class App:
    def __init__(self):
        self.root = ttk.Window(themename="flatly")
        self.root.title("Manual Sensor Data Generator")
        self.root.geometry("1000x640")
        self.root.minsize(900, 560)

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))

        right = ttk.Labelframe(main, text="로그", padding=8)
        right.pack(side="left", fill="both", expand=True)

        nb = ttk.Notebook(left, padding=0, bootstyle=PRIMARY)
        nb.pack(fill="both", expand=True)

        self.power_tab = PowerTab(nb, self)
        self.water_tab = WaterTab(nb, self)
        self.energy_tab = EnergyTab(nb, self)
        self.select_tab = DefaultSelectTab(nb, self)

        nb.add(self.select_tab.frame, text="기본 발행 선택")
        nb.add(self.power_tab.frame, text="Power")
        nb.add(self.water_tab.frame, text="Water")
        nb.add(self.energy_tab.frame, text="Energy")

        # 선택된위치만 데이터 발행 빈셋일 경우 모두 허용
        self.default_select = {
            'power': set(),  # {(floor:int, 'A'|'B')}
            'water': set(),  # {(floor:int,)}
            'energy': set(),  # {(floor:int, energy_id:str)}
        }

        # Log UI
        self.log_txt = tk.Text(right, height=24, wrap="none")
        self.log_txt.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(right, orient="vertical", command=self.log_txt.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log_txt.configure(yscrollcommand=yscroll.set)

        clear_btn = ttk.Button(right, text="로그 지우기", command=lambda: self.log_txt.delete("1.0", "end"))
        clear_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        # -------------------- 기본 데이터 생성용 -------------------
        # self.csv_path = {
        #     'power': './data/power_data.csv',
        #     'water': './data/water_data.csv',
        #     'energy': './data/energy_data.csv',
        # }
        # 수동 입력(override) 대상
        self.override = {
            'power': set(),  # {(floor:int, section:str)}
            'water': set(),  # {(floor:int,)}
            'energy': set(),  # {(floor:int, energy_id:str)}
        }

        self.env = load_env_vars(CONFIG_ENV)
        # MQTT 설정
        self.mqtt_base = self.env.get("MQTT_BASE_TOPIC", "lemon/sensors").rstrip("/")
        self.mqtt_qos = int(self.env.get("MQTT_QOS", "0"))
        self.mqtt_retain = to_bool(self.env.get("MQTT_RETAIN", "false"))

        # ✅ MQTT 연결
        self._init_mqtt()


        self.override_lock = threading.Lock()
        self.default_stop = threading.Event()
        self.default_thread = None
        self.log_queue = queue.Queue()
        self.root.after(100, self._drain_logs)
        self.start_default_worker(period_ms=1000)
        # --------------------------------------------------------

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # 허용 목록 교체/초기화 도우미
    def replace_default_select(self, dtype, keys):
        with self.override_lock:
            self.default_select[dtype] = set(keys)

    def clear_default_select(self, dtype):
        with self.override_lock:
            self.default_select[dtype].clear()

    # 허용 체크 도우미 (빈 set이면 모두 허용)
    def _is_allowed(self, dtype, key_tuple):
        sel = self.default_select.get(dtype, set())
        return (not sel) or (key_tuple in sel)

    # mqtt 연결 및 데이터 발행
    def _init_mqtt(self):
        host = self.env.get("MQTT_HOST", "localhost")
        port = int(self.env.get("MQTT_PORT", "8883"))
        ca = self.env.get("MQTT_CA_CERT", "ca.crt")
        user = self.env.get("MQTT_USER", "")
        pw   = self.env.get("MQTT_PASS", "")

        self.mqtt = mqtt.Client()
        if user:
            self.mqtt.username_pw_set(user, pw)

        # TLS 설정 (CA만 지정: 서버 인증서 검증)
        self.mqtt.tls_set(
            ca_certs=ca,
            certfile=None,
            keyfile=None,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        # 호스트네임 불일치/자체서명 문제를 일시 무시
        self.mqtt.tls_insecure_set(True)

        self.mqtt.enable_logger()
        # 콜백(선택)
        self.mqtt.on_connect = lambda c,u,f,rc: self.log(f"[MQTT] connected rc={rc}")
        self.mqtt.on_disconnect = lambda c,u,rc: self.log(f"[MQTT] disconnected rc={rc}")

        try:
            self.mqtt.connect(host, port, keepalive=30)
            # 백그라운드 네트워크 루프 시작
            self.mqtt.loop_start()
        except Exception as e:
            self.log(f"[MQTT] connect failed: {e}")

    def _mqtt_publish(self, topic: str, payload: dict):
        """스레드 어디서 호출해도 안전하게 발행"""
        try:
            data = json.dumps(payload, ensure_ascii=False)
            self.mqtt.publish(topic, data, qos=self.mqtt_qos, retain=self.mqtt_retain)
        except Exception as e:
            self.log(f"[MQTT] publish error: {e}")

    # 수동 탭에서 시작/중지 시 호출
    def register_override(self, dtype, keys):
        self.override[dtype].update(keys)

    def unregister_override(self, dtype, keys):
        for k in keys:
            self.override[dtype].discard(k)

    def make_default_data(self):
        # ----- POWER -----
        try:
            pdf = pd.read_csv(POWER_CSV, parse_dates=['date'])
            prow, now = find_nearest_time_row(pdf)
            with self.override_lock:
                ov = set(self.override['power'])
                sel = set(self.default_select['power'])
            count = 0
            for floor in range(1, 11):
                for section in ['A', 'B']:
                    key = (floor, section)
                    if key in ov:  # 수동 전송 중이면 제외
                        continue
                    if key not in sel:
                        continue

                    p_bias = bias_scale(floor, 3.0) * jitter_mul(2.0)
                    if section == 'B': p_bias *= 1.01
                    temp = float(prow['temp']) + (floor - 6) * 0.2 + jitter_add(0.3)
                    humi = clamp(float(prow['humi']) + (floor - 6) * 0.6 + jitter_add(1.5), 0, 100)
                    if section == 'B':
                        temp += 0.1
                        humi = clamp(humi + 0.2, 0, 100)
                    pf = clamp(float(prow['total_power_factor']) + jitter_add(0.02), 0.0, 1.0)

                    payload = {
                        "date": now_txt(),
                        "floor": floor,
                        "section": section,
                        "temp": float(temp),
                        "humi": float(humi),
                        "active_electric_energy": float(prow["active_electric_energy"] * p_bias),
                        "total_active_power": float(prow["total_active_power"] * p_bias),
                        "total_reactive_power": float(prow["total_reactive_power"] * p_bias),
                        "total_apparent_power": float(prow["total_apparent_power"] * p_bias),
                        "total_power_factor": float(pf),
                    }
                    topic = f"{self.mqtt_base}/power/F{floor}/{section}"
                    self._mqtt_publish(topic, payload)
                    count += 1
            if count:
                self.log(f"[{now}] POWER MQTT {count}건 발행")
        except Exception as e:
            self.log(f"[POWER 기본 생성 실패] {e}")

        # ----- WATER -----
        try:
            wdf = pd.read_csv(WATER_CSV, parse_dates=['date'])
            wrow, now = find_nearest_time_row(wdf)
            with self.override_lock:
                ov = set(self.override['water'])
                sel = set(self.default_select['water'])
            count = 0
            for floor in range(1, 11):
                key = (floor,)
                if key in ov:
                    continue
                if key not in sel:
                    continue

                flow_bias = bias_scale(floor, 2.0) * jitter_mul(5.0)
                sum_bias = bias_scale(floor, 1.0)

                payload = {
                    "date": now_txt(),
                    "floor": floor,
                    "section": "A",
                    "inst_flow": float(wrow["inst_flow"] * flow_bias),
                    "neg_dec_data": float(wrow["neg_dec_data"] * sum_bias),
                    "neg_sum_data": float(wrow["neg_sum_data"] * sum_bias),
                    "pos_dec_data": float(wrow["pos_dec_data"] * sum_bias),
                    "pos_sum_data": float(wrow["pos_sum_data"] * sum_bias),
                    "plain_dec_data": float(wrow["plain_dec_data"] * sum_bias),
                    "plain_sum_data": float(wrow["plain_sum_data"] * sum_bias),
                    "today_value": float(wrow["today_value"] * sum_bias),
                }
                topic = f"{self.mqtt_base}/water/F{floor}"
                self._mqtt_publish(topic, payload)
                count += 1
            if count:
                self.log(f"[{now}] WATER MQTT {count}건 발행")
        except Exception as e:
            self.log(f"[WATER 기본 생성 실패] {e}")

        # ----- ENERGY -----
        try:
            edf = pd.read_csv(ENERGY_CSV, parse_dates=['date'])
            erow, now = find_nearest_time_row(edf)
            with self.override_lock:
                ov = set(self.override['energy'])
                sel = set(self.default_select['energy'])
            count = 0
            for floor_key, cfg in sensor_dict.items():
                floor = int(floor_key.replace('F', ''))
                for energy_id in cfg['energy']:
                    key = (floor, energy_id)
                    if key in ov:
                        continue
                    if key not in sel:
                        continue

                    temp = float(erow["temp"]) + (floor - 6) * 0.2 + jitter_add(0.3)
                    humi = clamp(float(erow["humi"]) + (floor - 6) * 0.5 + jitter_add(1.0), 0, 100)
                    # pm_bias = bias_scale(floor, 2.0) * jitter_mul(10.0)
                    # voc_bias = bias_scale(floor, 1.0) * jitter_mul(8.0)
                    co2 = max(350.0, float(erow["co2"]) + (floor - 6) * 15 + jitter_add(25))

                    payload = {
                        "date": now_txt(),
                        "floor": floor,
                        "section": energy_id,
                        "co2": int(co2),
                        "temperature": int(temp),
                        "humidity": int(humi),
                        "pm1_0": 0,
                        "pm2_5": 0,
                        "pm10": 0,
                        "voc": 0,
                        "tempimage":0,
                        "errcode":123456,
                    }
                    topic = f"{self.mqtt_base}/energy/F{floor}/{energy_id}"
                    self._mqtt_publish(topic, payload)
                    count += 1
            if count:
                self.log(f"[{now}] ENERGY MQTT {count}건 발행")
        except Exception as e:
            self.log(f"[ENERGY 기본 생성 실패] {e}")

    MAX_LOG_LINES = 1000
    TRIM_TO_LINES = 800

    def _trim_log_ui(self):
        try:
            # 현재 마지막 문자 위치의 "줄.열"에서 줄 번호만 가져오기
            line_count = int(self.log_txt.index('end-1c').split('.')[0])
            if line_count > self.MAX_LOG_LINES:
                first_keep = line_count - self.TRIM_TO_LINES + 1
                # 1행부터 first_keep-1행까지 삭제
                self.log_txt.delete("1.0", f"{first_keep}.0")
        except Exception:
            pass

    def log(self, text):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda t=text: self.log(t))
            return

        try:
            self.log_txt.insert("end", text + "\n")
            self._trim_log_ui()
            self.log_txt.see("end")
        except Exception:
            pass

    def start_default_worker(self, period_ms=1000):
        """CSV 기반 make_default_data()를 주기적으로 호출하는 백그라운드 워커 시작"""
        if self.default_thread and self.default_thread.is_alive():
            return
        self.default_stop.clear()
        self.default_thread = threading.Thread(
            target=self._default_loop,
            args=(period_ms,),
            daemon=True,
        )
        self.default_thread.start()

    def stop_default_worker(self):
        """백그라운드 워커 중지"""
        self.default_stop.set()
        if self.default_thread and self.default_thread.is_alive():
            self.default_thread.join(timeout=1.0)
        self.default_thread = None

    def _default_loop(self, period_ms):
        while not self.default_stop.is_set():
            try:
                # 오버라이드(수동 입력 중) 제외하고 CSV 기본 데이터 생성
                self.make_default_data()
                # self.log_async(f"[기본 생성] {_count_basic} 생성 완료")
            except Exception as e:
                self.log_async(f"[기본 생성 오류] {e}")
            time.sleep(max(0.001, period_ms / 1000.0))

    # ---- 백그라운드에서 안전하게 로그 넣기 ----
    def log_async(self, text: str):
        try:
            self.log_queue.put_nowait(text)
        except Exception:
            pass

    def _drain_logs(self):
        """메인 스레드에서 주기적으로 큐를 비워 self.log 호출"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log(msg)  # self.log는 메인스레드에서만 UI 접근
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._drain_logs)

    def on_close(self):
        self.stop_default_worker()
        for tab in (self.power_tab, self.water_tab, self.energy_tab):
            if tab.running:
                tab.stop_event.set()
                if tab.thread and tab.thread.is_alive():
                    try:
                        tab.thread.join(timeout=1.0)
                    except Exception:
                        pass
        try:
            self.mqtt.loop_stop()
            self.mqtt.on_disconnect()
        except Exception as e:
            print(e)

        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
