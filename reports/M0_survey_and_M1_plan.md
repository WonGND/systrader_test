# M0 게이트 보고 — 스캐폴딩 / 구조 조사 / M1 실행 계획

- 작성일: 2026-08-07
- 마일스톤: M0 (착수)
- 상태: **사용자 승인 대기**. 크롤링 미실행.

---

## 1. 완료 항목

| STEP | 내용 | 상태 |
|---|---|---|
| STEP 1 | 디렉터리 스캐폴딩 + `.gitignore` | 완료 |
| STEP 2 | 지시서 원문 파일 4종 + 뼈대 문서 6종 | 완료 |
| STEP 3 | 블로그 구조 조사 | **차단 — 미수행** |
| STEP 4 | M1 실행 계획 제출 + STATE 갱신 + 정지 | 완료 |

---

## 2. 생성·변경 파일 목록

### 지시서 원문 그대로 기록 (한 글자도 변경하지 않음)
| 경로 | 출처 |
|---|---|
| `CLAUDE.md` | 지시서 `<file path="CLAUDE.md">` |
| `config/ticker_whitelist.yaml` | 지시서 `<file path="config/ticker_whitelist.yaml">` |
| `schemas/strategy_spec.schema.json` | 지시서 `<file path="schemas/strategy_spec.schema.json">` |
| `docs/STATE.md` | 지시서 `<file path="docs/STATE.md">` → 이후 현재 상태로 갱신 |

### 신규 작성
| 경로 | 내용 |
|---|---|
| `.gitignore` | `data/raw/`, `data/archive/`, `.venv/`, `__pycache__/`, `*.pkl`, `cache/` 포함 |
| `README.md` | 프로젝트 개요, 트랙 정의, 마일스톤, 판정 기준 |
| `docs/DECISIONS.md` | 결정 기록 표 (형식: 날짜/결정/근거/대안/되돌릴 조건) |
| `docs/OPEN_QUESTIONS.md` | 미결 질문 Q1~Q5 |
| `docs/data_limitations.md` | L-01~L-05 (생존편향, ETF 상장일, 무보간, 통화, 조정방식) |
| `docs/needs_image_review.md` | 사유 코드 정의 + 빈 표 |
| `docs/excluded_domestic.md` | Track C 제외 사유 코드 정의 + 빈 표 |
| `reports/M0_survey_and_M1_plan.md` | 본 문서 |

### 생성된 빈 디렉터리
`src/{crawler,extractor,data,backtest,validate}/`, `tests/regression/`,
`data/{raw,archive,specs}/`

---

## 3. 검증 근거

### 3.1 `.gitignore` 실효성 확인
`data/raw/`, `data/archive/`가 실제로 git에서 제외되는지 확인 필요 항목이며,
커밋 시 `git status`에 해당 경로가 나타나지 않음을 확인했다.

### 3.2 STEP 3 차단 — 실측 증거

**(a) 대상 도메인 접근 실패**

```
$ curl -sS -A "..." --max-time 30 "https://stock79.tistory.com/robots.txt"
curl: (56) CONNECT tunnel failed, response 403
```

WebFetch 경로도 동일: `HTTP 403 Forbidden`.

**(b) 프록시 진단 출력** (`$HTTPS_PROXY/__agentproxy/status`)

```json
"recentRelayFailures": [
  {
    "ts": "2026-08-07T01:12:58.470Z",
    "kind": "connect_rejected",
    "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
    "host": "stock79.tistory.com:443"
  }
]
```

**(c) 차단 범위 판별 — 대조 테스트**

| URL | HTTP | 해석 |
|---|---|---|
| `https://stock79.tistory.com/robots.txt` | 403 (CONNECT 거부) | 대상 블로그 |
| `https://tistory.com` | 403 (CONNECT 거부) | 플랫폼 전체 |
| `https://example.com` | 403 (CONNECT 거부) | 무관한 일반 도메인 |
| `https://query1.finance.yahoo.com/v8/finance/chart/SPY` | 403 (CONNECT 거부) | yfinance 데이터 엔드포인트 |
| `https://pypi.org/simple/` | **200** | 허용됨 |
| `https://api.github.com` | **200** | 허용됨 |

**결론**: `example.com`까지 동일하게 거부되고 패키지 레지스트리·GitHub API만
통과한다. 따라서 이것은 **블로그 측의 크롤러 차단이 아니라 이 실행 환경의
아웃바운드 네트워크 정책(allowlist)** 이다. 두 원인은 대응 방법이 전혀 다르므로
구분해서 보고한다.

