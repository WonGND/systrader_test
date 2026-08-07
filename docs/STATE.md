# STATE

- 현재 마일스톤: **M0 — 착수 / 구조 조사**
- 다음 액션 1순위: **네트워크 접근 방안 결정 대기** → 확보 후 STEP 3(구조 조사) 재시도 → M1 승인
- 최종 갱신: 2026-08-07

## 체크리스트
- [x] 디렉터리 스캐폴딩 생성
- [x] .gitignore에 data/raw, data/archive 포함
- [x] CLAUDE.md 생성
- [x] config/ticker_whitelist.yaml 생성
- [x] schemas/strategy_spec.schema.json 생성
- [x] docs 뼈대 문서 생성 (DECISIONS / OPEN_QUESTIONS / data_limitations /
      needs_image_review / excluded_domestic / README)
- [ ] 블로그 구조 조사 완료 (robots.txt 확인 포함) — **차단됨 (B-01 참조, 2026-08-07 재시도에서도 동일 403 확인)**
- [x] config/backtest_defaults.yaml 생성 (CLAUDE.md §5 값 그대로, DECISIONS.md 기록)
- [x] requirements.txt 생성
- [x] 원문 파일 3종 정밀 재검증 — 스키마·화이트리스트·CLAUDE.md 핵심 값 31/31 지시서 일치
- [x] M1 실행 계획 제출 → `reports/M0_survey_and_M1_plan.md`
- [ ] **사용자 승인 대기 중**

## 블로커

### B-01. 실행 환경의 아웃바운드 네트워크 정책으로 외부 도메인 접근 불가 (blocking)
- 증상: `stock79.tistory.com:443` CONNECT에 게이트웨이가 403 응답
  (`curl` 오류 56, WebFetch 403).
- 프록시 진단(`$HTTPS_PROXY/__agentproxy/status`)의 `recentRelayFailures`:
  `kind: "connect_rejected"`, `detail: "gateway answered 403 to CONNECT
  (policy denial or upstream failure)"`, `host: "stock79.tistory.com:443"`.
- 범위 확인: `example.com`, `tistory.com`도 동일하게 403.
  `pypi.org`(200), `api.github.com`(200)만 허용됨 → **사이트 측 차단이 아니라
  실행 환경의 네트워크 정책**이다.
- 조치: 우회 시도하지 않음(CLAUDE.md §11, 프록시 README "do not retry
  organization policy denials — report them instead").
- 영향: STEP 3 미수행 → robots.txt / 페이지네이션 / URL 패턴 / DOM 셀렉터 /
  실제 글 수 **전부 미확인**. 추측으로 채우지 않았다.

### B-02. Yahoo Finance 도메인도 동일하게 차단됨 (M3 전제 조건)
- `query1.finance.yahoo.com` 403. yfinance는 이 엔드포인트를 사용한다.
- 영향: 현 환경에서는 M3 회귀 테스트(SPY/IEF 실데이터 대조)와 M5 OOS 실행 불가.
- 단, 합성 시계열 기반 회귀 테스트(상수 수익률 CAGR 검증, 현금 100% 검증,
  비용 반영 방향성, 룩어헤드 탐지)는 네트워크 없이 실행 가능하다.

## 확정된 결정 (v1.1 착수 시점)
- 스코프: 해외 자산 전용. 국내(KRX) 백테스트 미수행
- 데이터: yfinance 단일 소스, USD 기준, pykrx 미사용
- 인샘플/OOS 경계: 2018-12-31 / 2019-01-01
- 벤치마크: SPY Buy&Hold
- 판정 기준: v1.0 (CLAUDE.md §7) — 테스트 중 조정 가능
- M2 대표 전략 선정: 후보 15개(Track A+B) 제시 → 사용자가 10개 확정
- M4 재현 대상: Track A만. Track A < 3개면 축소 실행 + 보조 대조군(사용자 확인)
- 티커 치환: config/ticker_whitelist.yaml 등재 항목만 자동 허용, 그 외 전부 질문

## 미결
- **Q1~Q5** (`docs/OPEN_QUESTIONS.md`) — M1 착수 전 확인 필요
- Track A 실제 개수 → M4 범위 확정 (M2에서 결정)
- 화이트리스트 추가 필요 자산군 (있을 경우, M2에서 결정)

## 다음 세션이 할 일
1. `CLAUDE.md` → 이 문서 → `docs/OPEN_QUESTIONS.md` 순으로 읽는다.
2. B-01 해소 여부를 먼저 확인한다
   (`curl -sS -o /dev/null -w "%{http_code}" https://stock79.tistory.com/robots.txt`).
3. 해소됐으면 STEP 3 구조 조사를 수행하고 결과를
   `reports/M0_survey_and_M1_plan.md`의 "STEP 3 조사 결과"에 채운다.
4. 해소되지 않았으면 Q1 답변에 따라 로컬 실행 경로로 전환한다.
5. **승인 없이 크롤링을 실행하지 않는다.**
