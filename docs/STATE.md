# STATE

- 현재 마일스톤: **M5 — OOS 검증 완료 / 게이트 보고 제출 — 사용자 승인 대기**
  - 보고서: `reports/M5_oos_validation.md` (미결 질문 Q13~Q16, 전부 blocking)
  - **결과: alive 0 / weak 14 / dead 3 / insufficient_sample 0 (17런)**
    - 17런 **전부**가 기준 (3) OOS CAGR ≥ SPY에서 탈락. OOS SPY가 CAGR 17.53%로 이례적 강세
    - (1) Sharpe≥0.5는 14/17, (2) MDD≤인샘플×1.5도 14/17 통과 → "무너지진 않았으나 지수를 못 이김"
    - 위험조정으로 보면 SPY(Sharpe 0.94) 초과 3건(c06 1.19, c02_perm_zc 1.06, c02_aw 0.97),
      17런 전부 SPY(-33.72%)보다 낙폭 얕음 — 판정은 바꾸지 않고 보조 정보로 병기
    - dead 3건: c07(계절성, Sharpe 0.94→0.08 붕괴), c09_spy(MDD 2.5배, 2020 -14.9%),
      c01(기준(2)만 미달 — 잔여분 SHY 라우팅이 2022 채권 급락에 노출)
    - **L-09 신규(중대)**: 발행일이 OOS 안인 글 5개(C2/C6/C7/C8/C9)는 진정한 OOS 아님
  - 구현: `src/validate/run_m5.py` + `src/validate/strategies_m5.py`(C13 이식판)
  - 판정: §7 v1.0, **비용반영 일간 기준**(Q11), 벤치마크 SPY도 동일 비용
  - 실행 방식: 전략별 전체 기간 1회 실행 후 지표를 인샘플/OOS로 절단
    (2019년 재시작 금지 — 경계에서 포지션 강제 청산·가짜 거래 방지)
  - 워크포워드: 롤링 36개월 안정성 점검, **파라미터 재적합 없음**
- M4: **2026-08-31 승인 종결** ("추천대로 진행해줘"). Q9~Q12 전부 권장안 확정.
  보고서: `reports/M4_inSample_reproduction.md`
- M3: **2026-08-26 승인 종결** ("M3 승인할게"). 보고서: `reports/M3_engine_regression.md`
- M4 실행 3차 완료(2026-08-30 로컬, 15런). 결과는 로컬 `reports/m4_results.json`(gitignore)
  - **핵심 단서 1**: 원문(C2) 표의 SPY MDD -50.78%는 SPY의 **월말 기준** 낙폭과 일치.
    일간 기준은 -55.19%(M3 외부 검증) → 원문은 R/월간 산출 (L-06)
  - **핵심 단서 2**: C2 누적수익 1.7262 + CAGR 7.25% ⟹ 약 14.25년 ⟹ 2005-11~2020-02.
    우리 자동 도출 시작일 2005-11-30과 일치. 뒤쪽 14개월이 인샘플 경계 밖 (L-07)
  - **M4가 잡은 결함**: 미배분 잔여 비중을 0% 현금에 두던 구현 → 원문 (72) 예시대로
    유니버스 현금 자산에 가산(C1→SHY, C2→AGG). c01 4.11→4.65%, c02 4.99→6.38%
  - **미해소 격차 2건**: C6(HAA) 7.68% vs 원문 15%, C9 Sharpe 0.64 vs 원문 2.11 주장.
    추측 보정하지 않고 보고서 §4에 그대로 기재
- M4 구현: Track A 9개 전략 + 대조 변형 = 15런, 오프라인 검증 27건 통과 (전체 45/45)
  - 대상: C1, C2(영구/올웨더), C3, C4, C5, C6, C7, C8, C9(SPY/QQQ).
    **C13(ported)은 "재현 불가 — 이식 전략" 사유로 M4 제외** (M5에서는 포함 권장)
  - Track A = 9 ≥ 3 → §3의 축소 실행·보조 대조군 조항 미발동
  - 엔진 내부 루프 numpy 재작성 — 슬리브 런 47배 가속(9.4s→0.20s), 회귀 18건 동작 불변 확인
- M2: **2026-08-26 승인 종결.** 스펙 10건(`data/specs/c*.json`) 확정, 인용 181건 기계 대조,
  스키마 0오류, content_hash 10/10 충전. 보고서: `reports/M2_candidate_selection.md`
- M3 계획: ① 엔진+합성 회귀(원격) ② 실데이터 대조(SPY B&H·60/40, 로컬 실행) — 전부 통과 전
  전략 백테스트 금지
- **M3 회귀 전 항목 통과 — 게이트 승인 대기** (`reports/M3_engine_regression.md`)
  - 합성 11건 + 크롤러 7건 = 18/18 통과
  - 실데이터(로컬): SPY B&H CAGR 10.24%/MDD -55.19% — 공개 SPY 총수익 수치와 일치,
    연도별 수익률 7개 표본 전부 일치. 60/40 월/분기/연 동작·회전율 단조성 확인.
    비용 드래그 -0.015%p = 회전율×비용 이론값과 일치
  - 회귀가 잡은 결함 3건 전부 수정: 리밸런싱 비용 차감 순서, 검증식 매수단가 오류(엔진 무결),
    보유종목 결측 무경고 동결. 합성 시세에 오버나이트 갭 사각지대가 있어 생성기·테스트 보강
