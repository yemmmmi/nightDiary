# Diary System - Start Script
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Redis (Docker) - 如果容器不存在则创建，已存在则启动
Write-Host "[Redis] Starting Redis via Docker..." -ForegroundColor Yellow
$redisRunning = docker ps --filter name=diary-redis --format "{{.Names}}" 2>$null
$redisExists = docker ps -a --filter name=diary-redis --format "{{.Names}}" 2>$null
if ($redisRunning -eq "diary-redis") {
    Write-Host "[Redis] Already running" -ForegroundColor Gray
} elseif ($redisExists -eq "diary-redis") {
    docker start diary-redis | Out-Null
    Write-Host "[Redis] Container restarted" -ForegroundColor Yellow
} else {
    docker run -d --name diary-redis -p 6379:6379 redis:7-alpine | Out-Null
    Write-Host "[Redis] Container created and started" -ForegroundColor Yellow
}

Write-Host "[Backend] Starting uvicorn..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; & '.\venv\Scripts\python.exe' -m uvicorn app.main:app --reload"

Write-Host "[Frontend] Starting vite..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"

Write-Host "[OK] Redis: localhost:6379  Backend: http://localhost:8000  Frontend: http://localhost:5173" -ForegroundColor Green
