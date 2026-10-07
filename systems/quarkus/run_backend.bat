@echo off
title AgentIA - Backend Orchestrator (FastAPI :8000)
echo ======================================================
echo    Iniciando AgentIA Backend Orchestrator (FastAPI)
echo ======================================================
echo Servidor: http://localhost:8000
echo Swagger UI: http://localhost:8000/docs
echo ReDoc: http://localhost:8000/redoc
echo ======================================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