- M1: **2026-08-26 승인 종결** ("추천대로"). 353건 아카이브, 172/172·181/181 MATCH,
  실패 0. 보고서: `reports/M1_crawl_report.md` (§7 통계, §8 승인 기록)
- M2 방식(Q6 승인): 2단계 깔때기 — ① 파생 특징(`post_features.jsonl`, 커밋 가능)으로
  1차 스크리닝 → ② 상위 ~30개 본문만 세션에 전달받아 정독 → 후보 15개 표 확정
- 본문 정독 완료(32건) → **후보 15개 확정 제시** (`reports/M2_candidate_selection.md`)
- **Track A 실제 개수 = 12** → M4 축소 실행 불필요 (원문 수치 텍스트 대조 가능 5건)
- **10개 확정(2026-08-26)**: C1~C9+C13, Q7/Q8 승인 → 스펙 JSON 10건 생성 완료
  (`data/specs/c*.json`, 인용 181건 원문 기계 대조, 스키마 검증 0오류)
- (M2 이력) 게이트 종결 완료 — 위 참조
- 최종 갱신: 2026-08-31

## STEP 3 구조 조사 — 완료 (2026-08-26 로컬 탐침 실측)
- robots.txt: 크롤링 **허용** (/guestbook, /manage, /search 등만 불허)
- 글 수: "실전 투자 전략" 172 = 예상 172 **정확 일치**, "투자의 기초" 181 = 예상 181 **정확 일치**
- 두 카테고리는 상위 "systrader79 칼럼"(451)의 하위 카테고리 (451=172+181+1+97 산술 일치)
- 페이지네이션 `?page=N`, 글 URL `/entry/<슬러그>` + 일부 `/N`
- 셀렉터(실측): 제목 `og:title` / 날짜 `article:published_time`(ISO) /
  본문 `.tt_article_useless_p_margin` → `.contents_style` (`.entry-content`는 광고 혼입으로 기각)
- 목록 페이지에 사이드바 위젯 링크 오염(~55 링크 vs 실제 ~28글) → 크롤러가
  반복 링크 필터링 + 172/181 대조 자가 검증
- 상세: `reports/M0_survey_and_M1_plan.md` §3.3

## 체크리스트
- [x] 디렉터리 스캐폴딩 생성
- [x] .gitignore에 data/raw, data/archive 포함
- [x] CLAUDE.md 생성
- [x] config/ticker_whitelist.yaml 생성
- [x] schemas/strategy_spec.schema.json 생성
- [x] docs 뼈대 문서 생성 (DECISIONS / OPEN_QUESTIONS / data_limitations /
      needs_image_review / excluded_domestic / README)
- [x] 블로그 구조 조사 완료 (robots.txt 허용 확인) — 2026-08-26 로컬 탐침 실측으로 해소
- [x] M1 크롤러 구현 (fetcher/list_parser/post_parser/archiver/checkpoint/run)
- [x] 크롤러 오프라인 단위 테스트 6건 통과 (tests/crawler/test_parsers.py)
- [x] config/backtest_defaults.yaml 생성 (CLAUDE.md §5 값 그대로, DECISIONS.md 기록)
- [x] requirements.txt 생성
- [x] 원문 파일 3종 정밀 재검증 — 스키마·화이트리스트·CLAUDE.md 핵심 값 31/31 지시서 일치
- [x] M1 실행 계획 제출 → `reports/M0_survey_and_M1_plan.md`
- [ ] **사용자 승인 대기 중**

## 블로커

### B-01. 원격 세션의 아웃바운드 네트워크 정책으로 외부 도메인 접근 불가 (완화됨)
- **2026-08-26 갱신**: 로컬 실행 경로(Q1 승인)로 우회 불필요해짐. 크롤링·탐침은
  사용자 로컬에서 실행하고 출력만 전달받는다. 원격 세션 자체의 차단은 여전하다
  (yfinance 관련 영향은 B-02 참조).
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
- **Q13~Q16 (`docs/OPEN_QUESTIONS.md` M5 절): M5 게이트 승인 대기 — blocking**
- C6(HAA)·C9 원문 격차 미해소 (추측 보정 금지 원칙에 따라 한계로 기재, M4 보고서 §4)

## 다음 세션이 할 일
1. `CLAUDE.md` → 이 문서 → `docs/OPEN_QUESTIONS.md` 순으로 읽는다.
2. **M5 게이트 승인 여부를 먼저 확인한다.** 미승인이면 M6에 착수하지 않는다(§1-9).
3. 승인 시 M6: ① C10·C12 스펙 작성(원문 인용 기반, 본문은 사용자 로컬에서 전달받음)
   ② 12전략 배치 재실행(M4·M5 동일 코드) ③ Q14 승인 시 발행일 기준 보조 슬라이스
   ④ `reports/M6_final_report.md` — 통합 판정표 + 전략별 1페이지 + 한계(L-01·L-06~L-09).
4. 실행은 사용자 로컬(B-02). 원격은 코드·리포트만.