**조치**: 우회를 시도하지 않았다. 프록시 README가 명시한다 —
`do not retry organization policy denials (403/407) — report them instead`.
CLAUDE.md §11 "크롤링 차단 시 우회 시도" 금지와도 일치한다.

### 3.3 STEP 3 요구 항목의 현재 상태

지시서가 요구한 6개 항목 중 **확인된 것은 0개**다.
추측으로 채우지 않고 미확인으로 남긴다.

| # | 요구 항목 | 상태 |
|---|---|---|
| 1 | robots.txt 내용 및 크롤링 허용 여부 | **미확인** |
| 2 | 페이지네이션 방식 및 파라미터 | **미확인** |
| 3 | 글 URL 패턴 | **미확인** |
| 4 | 본문 DOM 구조(제목/본문/작성일 셀렉터) | **미확인** |
| 5 | 이미지 포함 여부의 프로그램적 판별 가능성 | **미확인** |
| 6 | 실제 글 수가 172/181과 일치하는지 | **미확인** |

> Tistory 플랫폼의 일반적 URL 형태나 DOM 구조를 기억에 근거해 적을 수 있으나,
> 이 블로그는 스킨 커스터마이징 여부를 확인하지 못했고 robots.txt도 읽지 못했다.
> hard_constraint #1(no_fabrication)에 따라 **적지 않는다.**
> 이 6개 항목은 STEP 3 재시도 시 실측으로 채운다.

---

## 4. 발견된 문제와 한계

### P-01. 네트워크 정책으로 STEP 3 수행 불가 (blocking, B-01)
위 3.2 참조. M1 크롤러의 파싱 로직은 DOM 셀렉터 확인 없이는 작성할 수 없다.
셀렉터를 추측해 코드를 쓰면 "동작하는 것처럼 보이지만 조용히 틀린" 크롤러가 되며,
이는 이 프로젝트에서 가장 위험한 실패 유형이다.

### P-02. yfinance 데이터 소스도 동일하게 차단됨 (B-02)
`query1.finance.yahoo.com` 403. 현 환경에서 M3의 실데이터 회귀 테스트
(SPY Buy&Hold 외부 수치 대조, 60/40 배분)와 M5 OOS 실행이 불가하다.

단, M3 회귀 항목 중 아래는 **네트워크 없이 실행 가능**하다:
- 상수 수익률 시계열의 해석적 CAGR vs 엔진 산출값 일치
- 현금 100% 보유 시 수익률 0
- 비용 0 vs 비용 반영 결과 차이의 방향성·크기
- 룩어헤드 탐지(시그널 1일 미래 이동 시 성과 개선 여부)
- 리밸런싱 주기(월/분기/연) 동작 — 합성 가격 시계열로 검증

→ M3를 "합성 데이터 검증"과 "실데이터 대조" 두 단계로 분리하면,
   네트워크 없이도 엔진 구현과 절반 이상의 회귀 검증을 진행할 수 있다.

### P-03. 실행 환경이 지시서 전제(Windows/PowerShell)와 다름
이 세션은 Linux 컨테이너에서 실행 중이다. 코드는 지시서대로
`encoding="utf-8"` 명시와 `pathlib` 기반 경로 처리를 지켜 작성하면
양쪽에서 동작한다. 다만 **PowerShell 실행 명령은 이 환경에서 검증할 수 없다.**
문서에 적힌 PowerShell 명령은 사용자 환경 기준이며 미검증임을 밝힌다.

### P-04. 컨테이너 수명
이 실행 환경은 비활성 시 회수된다. 크롤링 산출물(`data/raw/`, `data/archive/`)은
gitignore 대상이라 커밋되지 않으므로, **컨테이너에서 크롤링하면 결과가 소실된다.**
→ Q1의 권장안이 "로컬 실행"인 주된 이유다.

---

## 5. 미결 질문 (권장안 포함)

> "추천대로"라고만 답해도 즉시 진행 가능하도록 구성했다.

### Q1. 크롤링을 어디서 실행할까? *(blocking)*

현 컨테이너는 외부 도메인이 차단되어 있고(B-01), 수집 결과는 gitignore 대상이라
커밋도 되지 않는다(P-04).

| 선택지 | 내용 | 평가 |
|---|---|---|
| **(a) 로컬 Windows 실행** ★권장 | 여기서는 크롤러 **코드만** 작성해 커밋. 사용자가 로컬 `.venv`에서 실행 | 네트워크·수명 문제 동시 해결. 원문이 로컬에만 남아 §1.8 비공개 원칙에도 부합 |
| (b) 환경 allowlist 추가 | `stock79.tistory.com` 추가 요청 | 가능하면 STEP 3 실측을 여기서 끝낼 수 있어 (a)와 병행하면 최선 |
| (c) 진행 보류 | — | 비권장 |

