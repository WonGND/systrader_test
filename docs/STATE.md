# STATE

- 현재 마일스톤: **M6 — 배치 / 최종 리포트 (진행 중)**
  - **다음 액션(사용자)**: C10·C12 원문 전달 (§미결 W16). 현재 PC에는 M1 아카이브가
    없으므로(인덱스 0건 — M1은 회사 PC에서 실행) **두 글만 재수집 후 번들 생성**:
    `python -m src.crawler.run --category strategy --from-shortlist "Larry Connors" "Defense First"`
    → `python -m src.extractor.make_bundle --match "Larry Connors" "Defense First" --out m6_bundle.txt`
    → `data/archive/m6_bundle.txt` 내용 전달 (저장소 커밋 금지)
  - 구현 완료: `src/validate/run_m6.py`(배치 + 발행후 보조 슬라이스 + 통합 판정표),
    `src/validate/strategies_m6.py`(C10·C12 삽입 지점), `make_bundle --match/--out`
  - 남은 작업: C10·C12 스펙 작성 → 빌더 구현 → 로컬 배치 실행 → `reports/M6_final_report.md`
- M5: **2026-08-31 승인 종결** ("추천대로 진행해줘"). Q13~Q16 전부 권장안 확정.
  보고서: `reports/M5_oos_validation.md`
  - **결과: alive 0 / weak 14 / dead 3 / insufficient_sample 0 (17런)**
  - 17런 **전부** 기준 (3) OOS CAGR ≥ SPY에서 탈락 (OOS SPY CAGR 17.53%)
  - (1) Sharpe≥0.5 14/17, (2) MDD≤인샘플×1.5 14/17 → "무너지진 않았으나 지수를 못 이김"
  - dead 3: c07(계절성 Sharpe 0.94→0.08 붕괴), c09_spy(MDD 2.5배), c01(기준(2)만 미달)
  - **L-09(중대)**: 발행일이 OOS 안인 글 5개(C2/C6/C7/C8/C9)는 진정한 OOS 아님
  - C11·C14·C15 정식 제외 확정, 미정독 코스닥 14건은 `unclassified_out_of_scope` 공시
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
- 최종 갱신: 2026-08-31 (M6 착수)

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
- [x] M1~M5 게이트 전부 승인 종결 (M1·M2·M3 2026-08-26, M4·M5 2026-08-31)
- [x] M6 배치 러너 구현 (`run_m6.py`, 발행후 보조 슬라이스 + 통합 판정표)
- [ ] C10·C12 스펙 작성 (원문 전달 대기 — W16)
- [ ] M6 배치 로컬 실행 → `reports/M6_final_report.md` → 최종 게이트 승인

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
- **W16: C10·C12 원문 전달 대기** (`make_bundle --match ...`) — 스펙 작성의 전제
- C6(HAA)·C9 원문 격차 미해소 (추측 보정 금지 원칙에 따라 한계로 기재, M4 보고서 §4)
- 미정독 코스닥 계열 14건 `unclassified_out_of_scope` (Q15로 범위 밖 확정, 공시 완료)

## 다음 세션이 할 일
1. `CLAUDE.md` → 이 문서 → `docs/OPEN_QUESTIONS.md` 순으로 읽는다.
2. 사용자가 전달한 **m6 번들**(C10·C12 본문)이 있는지 확인한다.
3. 있으면: 두 글 정독 → 스펙 JSON 2건 작성(인용 기계 대조·스키마 검증) →
   `strategies_m6.PENDING_BUILDERS`에 빌더 추가 → 로컬 배치 실행 요청.
4. 없으면: `make_bundle --match "Larry Connors" "Defense First" --out m6_bundle.txt` 실행 요청.
5. 배치 출력 수신 후 `reports/M6_final_report.md` 작성 —
   통합 판정표 + 전략별 1페이지 + 가정값 전수 + 한계(L-01·L-06~L-09) → 최종 게이트 승인 요청.
