# ✏️ 長文本 SRT 字幕校正工具

**雲端免費 AI 做不到的事——完整校正超長課程字幕。**

自動分段處理、合併輸出，支援 PDF / TXT / DOCX 參考資料校正專有名詞。
不綁定任何 AI 廠商——本地免費或付費 API 皆可，資料完全由你控制。

---

## 功能特色

- **長文本支援**：自動切段送 AI，完成後合併，無字幕數量上限
- **五種算力來源**：LM Studio、Ollama（本地免費）或 OpenAI、Google AI Studio、自訂相容端點（付費）
- **模型自動偵測**：從 API 自動抓取可用模型，下拉選擇不用手動輸入
- **思考型模型警告**：偵測到 DeepSeek-R1、QwQ 等時自動提示
- **參考資料校正**：讀入 PDF 講義或自訂關鍵字，確保專有名詞正確
- **格式嚴格保護**：字幕編號與時間軸一律不動，只改文字內容
- **進度透明**：顯示「第 X/N 段」精確進度，並提示如何確認模型正在運作

---

## 算力來源

### 本地（免費、資料不離開電腦）

| 來源 | 說明 | 預設端點 |
|------|------|----------|
| **LM Studio** | 圖形介面，適合新手 | `http://localhost:1234/v1` |
| **Ollama** | 指令列工具，輕量快速 | `http://localhost:11434/v1` |

**前置步驟：**
- **LM Studio**：[下載](https://lmstudio.ai/) → 載入模型 → 左側 **Local Server → Start Server**
- **Ollama**：[下載](https://ollama.com/) → 終端機執行 `ollama run llama3.2`

推薦繁體中文能力強的模型：`gemma3`、`qwen2.5`、`llama3.2`

---

### 付費 API（效果更穩定，需 API Key）

> ⚠️ **不建議使用免費額度**：免費方案配額有限，容易在校正中途因配額耗盡而失敗。請使用付費計畫。

| 來源 | 建議模型 | API Key 申請 |
|------|----------|--------------|
| **OpenAI ChatGPT** | `gpt-4o`、`gpt-4o-mini` | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Google AI Studio** | `gemini-2.0-flash`、`gemini-1.5-pro` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **自訂 OpenAI 相容** | 依服務商而定 | Azure OpenAI、Groq、OpenRouter 等 |

---

## 安裝方式

### 方法一：使用 Pinokio（最簡單，一鍵安裝）

在 Pinokio 搜尋框貼上此 repo 的 GitHub URL，或執行：

```bash
pterm download https://github.com/vincentchiou/srt-correction
```

然後點擊 **Install** → **Start** → **Open Web UI**

---

### 方法二：不使用 Pinokio（自動安裝腳本）

需先安裝 [Python 3.10+](https://www.python.org/downloads/)

**Windows**：雙擊 `run.bat`，腳本自動偵測環境、安裝套件、啟動服務。

**Mac / Linux**：
```bash
git clone https://github.com/vincentchiou/srt-correction.git
cd srt-correction
chmod +x run.sh && ./run.sh
```

> 第一次執行自動建環境並安裝套件（約 1～3 分鐘），之後直接啟動。

瀏覽器前往 `http://127.0.0.1:7860`

---

## 使用方式

### ⚙️ 設定頁

1. **選擇算力來源**，URL 與端點自動填入
2. 點 **🔄 取得模型清單** 從服務自動抓取，下拉選擇模型
3. 付費來源填入 **API Key**
4. 點 **🔌 測試連線** 確認可正常回應
5. 點 **📁 選取資料夾** 選擇放 SRT 與參考資料的資料夾
6. 調整每段字幕數（預設 150，模型 context 小時請調低）
7. 點 **💾 儲存設定**，自動跳至校正頁

### ✏️ 開始校正頁

1. 點 **🔄 重新整理** 載入資料夾檔案
2. 選擇 `.srt` 檔案
3. （選用）勾選參考資料 PDF／TXT／DOCX
4. （選用）在右側**補充關鍵字**欄位輸入額外術語，每行一個
5. 點 **🚀 開始校正**
6. 頁面頂端出現警告「校正進行中，請勿關閉頁面」
7. 完成後輸出 `原檔名-已修正.SRT` 存於同一資料夾

> 📌 長文本校正需要時間，每段等待 AI 回應後才更新進度。
> 可開啟**工作管理員**確認 Python 正在使用 CPU，或查看 **LM Studio / Ollama 的 Log** 確認模型有在回應。

---

## 工作資料夾結構

```
工作資料夾/
├── 課程字幕.srt          ← 原始 SRT（可多個）
├── 課程講義.pdf          ← 參考資料（可多個）
├── 術語表.txt            ← 自訂詞彙（可選）
└── 課程字幕-已修正.SRT   ← 校正輸出（自動生成）
```

---

## 校正規則

**會修正：**
- ASR 語音辨識錯誤（同音異字、近音誤識）
- 明顯錯別字
- 口語贅詞（就是、然後、那個、這樣子等填充詞）
- 連續重複三次以上的詞語（保留一次）
- 英文專有名詞大小寫（依參考資料為準）

**不會修正：**
- 字幕編號與時間軸
- 說話者刻意重複的強調語句
- 語氣詞（呢、啦、喔）

---

## 相依套件

| 套件 | 用途 |
|------|------|
| `openai>=1.30.0` | 所有算力來源（OpenAI 相容格式） |
| `gradio>=5.0.0` | Web UI |
| `pymupdf>=1.24.0` | PDF 文字擷取 |
| `python-dotenv>=1.0.0` | 設定檔管理 |

---

## Pinokio 使用者

- **重置**：移除虛擬環境重新安裝，解決套件衝突
- **更新套件**：升級所有套件至最新版本
