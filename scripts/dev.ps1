# Inicializa backend (porta 8000) e frontend (porta 5173) para desenvolvimento local.
# Uso:  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "Arquivo .env criado a partir de .env.example. Configure sua chave de IA." -ForegroundColor Yellow
}

$backend = "$root\backend"
if (-not (Test-Path "$backend\.venv")) {
    python -m venv "$backend\.venv"
    & "$backend\.venv\Scripts\python" -m pip install -r "$backend\requirements-dev.txt"
}
$frontend = "$root\frontend"
if (-not (Test-Path "$frontend\node_modules")) {
    Push-Location $frontend; npm.cmd install; Pop-Location
}

Start-Process -WorkingDirectory $backend -FilePath "$backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","app.main:app","--reload","--port","8000"
Start-Process -WorkingDirectory $frontend -FilePath "npm.cmd" -ArgumentList "run","dev"

Write-Host "Backend:  http://localhost:8000/api/docs"
Write-Host "Frontend: http://localhost:5173"
