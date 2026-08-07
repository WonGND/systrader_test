# systrader79 Strategy Validation Pipeline

systrader79 블로그(stock79.tistory.com)의 투자 전략 글을 구조화하여,
**해외 자산 기준 2019년 이후 out-of-sample 구간에서 전략이 여전히 유효한지** 판정하는
검증 파이프라인.

> 원문 수익률 재현은 최종 목표가 아니다. 엔진 정합성 검증 수단일 뿐이다.
> 최종 판정 질문은 하나: **"2019년 이후 OOS 구간에서 이 전략이 살아있는가?"**

---

## 시작하기

세션/작업 시작 시 아래 순서로 읽는다.

1. **[`CLAUDE.md`](CLAUDE.md)** — 상시 지침 (절대 규칙, 데이터·백테스트 규약, 판정 기준)
2. **[`docs/STATE.md`](docs/STATE.md)** — 현재 마일스톤과 다음 액션
3. **[`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md)** — 미결 질문

---

## 디렉터리 구조

```
src/crawler/       수집기 (재개 가능, rate-limited)
src/extractor/     원문 → 전략 스펙(JSON) 변환
src/data/          yfinance 어댑터, 유니버스 구성, 로컬 캐시
src/backtest/      엔진, 비용 모델, 성과 지표
src/validate/      인샘플 재현 비교, OOS, 워크포워드, 판정 로직
schemas/           strategy_spec.schema.json
config/            ticker_whitelist.yaml, backtest_defaults
data/raw/          원문 아카이브        (gitignore — 비공개)
data/archive/      원문 아카이브        (gitignore — 비공개)
data/specs/        생성된 전략 스펙 JSON
tests/regression/  자명 케이스 회귀 테스트
reports/           마일스톤별 리포트(한국어)
docs/              STATE / DECISIONS / OPEN_QUESTIONS / data_limitations /
                   needs_image_review / excluded_domestic
```

---

## 스코프 — 해외 전용 트랙 분류

| 트랙 | 코드 | 정의 | 처리 |
|---|---|---|---|
| A | `native_overseas` | 원문이 이미 해외 자산 대상 | M4 인샘플 재현 + M5 OOS |
| B | `ported` | 국내 대상이나 로직이 자산군 독립적 | M5 OOS만 (`port_note` 필수) |
| C | `excluded_domestic_only` | 국내 고유 요소 의존 | 분류만, 백테스트 없음 |

국내(KRX) 시장 백테스트는 수행하지 않는다.

---

## 마일스톤

각 단계 완료 시 **반드시 멈추고 사용자 승인을 기다린다.**

| | 내용 |
|---|---|
| **M1** | 크롤러 + 원문 로컬 아카이브 (재개 가능, 이미지 유무 판별, 인덱스 생성) |
| **M2** | JSON 스키마 확정 + 트랙 분류 + 후보 15개 제시 → 사용자가 10개 확정 |
| **M3** | 백테스트 엔진 + 회귀 테스트 전부 통과 |
| **M4** | 확정 10개 중 **Track A만** 인샘플 재현 + 원문 수치 대비 오차 리포트 |
| **M5** | OOS 확장(2019~현재) + 워크포워드 + 판정 기준 적용 |
| **M6** | 나머지 전략 배치 처리 + 최종 판정 테이블 |

현재 위치는 [`docs/STATE.md`](docs/STATE.md)에서 확인한다.

---

## 판정 기준 v1.0

- **벤치마크**: SPY Buy & Hold (동일 기간·동일 비용 가정, 배당 재투자)
- **OOS 구간**: 2019-01-01 ~ 현재 / **인샘플**: ~2018-12-31

| 조건 | 내용 |
|---|---|
| (1) | OOS Sharpe ≥ 0.5 |
| (2) | OOS MDD ≤ 인샘플 MDD × 1.5 |
| (3) | OOS CAGR ≥ SPY Buy&Hold CAGR |

3충족 `alive` / 2충족 `weak` / 1이하 `dead`
OOS 리밸런싱 12회 미만 → `insufficient_sample` (판정 보류)

---

## 핵심 원칙

1. **추측 금지** — 원문에 없는 파라미터는 채우지 않는다.
   `value: null` + `assumption_needed: true` + 사용자 질문.
2. **근거 필수** — 모든 값 필드는 `source_quote`와 `confidence`를 가진다.
3. **티커 치환은 화이트리스트만** — [`config/ticker_whitelist.yaml`](config/ticker_whitelist.yaml)이
   단일 진실 공급원. 미등재 자산은 임의 치환 금지, 전부 사용자 확인.
4. **엔진 우선** — M3 회귀 테스트 통과 전 실제 전략 백테스트 금지.
5. **생존편향 공시** — yfinance의 상장폐지 데이터 한계는 은폐하지 않는다.
   [`docs/data_limitations.md`](docs/data_limitations.md) 참조.
6. **원문 비공개** — `data/raw/`, `data/archive/`는 커밋하지 않는다.

---

## 데이터

- 단일 소스: **yfinance** (pykrx 미사용)
- 배당 포함 총수익 기준, 기준 통화 **USD**, 환헤지 미고려
- 결측은 보간하지 않고 기록한다
- API 응답은 로컬 캐시에 저장 (재현성 + 호출 절감)

한계 전문은 [`docs/data_limitations.md`](docs/data_limitations.md)에 있다.

---

## 개발 환경

- Windows / PowerShell / Python 가상환경
- 활성화: `.\.venv\Scripts\Activate.ps1`
- 모든 파일 I/O에 `encoding="utf-8"` 명시 (한글 깨짐은 버그로 취급)
- PowerShell에서 `&&` 대신 `;` 사용, 경로는 따옴표로 감싼다
