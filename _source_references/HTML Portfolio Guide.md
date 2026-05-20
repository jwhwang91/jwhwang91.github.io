# 🚀 [Master Context] Vehicle Dynamics & AI Toolchain Architect Portfolio

## 1. 포트폴리오의 본질 및 메인 전략 (Philosophy & Strategy)
*   **핵심 서사 (The T-shaped Engineer):** 단순한 제어 로직 개발자나 파이썬 코더가 아님. **"물리적/하드웨어적 제약(Physical Constraints)을 수학적 로직으로 뚫어내고, R&D 테스트 파이프라인의 병목을 독자적 툴체인(Toolchain) 아키텍처로 창조해 낸 Full-Stack 엔지니어."**
*   **보안 규정(NDA)의 무기화:** 상용 소스 코드는 절대 공개하지 않음. 대신 **"문제 정의(Problem) -> 아키텍처 다이어그램/핵심 수식(Architecture/Math) -> 정량적 결과(Result)"** 구조로 논리를 추상화하여 프로페셔널함 어필.
*   **미국 취업 & 이민 전략 (O-1 Visa Focus):** 
    *   박사 학위가 없어도 SCI 논문(2편), 등록 특허(드라이브라인 토크 추정 등), 방산/양산 실차 적용 실적을 '이민국(USCIS) O-1A 자격 요건 3가지(독창적 기여, 논문 저자, 핵심적 역할)'로 조립하여 스크리닝 돌파.
    *   타겟 인더스트리: 국방(ITAR 제한) 제외 -> Heavy Machinery, Autonomous Trucking, EV Powertrain 스타트업.
    *   핵심 키워드 도배: `Extended Kalman Filter (EKF)`, `XCP Calibration`, `Lock-free IPC`, `Sensorless Control`, `DWARF Parsing`, `AI in the Loop`.
*   **AI 활용의 역이용:** LLM(Claude 등) 사용을 숨기지 않고, "AI Coding Assistant를 도입해 1인 개발로 6개월짜리 아키텍처 구축을 2개월로 압축한 미친 생산성"으로 포장.

## 2. 4-Phase 핵심 프로젝트 테크트리 (Core Narrative Arc)

### Phase 1: Foundation (수학/동역학적 뼈대 구축)
*   **프로젝트:** 이동형 플랫폼 포탑 모션 안정화 제어 (석사 연구)
*   **핵심 가치:** 센서 노이즈와 베이스 모션 외란을 통제하기 위해 **Kalman Filter**와 **TDE(Time Delay Estimation)**를 수학적으로 모델링. 훗날 자율주행 EKF 설계의 근간이 됨.

### Phase 2: Productization (하드웨어 한계 극복 및 실차 양산)
*   **프로젝트:** ADD K2 전차 TCU 국산화 및 실차 튜닝
*   **Problem:** 55톤 전차의 거대 변속기. 원가 및 내구성 문제로 개별 클러치 압력 센서 탑재 불가 (물리적 제약).
*   **Architecture (Math):** 센서리스 환경 극복을 위해 오픈 루프(Open-loop) 제어 한계를 뚫는 **'클러치 Kiss-point EOL 및 실시간 Adaptation 로직'** 직접 구현. 유압/기계 시스템의 동역학 방정식(Newton Iteration) 모델링.
*   **Result:** 국산화 성공 및 기존 ZF TCU 대비 성능 압도.

### Phase 3: Sensor Fusion & Optimization (도메인 병목 파괴)
*   **프로젝트:** HMC 상용차 Lvl2 ADAS (SCC2, ODP/TOS 모듈 개발)
*   **Problem:** 긴 휠베이스로 인한 상용차 특유의 EBS Yawrate 지연 현상 + 비전 센서(Mobileye) 신뢰도 부족. Rule-based 로직 특성상 쏟아지는 오감지 및 테스트 리소스 낭비.
*   **Solution (EKF):** Steering angle 기반 Tire angle 역학과 Yawrate 역학을 퓨전한 **Extended Kalman Filter(EKF)** 적용. 
*   **Solution (Automation):** MATLAB GUI 환경 구축으로 TOS/ODP 모듈 독립 시뮬레이션 배포. 버스 전용차로 실차 테스트 소요 시간 O시간 -> O분 단축.
*   **Result:** 유럽 안전 법규 통과 및 QZ FCEV 양산 차량 탑재 완료.

### Phase 4: Next-Gen Architecture (🔥 메인 필살기)
*   **프로젝트:** XCP/CAN-FD 기반 AI 모델 실시간 실차 우회(Bypass) 검증 플랫폼 설계
*   **Problem:** 양산 ECU에 무거운 AI 모델 탑재 불가. 매번 타겟 빌드 시 발생하는 막대한 시간 낭비. 벤더 종속성(CANape).
*   **Architecture:**
    *   **Auto-Mapping (벤더 종속성 파괴):** 파이썬 `pyelftools`로 ELF(DWARF) 파싱하여 A2L 메모리 주소를 자동 매핑. (고가의 CANape 의존도 탈피).
    *   **Zero Jitter (통신 최적화):** Classic CAN의 한계를 CAN-FD `daq_max_dto=64`로 튜닝하여 1 ODT/cycle로 묶어 타이밍 지터 완전 제거.
    *   **Lock-free IPC (OS 레벨 동역학):** C++(하드웨어 제어/vxlapi)와 Python(ONNX 추론/UI) 병목을 분리하고, 11,360B 크기의 Shared Memory에 `seqlock`을 적용해 원자적 데이터 교환 구축.
*   **Result:** 노트북과 VN1640만으로 실차에서 양산 ECU를 Bypass하여 AI 모델 실시간 2ms Loop time 검증 환경 완성.

## 3. 웹 포트폴리오 구조화 및 호스팅 전략 (Web Structure)

*   **호스팅 플랫폼:** GitHub Pages (가장 상식적이고 전문성 있음) 또는 Vercel/Netlify (드래그 앤 드롭으로 HTML 폴더 통째로 배포 가능).
*   **디렉토리 트리(Tree):**
    ```text
    /my_portfolio
      ├── index.html          (메인 포트폴리오: 아키텍처, 수식, 결과 요약)
      ├── style.css           (메인 디자인)
      └── /projects           (회사에서 추출한 GUI/Log HTML 격리 폴더)
           ├── e2e_gui.html
           └── /assets
    ```
*   **연동 방식 (Hookup):** 메인 `index.html`은 철저히 **카드형 UI**로 정보 밀도를 높이고, 하단에 `<a href="./projects/e2e_gui.html" target="_blank">` 형태로 서브 페이지 링크를 삽입. 면접관의 인지 과부하 방지.

## 4. 특허 및 논문 영문화 (Translation Engineering)
*(O-1 비자 증빙 및 미국 이력서 타겟용 포장)*
*   K2 자동변속기 고장진단 특허: *Advanced Fault Diagnostics and Telemetry System for Heavy-Duty Autonomous/Tracked Vehicles*
*   드라이브라인 토크 추정 논문 (SCI): *Dynamic driveline torque estimation during whole gear shift for an automatic transmission (Mechanism and Machine Theory)*
*   (※ 국내 KCI 논문 및 학회 발표 자료는 웹 포트폴리오 메인에서는 숨기고, O-1 청원서 증빙용 아카이브(Archive)로만 활용.)