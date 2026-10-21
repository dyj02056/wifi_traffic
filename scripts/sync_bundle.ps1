# backend/dist/data → web-draft/data, frontend/public/data
# contracts/mock    → web-draft/mock, frontend/public/mock
# contracts/golden_scores.json → web-draft/tests/golden_scores.json
# 실행(저장소 루트에서): powershell -ExecutionPolicy Bypass -File scripts\sync_bundle.ps1
#
# [이 파일이 하는 일] sync_bundle.sh와 같은 일을 하는 윈도우 PowerShell 버전.
#   백엔드 번들·mock 번들·정답표를 web-draft와 frontend에 복사한다(복사 대상 폴더는 먼저 지우고 새로 복사).
# $ErrorActionPreference = "Stop": 명령이 실패하면 바로 멈춘다
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "backend\dist\data"
$Mock = Join-Path $Root "contracts\mock"
$Frontend = Join-Path $Root "frontend"

function Copy-Bundle($Src, $Dst) {
    if (Test-Path $Dst) { Remove-Item -Recurse -Force $Dst }
    New-Item -ItemType Directory -Force $Dst | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Src "*") $Dst
    $n = (Get-ChildItem -Recurse -Filter *.json $Dst).Count
    Write-Host "  $Src -> $Dst ($n files)"
}

Write-Host "[sync_bundle]"
if (Test-Path (Join-Path $Dist "meta.json")) {
    Copy-Bundle $Dist (Join-Path $Root "web-draft\data")
    if (Test-Path $Frontend) { Copy-Bundle $Dist (Join-Path $Frontend "public\data") }
} else {
    Write-Host "  backend/dist/data 없음 - 실데이터 번들은 건너뜀 (python pipeline/export_bundle.py 먼저)"
}
Copy-Bundle $Mock (Join-Path $Root "web-draft\mock")
if (Test-Path $Frontend) { Copy-Bundle $Mock (Join-Path $Frontend "public\mock") }
Copy-Item -Force (Join-Path $Root "contracts\golden_scores.json") (Join-Path $Root "web-draft\tests\golden_scores.json")
Write-Host "  contracts/golden_scores.json -> web-draft/tests/golden_scores.json"
