@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo  SRT 字幕校正工具 - 自動安裝並啟動
echo ============================================
echo.

REM ── Step 1：確認 Python ──────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.10 以上版本。
    echo 下載網址：https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python 版本：%PYVER%

REM ── Step 2：建立虛擬環境（若尚未建立）──────────
if not exist "app\env" (
    echo.
    echo [安裝] 建立虛擬環境...
    python -m venv app\env
    if errorlevel 1 (
        echo [錯誤] 建立虛擬環境失敗。
        pause
        exit /b 1
    )
    echo [OK] 虛擬環境建立完成
)

REM ── Step 3：安裝套件（若尚未安裝）──────────────
app\env\Scripts\python.exe -c "import gradio" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [安裝] 安裝必要套件（第一次需要幾分鐘）...
    app\env\Scripts\pip install -r app\requirements.txt
    if errorlevel 1 (
        echo [錯誤] 套件安裝失敗，請確認網路連線。
        pause
        exit /b 1
    )
    echo [OK] 套件安裝完成
) else (
    echo [OK] 套件已安裝，略過
)

REM ── Step 4：確認 LM Studio ─────────────────────
echo.
echo [提示] 請確認 LM Studio 已載入模型並啟動 Local Server（預設 http://localhost:1234）
echo        若尚未啟動，請先開啟 LM Studio 再繼續。
echo.
pause

REM ── Step 5：啟動 ────────────────────────────────
echo [啟動] 開啟 Web UI...
echo        瀏覽器請前往 http://127.0.0.1:7860
echo        關閉此視窗即停止服務
echo.
app\env\Scripts\python.exe app\app.py

pause
