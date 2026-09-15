@echo off
title AgentIA - Microservice Code Studio Launcher
echo ==============================================================================
echo             AgentIA - Microservice Code Studio (Local Launcher)
echo ==============================================================================
echo.
cd /d "%~dp0"

echo [1/2] Iniciando Backend Orchestrator (FastAPI en http://localhost:8000)...
start "AgentIA - Backend Orchestrator (:8000)" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] Esperando inicializacion del backend (3 segundos)...
timeout /t 3 /nobreak >nul

echo [2/2] Iniciando Frontend Studio (Streamlit en http://localhost:8501)...
start "AgentIA - Frontend Studio (:8501)" cmd /k "cd /d "%~dp0" && python -m streamlit run frontend/app.py --server.port 8501"

echo.
echo ==============================================================================
echo Los servicios se estan ejecutando en ventanas dedicadas:
echo.
echo   * Frontend Web UI : http://localhost:8501
echo   * Backend REST API: http://localhost:8000
echo   * Swagger Docs    : http://localhost:8000/docs
echo.
echo Para detener los servicios, simplemente cierra las ventanas de terminal.
echo ==============================================================================
pause

