@echo off
title Bolão da Cabine do Glória
call .venv\Scripts\activate
streamlit run app.py --server.runOnSave true --server.headless true
pause
