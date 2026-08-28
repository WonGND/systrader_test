# run_local.ps1 — 로컬(Windows/PowerShell) 원스톱 실행 스크립트
#
# 저장소 클론/갱신 → 가상환경 → 의존성 → 회귀 테스트 → M4 실행 → 출력 저장
#
# 사용법:
#   .\scripts\run_local.ps1              # M4 실행 (기본)
#   .\scripts\run_local.ps1 -Task test   # 회귀 테스트만
#
# 가상환경을 "활성화"하지 않고 .venv\Scripts\python.exe 를 직접 호출한다.
# PowerShell 실행 정책(Activate.ps1 차단) 문제를 원천적으로 피하기 위함이다.

param(
    [ValidateSet("m4", "test", "setup")]
    [string]$Task = "m4",
    [string]$BaseDir = "$env:USERPROFILE\Desktop\Python_Lab",
    [string]$Branch = "claude/systrader79-validation-pipeline-18lzzr",
    [string]$RepoUrl = "https://github.com/WonGND/systrader_test.git"
)

$ErrorActionPreference = "Stop"

# --- 한글 출력 인코딩 -------------------------------------------------------
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# --- 사전 점검 --------------------------------------------------------------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[!] git이 없습니다. https://git-scm.com/download/win 에서 설치 후 다시 실행하세요." -ForegroundColor Red
    exit 1
}
$Boot = if (Get-Command python -ErrorAction SilentlyContinue) { "python" }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" }
        else { $null }
if (-not $Boot) {
    Write-Host "[!] Python이 없습니다. https://www.python.org/downloads/ 에서 3.10+ 설치 후 다시 실행하세요." -ForegroundColor Red
    Write-Host "    설치 시 'Add python.exe to PATH' 체크를 꼭 켜세요." -ForegroundColor Yellow
    exit 1
}

# --- 저장소 준비 ------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $BaseDir | Out-Null
$Repo = Join-Path $BaseDir "systrader_test"

if (Test-Path (Join-Path $Repo ".git")) {
    Write-Host "[1/5] 기존 저장소 갱신: $Repo" -ForegroundColor Cyan
    Set-Location $Repo
    git fetch origin $Branch
    git checkout $Branch
    git pull origin $Branch
} else {
    Write-Host "[1/5] 저장소 클론: $Repo" -ForegroundColor Cyan
    git clone -b $Branch $RepoUrl $Repo
    Set-Location $Repo
}

# --- 가상환경 + 의존성 ------------------------------------------------------
$Py = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[2/5] 가상환경 생성" -ForegroundColor Cyan
    & $Boot -m venv .venv
} else {
    Write-Host "[2/5] 가상환경 재사용" -ForegroundColor Cyan
}
Write-Host "[3/5] 의존성 설치 (수 분 소요될 수 있음)" -ForegroundColor Cyan
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r requirements.txt

if ($Task -eq "setup") { Write-Host "`n준비 완료: $Repo" -ForegroundColor Green; exit 0 }

# --- 회귀 테스트 ------------------------------------------------------------
Write-Host "[4/5] 회귀 테스트 (엔진 정상 확인)" -ForegroundColor Cyan
& $Py -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] 회귀 테스트 실패 — 이 출력을 Claude에게 전달하세요. M4는 실행하지 않습니다." -ForegroundColor Red
    exit 1
}
if ($Task -eq "test") { Write-Host "`n회귀 테스트 통과." -ForegroundColor Green; exit 0 }

# --- M4 실행 ----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path (Join-Path $Repo "reports") | Out-Null
$OutFile = Join-Path $Repo "reports\m4_output.txt"
Write-Host "[5/5] M4 인샘플 재현 실행 (첫 실행은 시세 다운로드로 1~3분)" -ForegroundColor Cyan
& $Py -m src.validate.run_m4 --json reports\m4_results.json 2>&1 |
    Tee-Object -FilePath $OutFile

Write-Host "`n출력 저장 위치:" -ForegroundColor Green
Write-Host "  $OutFile"
Write-Host "  $(Join-Path $Repo 'reports\m4_results.json')"
Write-Host "`n위 파일 내용(또는 위 콘솔 출력 전체)을 Claude에게 전달하세요." -ForegroundColor Yellow
