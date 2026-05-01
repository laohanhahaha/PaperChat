@echo off
title ChatPDF Launcher

echo ========================================
echo  ChatPDF - Starting...
echo ========================================

echo Starting backend on port 8000...
start "ChatPDF-Backend" cmd /k "cd /d D:\Trae_projects\ChatPDF\backend && ..\chatpdf_venv\Scripts\python run.py"

echo Starting frontend on port 5173...
start "ChatPDF-Frontend" cmd /k "cd /d D:\Trae_projects\ChatPDF\frontend && npm run dev"

echo.
echo ========================================
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo ========================================
