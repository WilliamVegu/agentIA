@echo off
title AgentIA - Frontend Studio (Streamlit :8501)
echo ======================================================
echo    Iniciando AgentIA Microservice Code Studio (Frontend)
echo ======================================================
echo Interfaz Web: http://localhost:8501
echo ======================================================
cd /d "%~dp0"
python -m streamlit run frontend/app.py --server.port 8501
pause