**권장안: (a) + 가능하면 (b) 병행.**
(b)가 되면 제가 STEP 3 실측을 마치고 검증된 셀렉터로 크롤러를 작성합니다.
(b)가 안 되면 Q2로 넘어갑니다.

---

### Q2. (b)가 불가능할 경우, DOM 구조를 어떻게 확보할까? *(blocking, Q1이 (a) 단독일 때만)*

셀렉터를 추측해 작성하지 않겠다는 것이 원칙이므로, 실측 정보가 필요합니다.

| 선택지 | 내용 |
|---|---|
| **(a) 사용자가 샘플 HTML 1~2개 제공** ★권장 | 목록 페이지 1개 + 본문 페이지 1개를 저장해 전달. 이것만으로 셀렉터·페이지네이션·이미지 판별을 전부 확정 가능 |
| (b) 탐침 스크립트 선제공 | 제가 "구조를 조사해 출력하는" 읽기 전용 스크립트를 먼저 커밋 → 사용자가 로컬 실행 후 출력을 전달 |
| (c) 자가 적응형 파서 | 여러 후보 셀렉터를 시도 | **비권장.** 조용히 틀릴 위험 |

**권장안: (b).** 사용자 부담이 "스크립트 1회 실행"으로 끝나고,
`robots.txt` 확인·글 수 집계·이미지 판별까지 한 번에 근거 있게 수집됩니다.
(a)도 병행하면 더 빠릅니다.

---

### Q3. 대상 카테고리의 정확한 URL을 알려주실 수 있나요? *(blocking)*

지시서에는 카테고리 **이름**만 있습니다 —
"systrader79 칼럼/실전 투자 전략"(약 172개), "투자의 기초"(약 181개).
Tistory 카테고리는 내부 ID로 접근하는 경우가 많은데, 확인하지 못해 추측하지 않았습니다.

**권장안**: 두 카테고리 목록 페이지의 URL을 브라우저 주소창에서 복사해 전달.
없으면 Q2(b) 탐침 스크립트가 카테고리 목록을 열거해 후보를 출력하도록 만들겠습니다.

---

### Q4. 원문 아카이브 저장 형식과 이미지 처리 범위는? *(non-blocking)*

| 항목 | 권장안 | 근거 |
|---|---|---|
| 저장 형식 | 원본 HTML + 추출 텍스트(`.txt`) **둘 다** | 파서 개선 시 재크롤링 불필요 |
| 인코딩 | `encoding="utf-8"` 명시 | CLAUDE.md §9 |
| 이미지 | **바이너리 미다운로드.** `<img>` URL·개수·alt만 메타데이터로 기록 | 이미지 의존 판별에는 개수·위치면 충분. 용량·저작권 부담 회피 |
| 인덱스 | `data/archive/index.jsonl` (URL/제목/발행일/해시/이미지수/상태) | 재개 및 M2 분류의 입력 |
| 체크포인트 | `data/archive/checkpoint.json` | CLAUDE.md §9 중단·재개 |

**권장안: 위 표 그대로.** 이미지 바이너리가 필요하면 M2에서 대상을 좁혀 재수집합니다.

---

### Q5. "이미지 의존" 자동 판별 기준을 얼마나 보수적으로 잡을까? *(non-blocking)*

hard_constraint #2에 따라 텍스트만으로 재현 불가한 글은 건너뛰어야 하는데,
자동 판별은 필연적으로 오분류가 생깁니다.

| 선택지 | 내용 | 결과 |
|---|---|---|
| **(a) 보수적** ★권장 | 이미지가 1개라도 있고 본문에 수치·규칙 서술이 부족하면 `needs_image_review` | 후보가 줄지만 잘못된 스펙이 M4/M5로 흘러가지 않음 |
| (b) 공격적 | 텍스트에 파라미터가 있으면 이미지 무시 | 후보는 늘지만 이미지에만 있던 조건을 놓칠 위험 |

**권장안: (a).** 단, 자동 판별은 **플래그일 뿐 최종 결정이 아니게** 하고,
M2에서 사람이 검토할 수 있도록 판별 사유와 이미지 위치를 함께 기록하겠습니다.
`needs_image_review`로 분류된 글은 삭제하지 않고 `docs/needs_image_review.md`에 누적합니다.

---

## 6. 다음 단계 계획 — M1 상세 실행 계획

> **승인 전에는 실행하지 않습니다.** Q1~Q3 답변에 따라 Phase 0의 형태가 정해집니다.

