@echo off
echo ======================================================
echo    Iniciando AgentIA Backend Orchestrator (FastAPI)
echo ======================================================
cd backend
python -m uvicorn app.main:app --reload --port 8000
pause

