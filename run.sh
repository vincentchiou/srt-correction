#!/bin/bash
# SRT 字幕校正工具 - Mac/Linux 自動安裝並啟動

echo "============================================"
echo " SRT 字幕校正工具 - 自動安裝並啟動"
echo "============================================"
echo ""

# ── Step 1：確認 Python ──────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[錯誤] 找不到 python3，請先安裝 Python 3.10 以上版本。"
    echo "Mac 可用：brew install python3"
    echo "Ubuntu 可用：sudo apt install python3 python3-venv"
    exit 1
fi

PYVER=$(python3 --version)
echo "[OK] $PYVER"

# ── Step 2：建立虛擬環境（若尚未建立）──────────────
if [ ! -d "app/env" ]; then
    echo ""
    echo "[安裝] 建立虛擬環境..."
    python3 -m venv app/env
    if [ $? -ne 0 ]; then
        echo "[錯誤] 建立虛擬環境失敗。"
        exit 1
    fi
    echo "[OK] 虛擬環境建立完成"
fi

# ── Step 3：安裝套件（若尚未安裝）──────────────────
app/env/bin/python -c "import gradio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "[安裝] 安裝必要套件（第一次需要幾分鐘）..."
    app/env/bin/pip install -r app/requirements.txt
    if [ $? -ne 0 ]; then
        echo "[錯誤] 套件安裝失敗，請確認網路連線。"
        exit 1
    fi
    echo "[OK] 套件安裝完成"
else
    echo "[OK] 套件已安裝，略過"
fi

# ── Step 4：提示 LM Studio ──────────────────────────
echo ""
echo "[提示] 請確認 LM Studio 已載入模型並啟動 Local Server（預設 http://localhost:1234）"
echo "       若尚未啟動，請先開啟 LM Studio，再按 Enter 繼續。"
read -p "按 Enter 繼續..."

# ── Step 5：啟動 ────────────────────────────────────
echo ""
echo "[啟動] 開啟 Web UI..."
echo "       瀏覽器請前往 http://127.0.0.1:7860"
echo "       按 Ctrl+C 停止服務"
echo ""
app/env/bin/python app/app.py