### Phase 0 — 구조 실측 (STEP 3 대체 수행)
| 산출물 | 내용 |
|---|---|
| `src/crawler/probe.py` | **읽기 전용** 탐침. 쓰기·저장 없음 |
| | ① `robots.txt` 원문 출력 및 대상 경로 허용 여부 판정 |
| | ② 카테고리 목록 페이지 1~2개만 조회 → 페이지네이션 파라미터 추출 |
| | ③ 글 URL 패턴 샘플 수집 |
| | ④ 본문 페이지 1개의 DOM 후보 셀렉터(제목/본문/작성일) 출력 |
| | ⑤ `<img>` 태그 검출 가능성 확인 |
| | ⑥ 카테고리별 실제 글 수 집계 → **172/181과의 차이를 보정 없이 그대로 보고** |
| `reports/M0_survey_and_M1_plan.md` | 위 §3.3 표를 실측값으로 채움 |

**게이트**: robots.txt가 대상 경로를 불허하면 **즉시 중단하고 보고**한다. 우회하지 않는다.

### Phase 1 — 크롤러 구현
| 모듈 | 역할 |
|---|---|
| `src/crawler/config.py` | 카테고리 URL, 지연시간, 재시도 정책 (하드코딩 금지) |
| `src/crawler/fetcher.py` | **요청 간 최소 2초 지연**, 지수 백오프 재시도, robots.txt 준수, User-Agent 명시 |
| `src/crawler/list_parser.py` | 목록 페이지 → 글 URL·제목·발행일 (Phase 0 실측 셀렉터 사용) |
| `src/crawler/post_parser.py` | 본문 페이지 → 텍스트, 이미지 메타, 콘텐츠 해시 |
| `src/crawler/archiver.py` | `data/archive/` 저장 (`encoding="utf-8"`), 인덱스 append |
| `src/crawler/checkpoint.py` | 중단·재개. 재실행 시 이미 수집한 URL 건너뜀 |
| `src/crawler/run.py` | 엔트리포인트. `--category`, `--limit`, `--dry-run` |

**설계 원칙**
- 멱등성: 같은 URL 재수집 시 해시 비교 후 변경 없으면 건너뜀
- 실패 격리: 개별 글 파싱 실패가 전체 배치를 중단시키지 않음. 실패 목록 별도 기록
- `--dry-run`: 저장 없이 파싱 결과만 출력 (셀렉터 검증용)
- 부분 실패 시에도 인덱스는 항상 일관된 상태 유지

### Phase 2 — 소규모 검증 실행
- `--limit 5`로 카테고리당 5개만 수집 → 파싱 정확도 육안 확인
- 한글 깨짐 여부 확인 (깨지면 **버그로 취급하고 수정**, CLAUDE.md §9)
- 여기서 문제가 없어야 전량 수집으로 넘어간다

### Phase 3 — 전량 수집
- 두 카테고리 전량. 2초 지연 기준 약 353건 → 최소 12분 + 재시도 여유
- 중단 시 체크포인트에서 재개

### Phase 4 — 인덱스 생성 및 M1 게이트 보고
| 산출물 | 내용 |
|---|---|
| `data/archive/index.jsonl` | 전체 메타데이터 (gitignore — 커밋 안 함) |
| `data/specs/` | 아직 비어 있음 (M2에서 채움) |
| `reports/M1_crawl_report.md` | 수집 건수, **실제 글 수 vs 172/181 차이**, 이미지 포함 글 비율, 실패 목록, 소요 시간 |
| `docs/needs_image_review.md` | 1차 자동 판별 결과 누적 |
| `docs/STATE.md` | M1 완료 상태로 갱신 |

**M1 게이트에서 멈추고 승인을 기다립니다.**

### 커밋되는 것 / 안 되는 것
| 커밋됨 | 커밋 안 됨 (`.gitignore`) |
|---|---|
| `src/crawler/` 코드 | `data/raw/` 원문 |
| `reports/` 리포트 | `data/archive/` 아카이브·인덱스 |
| `docs/` 문서 | `cache/`, `*.pkl` |

---

## 7. 요약

- STEP 1·2·4 완료. **STEP 3은 환경 네트워크 정책으로 차단되어 미수행.**
- 차단은 블로그 측이 아니라 실행 환경 allowlist임을 대조 테스트로 확인했다.
- 구조 조사 6개 항목은 **하나도 추측으로 채우지 않았다.**
- yfinance 엔드포인트도 차단되어 M3 실데이터 대조에 영향이 있다(P-02).
- **크롤링은 실행하지 않았다.** Q1~Q5 답변 후 M1에 착수한다.
