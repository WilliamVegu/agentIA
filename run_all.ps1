# AgentIA - Microservice Code Studio (PowerShell Launcher)
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "            AgentIA - Microservice Code Studio (Local Launcher)" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n[1/2] Iniciando Backend Orchestrator (FastAPI en http://localhost:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptDir\backend'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 3

Write-Host "[2/2] Iniciando Frontend Studio (React/Vite en http://localhost:3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptDir\frontend'; npm run dev"

Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "Servicios iniciados en consolas independientes:" -ForegroundColor Green
Write-Host "  * Frontend Web UI : http://localhost:3000" -ForegroundColor White
Write-Host "  * Backend REST API: http://localhost:8000" -ForegroundColor White
Write-Host "  * Swagger Docs    : http://localhost:8000/docs" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Green

