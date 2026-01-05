import logging
import logging.handlers
import threading
from datetime import datetime
import random
import pandas as pd

import sys, os

def exe_dir():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
           else os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(exe_dir(), "data")
POWER_CSV  = os.path.join(DATA_DIR, "power_data.csv")
WATER_CSV  = os.path.join(DATA_DIR, "water_data.csv")
ENERGY_CSV = os.path.join(DATA_DIR, "energy_data.csv")
CONFIG_ENV = os.path.join(exe_dir(), "config.env")

# 로그를 저장하고 관리하는 클래스
# Singleton 구조
class logSave:
    _instances = {}
    _instances_lock = threading.Lock()

    def __new__(cls, dir, logname):
        key = (dir, logname)
        with cls._instances_lock:
            if key not in cls._instances:
                cls._instances[key] = super(logSave, cls).__new__(cls)
        return cls._instances[key]

    def __init__(self, dir, logname):
        if hasattr(self, '_initialized'):
            return
        self.base_name = logname
        self.dir = os.path.join(exe_dir(), dir, self.base_name)
        self._cur_date = None
        self._lock = threading.Lock()

        self.logger = logging.getLogger(self.base_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        self._ensure_today_handler()
        self._initialized = True

    def _ensure_today_handler(self):
        today = datetime.now().strftime("%Y%m%d")
        if self._cur_date == today and self.logger.handlers:
            return

        # 디렉터리 준비
        os.makedirs(self.dir, exist_ok=True)

        # 기존 핸들러 제거/닫기
        for h in list(self.logger.handlers):
            self.logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        # 오늘 날짜로 파일 열기: logs/<base_name>/<base_name>_YYYYMMDD.log
        filename = os.path.join(self.dir, f"{self.base_name}_{today}.log")
        handler = logging.FileHandler(filename, encoding='utf-8')
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
        self.logger.addHandler(handler)
        self._cur_date = today

    def LogTextOut(self, msg):
        with self._lock:
            self._ensure_today_handler()
            self.logger.info(str(msg))

def load_env_vars(env_path=CONFIG_ENV):
    env = {}
    if not env_path:
        return env

    # ~, %VAR% 확장 + exe 기준 상대경로 보정
    path = os.path.expanduser(os.path.expandvars(env_path))
    if not os.path.isabs(path):
        path = os.path.join(exe_dir(), path)

    if not os.path.exists(path):
        return env  # 파일 없으면 빈 dict

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            # 값의 양쪽 따옴표 제거 + 인라인 주석 제거
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            elif "#" in v:
                v = v.split("#", 1)[0].rstrip()
            env[k] = v
    return env

def now_txt():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def find_nearest_time_row(df: pd.DataFrame):
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).copy()
    now = datetime.now().replace(microsecond=0)
    now_time = now.time()
    df['time_only'] = df['date'].dt.time
    df['diff_sec'] = df['time_only'].apply(
        lambda t: abs(datetime.combine(datetime.min, t) - datetime.combine(datetime.min, now_time)).total_seconds()
    )
    row = df.loc[df['diff_sec'].idxmin()]
    return row, now

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def bias_scale(floor, per_floor_pct):
    """층에 따른 비율 바이어스: 6층을 기준(=1.0)으로 위층↑, 아래층↓"""
    return 1.0 + (floor - 6) * (per_floor_pct / 100.0)

def jitter_mul(pct):
    """±pct% 배율 지터"""
    return 1.0 + random.uniform(-pct, pct) / 100.0

def jitter_add(delta):
    """±delta 값 지터(가/감)"""
    return random.uniform(-delta, delta)