@echo off
echo ======================================================
echo    Iniciando AgentIA Microservice Code Studio (Legacy Streamlit)
echo    Puerto: 8501
echo ======================================================
python -m streamlit run frontend-legacy/app.py --server.port 8501
pause
