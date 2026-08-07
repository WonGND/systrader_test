# CLAUDE.md — systrader79 Strategy Validation Pipeline

이 문서는 매 세션 시작 시 최우선으로 읽는 상시 지침이다.
이 문서와 충돌하는 판단이 필요하면 임의로 진행하지 말고 사용자에게 묻는다.

## 0. 프로젝트 한 줄 정의
systrader79 블로그의 투자 전략 글을 구조화하여, **해외 자산 기준 2019년 이후
out-of-sample 생존 여부**를 판정한다. 원문 수익률 재현은 엔진 검증 수단이며 목적이 아니다.

## 1. 절대 규칙 (Non-negotiable)
1. **추측 금지**: 원문에 없는 파라미터는 채우지 않는다. `value: null` + `assumption_needed: true` + 사용자 질문.
2. **근거 필수**: 모든 값 필드는 `source_quote`와 `confidence`를 가진다. 인용 없이 채워진 값은 무효다.
3. **이미지 의존 글 제외**: 텍스트만으로 재현 불가하면 `needs_image_review`로 분류하고 진행하지 않는다.
4. **엔진 우선**: 회귀 테스트(M3) 통과 전에는 실제 전략 백테스트를 실행하지 않는다.
5. **생존편향**: point-in-time 유니버스. yfinance 한계는 §4에 따라 반드시 공시한다.
6. **해외 전용**: 국내(KRX) 백테스트는 수행하지 않는다. 트랙 분류는 §3.
7. **티커 치환은 화이트리스트만**: `config/ticker_whitelist.yaml` 외 치환 금지. §3.1 참조.
8. **원문 비공개**: `data/raw/`, `data/archive/`는 커밋하지 않는다.
9. **마일스톤 게이트**: M1~M6 각 단계 완료 시 반드시 멈추고 승인 대기.
10. **한국어 보고**: 설명·보고·질문은 한국어. 코드/필드명/커밋은 영어.

## 2. 디렉터리 구조
- `src/crawler/` 수집기 (재개 가능, rate-limited)
- `src/extractor/` 원문 → 전략 스펙(JSON) 변환
- `src/data/` yfinance 어댑터, 유니버스 구성, 로컬 캐시
- `src/backtest/` 엔진, 비용 모델, 성과 지표
- `src/validate/` 인샘플 재현 비교, OOS, 워크포워드, 판정 로직
- `schemas/` strategy_spec.schema.json
- `config/` ticker_whitelist.yaml, backtest_defaults(비용·체결 규약)
- `data/raw/`, `data/archive/` **(gitignore)**
- `data/specs/` 생성된 전략 스펙 JSON
- `tests/regression/` 자명 케이스 회귀 테스트
- `reports/` 마일스톤별 리포트(한국어)
- `docs/` STATE.md, DECISIONS.md, OPEN_QUESTIONS.md, data_limitations.md,
  needs_image_review.md, excluded_domestic.md

## 3. 스코프 — 해외 전용 트랙 분류
- **Track A `native_overseas`**: 원문이 해외 자산 대상 → M4 재현 + M5 OOS
- **Track B `ported`**: 국내 대상이나 로직이 자산군 독립적 → M5 OOS만. `port_note` 필수
- **Track C `excluded_domestic_only`**: 국내 고유 요소 의존 → 분류만, 백테스트 없음
- 애매하면 Track B로 밀어 넣지 말고 `needs_user_confirm`으로 두고 질문한다.
- M2 후보 15개에는 Track A와 Track B를 **모두** 포함한다(Track A 우선 배치).
- M4 재현 대상은 Track A만. Track A가 3개 미만이면 M4를 축소 실행으로 전환하고
  외부 검증 수치가 존재하는 표준 전략을 보조 대조군으로 추가한다(사용자 확인 후).

### 3.1 티커 치환 규칙
- 단일 진실 공급원: **`config/ticker_whitelist.yaml`**. 매핑을 코드에 하드코딩하지 않는다.
- 화이트리스트 등재 자산군만 자동 치환 → `mapping_source: "whitelist"`
- 미등재 자산(소형주, 섹터, 팩터, 개별 종목 스크리닝, 레버리지/인버스 등)은
  임의 치환 금지 → `needs_user_confirm` + `open_questions`에 권장안과 함께 질문
  → 승인 시 `mapping_source: "user_approved"`, 재사용 가치가 있으면 화이트리스트 추가를 제안
- **유사도 확대 해석 금지.** "코스피 소형주"는 "광의 주식지수"가 아니다. 애매하면 전부 질문.
- 모든 치환은 `strategy.universe.ticker_mapping[]`에 근거와 함께 기록한다.

## 4. 데이터 규약
- 단일 소스: **yfinance**. pykrx는 사용하지 않는다.
- 배당 포함 총수익 기준. 조정 방식(auto_adjust 여부)을 코드와 리포트에 명시한다.
- 기준 통화 USD. 환헤지 미고려. 원화 환산하지 않는다.
- **생존편향 한계(중대)**: yfinance는 상장폐지·티커 변경 이력을 신뢰성 있게 주지 않는다.
  - 개별 종목 유니버스 전략 → `survivorship_risk: "high"`, 리포트에 "상방 과대평가" 명시
  - ETF/지수 기반 전략 우선 검증 (편향 노출 낮음)
  - 청산된 ETF도 동일 문제가 있으므로 유니버스 구성 시점을 기록한다
  - 모든 한계는 `docs/data_limitations.md`에 기록한다. 은폐 금지.
