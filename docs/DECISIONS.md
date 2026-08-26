# DECISIONS

기술적·방법론적 결정의 영구 기록. 형식은 CLAUDE.md §8을 따른다.

`날짜 | 결정 | 근거 | 검토한 대안 | 되돌릴 조건`

---

| 날짜 | 결정 | 근거 | 검토한 대안 | 되돌릴 조건 |
|---|---|---|---|---|
| 2026-08-07 | `config/backtest_defaults.yaml` v1.0 생성. 값은 CLAUDE.md §5 명시값 그대로(익일 시가, 수수료 0%, 편도 슬리피지 0.05%, 거래세 0, 인샘플/OOS 경계, SPY 벤치마크). `auto_adjust`는 null로 두고 M3에서 확정 | CLAUDE.md §2가 이 파일을 요구하며 §5가 "config로 파라미터화, 하드코딩 금지"를 명시. 새 값 창작 없음 — 전부 §5 인용 | 엔진 구현 시점(M3)에 생성 — 그 전까지 규약이 문서에만 존재해 코드와 어긋날 위험이 있어 기각 | §5 규약 자체가 사용자 지시로 변경될 때(버전업 동반) |
| 2026-08-07 | **M0 미결 질문 Q1~Q5를 전부 권장안으로 확정** (사용자 답변: "추천대로"). Q1 로컬 Windows에서 크롤링 실행(원격은 코드만) / Q2 읽기 전용 탐침 `probe.py`로 구조 실측 / Q3 탐침이 카테고리 자동 열거 / Q4 HTML+텍스트 병행 저장·이미지 바이너리 미다운로드 / Q5 보수적 이미지 의존 판별+M2 사람 검토 | 원격 환경 네트워크 차단(B-01)과 gitignore로 인한 수집물 소실(P-04). 셀렉터 추측 금지 원칙 | 컨테이너 allowlist 추가 단독(환경 설정 권한 필요), 샘플 HTML 수동 전달 단독(페이지네이션 실측 불가) | 환경 allowlist에 대상 도메인이 추가되면 원격 실측·실행으로 전환 가능 |
| 2026-08-07 | 탐침 `probe.py` 설계 확정: 요청 상한 10회, 요청 간 최소 2초(하향 불가), 모든 URL을 robots.txt 대조 후 요청, robots 불허 시 즉시 중단, 본문 미저장(구조 메타데이터만 출력), 오프라인 selftest 내장 | hard_constraint #5(2초 지연)·CLAUDE.md §11(차단 시 우회 금지). selftest는 네트워크 없는 원격 환경에서 파서 검증 수단 | 상한 없는 전량 열거(과도한 요청), Selenium 동적 렌더링(불필요 복잡도) | 대상 스킨이 JS 렌더링 필수로 확인될 때 |
| 2026-08-07 | `requirements.txt` 추가 (requests, beautifulsoup4, lxml, jsonschema, PyYAML, numpy, pandas, yfinance, pytest; Python ≥3.10) | 재현 가능한 환경 구성. 기술적 세부 선택은 자체 결정 후 기록(CLAUDE.md §10) | conda env / pyproject.toml — 사용자 환경(Windows venv) 기준 requirements.txt가 가장 단순 | 패키지 충돌 발생 시 버전 핀 고정으로 전환 |

---

## 기록 규칙
- 사용자 승인이 필요한 결정은 승인 확인 후에만 기록한다.
- 판정 기준(CLAUDE.md §7) 변경 시 버전을 올리고 여기에 반드시 남긴다.
- 화이트리스트(`config/ticker_whitelist.yaml`) 항목 추가는 전부 여기에 기록한다.
