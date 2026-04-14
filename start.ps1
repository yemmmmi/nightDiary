# Diary System - Start Script
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[Backend] Starting uvicorn..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; & '.\venv\Scripts\python.exe' -m uvicorn app.main:app --reload"

Write-Host "[Frontend] Starting vite..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"

Write-Host "[OK] Backend: http://localhost:8000  Frontend: http://localhost:5173" -ForegroundColor Green
