#

# SensorPublisher MVP (WinForms)


## 구성 요소

### Core 라이브러리
- **EnvConfigLoader**  
  - `config.env` 파일을 로드하여 환경 설정을 관리
- **LogHub**  
  - 이벤트 기반 로그 전달 (UI 스레드 안전)
- **MqttPublisher (MQTTnet 기반)**  
  - MQTT 서버 연결 및 JSON 메시지 발행
- **SelectionState**  
  - 기본 발행 대상(Default Selection)과  
    수동 발행 시 제외 대상(Override) 관리
- **DefaultDataWorker**  
  - Power / Water / Energy 데이터를 주기적으로 자동 발행
- **ManualEmitSession**  
  - 탭별 수동 발행(Start / Stop) 및 발행 횟수 관리

---

### WinForms 애플리케이션
- 좌측 **탭 UI**, 우측 **로그 패널** 구조
- **Default 탭**
  - MQTT 연결
  - 기본 발행 워커(Start / Stop)
  - 기본 발행 대상 프리셋 선택
- **Power / Water / Energy 탭**
  - Start / Stop
  - 단발 발행(Emit Once)
  - 발행 주기(ms) 설정
  - 대상 선택(층 / 구역 / 에너지 ID)
  - 발행 횟수 표시
- 수동 발행이 시작되면  
  → 해당 대상은 **DefaultDataWorker에서 자동 제외**  
  → 수동 발행 종료 시 자동 제외 해제

---

## 실행 방법

1. **Visual Studio 2022 이상**에서  
   `SensorPublisherMVP.sln` 열기
2. 솔루션 탐색기에서  
   **`SensorPublisher.WinForms` 프로젝트를 시작 프로젝트로 설정**
3. `config.env` 파일이 빌드 결과물 옆에 위치하도록 확인
   - 본 MVP에는 `SensorPublisher.WinForms/config.env`가 포함되어 있음
   - 빌드 후 경로 예시  
     ```
     bin\Debug\net8.0-windows\config.env
     ```
   - 또는 `.csproj`에서 *Copy to Output Directory* 설정 사용
4. 실행 (F5)

---

## 참고 사항 / 다음 단계

- 현재 MVP는 **랜덤 값(payload)** 을 발행합니다.
- `SensorCatalog.EnergyIds`는
  - Python의 `sensor_dict` 기반 실제 에너지 ID 목록으로 교체하세요.
- **TLS + CA 인증서**를 사용하는 경우
  - `config.env` 설정 예시:
    ```
    MQTT_PORT=8883
    MQTT_CA_CERT=path/to/ca.crt
    ```
  - TLS를 사용하지 않으면 1883 포트 그대로 사용하면 됩니다.
