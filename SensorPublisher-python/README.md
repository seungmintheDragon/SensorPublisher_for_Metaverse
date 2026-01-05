# Sensor MQTT Manual Publisher (Python)

본 프로젝트는 **건물 에너지/설비 센서 데이터를 수동 및 자동으로 MQTT로 발행**하기 위한  
Python 기반 GUI 도구입니다.  
기존 BEMS/EMS, 메타버스 에너지 관리 플랫폼, 테스트베드 실증 환경에서  
**센서 데이터 시뮬레이션 및 검증** 목적으로 사용됩니다.

---

## 프로젝트 개요

- Python + Tkinter 기반 GUI 애플리케이션
- MQTT 서버로 Power / Water / Energy 센서 데이터 발행
- **기본 자동 발행(Default Worker)** 과  
  **수동 발행(Manual Override)** 을 동시에 지원
- CSV 시나리오 기반 시간대별 데이터 재현 가능
- 실제 센서 연동 전, 서버·플랫폼·대시보드 검증용으로 활용

---

## 주요 기능

### 1. MQTT 발행
- TLS / 비 TLS MQTT 연결 지원
- QoS / Retain 옵션 설정 가능
- JSON 형식의 센서 데이터 발행
- 토픽 구조 예시:
  - `building/power/F1A`
  - `building/water/F3`
  - `building/energy/F5/1209`

---

### 2. 기본 자동 발행 (Default Worker)
- 설정된 주기(ms)마다 전체 센서 데이터 자동 발행
- **CSV 시나리오 파일 기반**
  - 현재 시각과 가장 가까운 시간(row)을 찾아 값 사용
  - bias / jitter 적용으로 현실적인 데이터 변동 재현
- 기본 발행 대상 선택 가능
  - 층(Floor)
  - 구역(Section)
  - 에너지 센서 ID

---

### 3. 수동 발행 (Manual Override)
- Power / Water / Energy 별 개별 탭 제공
- 특정 센서만 선택하여:
  - 단발 발행(Emit Once)
  - 주기 발행(Start / Stop)
- 수동 발행 중인 센서는
  → **기본 자동 발행에서 자동 제외**
- 수동 발행 종료 시
  → 기본 발행 대상에 자동 복귀

---

### 4. GUI 구성 (Tkinter)
- 좌측 탭 구조
  - Default
  - Power
  - Water
  - Energy
- 우측 로그 패널
  - 실시간 MQTT 발행 로그
  - 오류 / 상태 메시지 확인 가능
- 발행 횟수 카운트 표시

---

## 프로젝트 구조

```
.
├─ main.py            # Tkinter GUI 및 전체 제어 로직
├─ sensor_mqtt.py     # MQTT 연결 및 메시지 발행
├─ defFunc.py         # 공통 유틸 함수
│   ├─ config.env 로딩
│   ├─ CSV 최근 시간 행 탐색
│   ├─ bias / jitter 처리
│   └─ 로그 처리
├─ db.py              # (선택) PostgreSQL DB 저장 로직
├─ config.env         # MQTT 및 환경 설정 파일
└─ csv/
   ├─ power.csv
   ├─ water.csv
   └─ energy.csv
```

---

## 실행 방법

### 1. 환경 준비
```bash
pip install paho-mqtt psycopg2
```

> Python 3.7 이상 권장

---

### 2. 설정 파일 작성 (`config.env`)
```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USER=
MQTT_PASS=
MQTT_CA_CERT=

MQTT_BASE_TOPIC=building
MQTT_QOS=1
MQTT_RETAIN=false
```

---

### 3. 실행
```bash
python main.py
```

---

## CSV 시나리오 파일 설명

- 시간 컬럼을 기준으로 현재 시각과 가장 가까운 데이터 사용
- 컬럼 예시:
  - Power: `inst_kw`, `acc_kwh`
  - Water: `inst_flow`, `acc_flow`
  - Energy: 센서 ID별 값
- bias / jitter 값으로 실제 센서 노이즈 재현

---

## 활용 사례

- MQTT 수신 서버(Spring, Node.js) 부하 테스트
- 대시보드 / 메타버스 플랫폼 실시간 연동 검증
- 실증 테스트베드 사전 시뮬레이션
- 실제 센서 설치 전 데이터 흐름 검증

---

## 향후 개선 방향

- WinForms / .NET 기반 도구로 마이그레이션 (진행 중)
- CSV → DB 시나리오 확장
- 센서 그룹/건물 단위 프리셋 관리
- Docker 기반 실행 환경 제공
- 실시간 그래프 시각화 기능 추가

---