- 결측은 보간하지 않는다. 결측 구간을 기록하고 결과 해석에 반영한다.
- API 응답은 로컬 캐시에 저장한다(재현성 + 호출 절감).
- ETF 상장일 이전 구간은 프록시 지수로 대체하지 않는다. 백테스트 시작일을 늦춘다.

## 5. 백테스트 규약
- 룩어헤드 금지: 시그널 생성 시점과 체결 시점을 명시적으로 분리한다.
- 기본 체결 규약: **익일 시가**(보수적). 원문에 명시가 있으면 그것을 따르고 출처를 기록.
- 비용 기본값(미국 시장, config로 파라미터화, 하드코딩 금지):
  수수료 0%, 편도 슬리피지 0.05%, 거래세 없음. 전부 "가정값"으로 리포트에 표기.
- 필수 지표: CAGR, MDD, Sharpe, 승률, 연도별 수익률, 거래 횟수, 회전율.
- 인샘플/OOS 경계 고정: 인샘플 ~2018-12-31 / OOS 2019-01-01~현재. 전략별 임의 조정 금지.

## 6. 회귀 테스트 (M3 통과 조건)
- SPY 단일 종목 Buy&Hold — 외부 공개 수치와 CAGR/MDD 대조
- 60/40 정적 배분(SPY/IEF) + 리밸런싱 주기별(월/분기/연) 동작
- 상수 수익률 시계열의 해석적 CAGR과 엔진 산출값 일치
- 비용 0 vs 비용 반영 결과 차이의 방향성·크기 검증
- 현금 100% 보유 시 수익률 0 확인
- 룩어헤드 탐지: 시그널을 1일 미래로 밀면 성과가 비현실적으로 개선되는지 확인
- 위 전부 통과 전에는 실제 전략 검증 금지

## 7. 판정 기준 v1.0
- 벤치마크: SPY Buy&Hold (동일 기간·동일 비용 가정)
- (1) OOS Sharpe ≥ 0.5  (2) OOS MDD ≤ 인샘플 MDD × 1.5  (3) OOS CAGR ≥ SPY CAGR
- 3충족 `alive` / 2충족 `weak` / 1이하 `dead`
- OOS 리밸런싱 12회 미만 → 판정 보류, `insufficient_sample`
- 테스트 중 사용자 지시로 조정 가능. 변경 시 버전업 + DECISIONS.md 기록.

## 8. 세션 핸드오프
세션 시작: `CLAUDE.md` → `docs/STATE.md` → `docs/OPEN_QUESTIONS.md` 순으로 읽는다.
세션 종료·마일스톤 승인 시: STATE.md / DECISIONS.md / OPEN_QUESTIONS.md 갱신.
DECISIONS.md 형식: `날짜 | 결정 | 근거 | 검토한 대안 | 되돌릴 조건`

## 9. 개발 환경 (Windows / PowerShell)
- 가상환경: `.\.venv\Scripts\Activate.ps1`
- 모든 파일 I/O는 `encoding="utf-8"` 명시. 한글 깨짐은 버그로 취급한다.
- PowerShell에서 `&&` 대신 `;` 또는 명령 분리. 경로는 항상 따옴표로 감싼다.
- 장시간 작업(크롤링/배치)은 체크포인트 파일로 중단·재개 가능해야 한다.

## 10. 질문 규약
- 질문은 블로킹 시점에 모아서 제시하고, 각각에 **권장안**을 붙인다.
- 사용자가 "추천대로"라고 답하면 즉시 진행 가능한 상태로 만든다.
- 기술적 세부 선택은 스스로 결정하고 DECISIONS.md에 기록한다.

## 11. 하지 말 것
- 원문에 없는 파라미터를 상식으로 보충
- 이미지 안 수치를 "아마 이랬을 것"으로 추정
- 화이트리스트에 없는 티커를 임의 치환
- 회귀 테스트 미통과 상태에서 전략 결과 보고
- 원문 텍스트/이미지를 커밋
- 마일스톤 승인 없이 다음 단계 진행
- 크롤링 차단 시 우회 시도
- 국내 시장 백테스트 실행
- 생존편향 한계를 언급 없이 넘어가기
- Track A 개수를 채우려고 Track C를 Track B로 재분류

# Success Criteria
- [ ] 새 세션이 이 문서만 읽고도 현재 상태와 다음 액션을 파악할 수 있다
- [ ] 모든 전략 스펙이 근거 인용과 confidence를 보유한다
- [ ] 모든 티커 치환이 whitelist 또는 user_approved 출처를 가진다
- [ ] 저장소에 원문 텍스트/이미지가 존재하지 않는다
- [ ] 회귀 테스트 전부 통과 후에만 전략 결과가 생성되었다
- [ ] 모든 결과 리포트에 생존편향 노출 수준이 표기되었다
- [ ] 각 마일스톤이 승인 기록과 함께 종료되었다
