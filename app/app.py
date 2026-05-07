"""
app.py — 長文本 SRT 字幕校正工具 Gradio 主介面
支援本地（LM Studio、Ollama）與付費（OpenAI、Google AI Studio、自訂相容端點）
"""
import os
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv, set_key

import corrector
from reader import read_reference_files

# ── 路徑設定 ──────────────────────────────────────────────
APP_DIR = Path(__file__).parent.resolve()
ENV_FILE = APP_DIR / ".env"
DEFAULT_WORK_DIR = str(Path.home())

REF_EXTS = (".pdf", ".txt", ".md", ".docx")
SRT_EXTS = (".srt",)

# ── 算力來源設定 ───────────────────────────────────────────
PROVIDERS = {
    "lmstudio": {
        "label": "🏠 LM Studio（本地）",
        "url": "http://localhost:1234/v1",
        "need_key": False,
        "key_placeholder": "本地模型不需要 API Key",
    },
    "ollama": {
        "label": "🦙 Ollama（本地）",
        "url": "http://localhost:11434/v1",
        "need_key": False,
        "key_placeholder": "本地模型不需要 API Key",
    },
    "openai": {
        "label": "💳 OpenAI ChatGPT（付費）",
        "url": "https://api.openai.com/v1",
        "need_key": True,
        "key_placeholder": "sk-...",
    },
    "google": {
        "label": "💳 Google AI Studio / Gemini（付費）",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "need_key": True,
        "key_placeholder": "AIza...",
    },
    "custom": {
        "label": "🔧 自訂 OpenAI 相容（付費）",
        "url": "",
        "need_key": True,
        "key_placeholder": "你的 API Key",
    },
}

PROVIDER_CHOICES = [(v["label"], k) for k, v in PROVIDERS.items()]
THINKING_MODEL_KEYWORDS = ["deepseek-r1", "qwq", "o1", "o3", "thinking", "reasoner"]

# ── 自訂 CSS：隱藏廣告與頁尾 ──────────────────────────────
CUSTOM_CSS = """
footer, .footer, .gradio-footer, .built-with,
[class*="footer"], [class*="built-with"],
.svelte-byatnx, .api-logo, .show-api {
    display: none !important;
}
.running-warning {
    background: #fff3cd;
    border: 2px solid #ffc107;
    border-radius: 8px;
    padding: 12px 16px;
    font-weight: bold;
    font-size: 1.05em;
    color: #856404;
}
"""

# ── 深色模式切換 JS ───────────────────────────────────────
DARKMODE_JS = """
function toggleDark() {
    document.body.classList.toggle('dark');
    const btn = document.getElementById('darkmode-btn');
    if (btn) btn.innerText = document.body.classList.contains('dark') ? '☀️ 切換為淺色模式' : '🌙 切換為深色模式';
}
"""


# ── 工具函式 ──────────────────────────────────────────────
def _load_env():
    load_dotenv(ENV_FILE, override=True)


def _get_setting(key: str, default: str = "") -> str:
    _load_env()
    if key == "API_BASE_URL" and not os.getenv(key):
        return os.getenv("LMSTUDIO_URL", default)
    if key == "MODEL" and not os.getenv(key):
        return os.getenv("LMSTUDIO_MODEL", default)
    return os.getenv(key, default)


def _list_files(folder: str, exts: tuple) -> list:
    if not folder or not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if Path(f).suffix.lower() in exts)


def _is_thinking_model(model_id: str) -> bool:
    return any(k in model_id.lower() for k in THINKING_MODEL_KEYWORDS)


# ── 事件處理 ──────────────────────────────────────────────
def on_provider_change(provider_key: str):
    p = PROVIDERS.get(provider_key, PROVIDERS["lmstudio"])
    return (
        gr.update(value=p["url"]),
        gr.update(visible=p["need_key"], placeholder=p["key_placeholder"], value=""),
        gr.update(choices=[], value=None),
        gr.update(value=""),
    )


def fetch_model_list(api_base_url: str, api_key: str):
    if not api_base_url:
        return gr.update(choices=[], value=None), "❌ 請先填入 API 端點 URL"
    models = corrector.fetch_models(api_base_url, api_key)
    if not models:
        return gr.update(choices=[], value=None), "❌ 無法取得模型清單，請確認服務已啟動"
    return gr.update(choices=models, value=models[0]), f"✅ 找到 {len(models)} 個模型"


def on_model_change(model_id: str):
    if not model_id:
        return gr.update(value="", visible=False)
    if _is_thinking_model(model_id):
        return gr.update(
            value="⚠️ 偵測到思考型模型！\n"
                  "DeepSeek-R1、QwQ、o1 等模型會輸出大量思考過程，容易破壞 SRT 格式。\n"
                  "建議改用一般指令型模型（如 Gemma 3、Qwen 2.5、Llama 3）。",
            visible=True,
        )
    return gr.update(value="", visible=False)


def pick_work_dir():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(title="選取工作資料夾")
        root.destroy()
        return folder if folder else gr.update()
    except Exception:
        return gr.update()


def test_connection(api_base_url: str, model: str, api_key: str):
    if not api_base_url or not model:
        return "❌ 請先填入 API 端點與模型名稱"
    try:
        from openai import OpenAI
        client = OpenAI(base_url=api_base_url.rstrip("/"), api_key=api_key.strip() or "no-key")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content or ""
        return f"✅ 連線成功！模型回應：{reply[:50]}"
    except Exception as e:
        return f"❌ 連線失敗：{e}"


def save_settings(provider, api_base_url, model, api_key, work_dir, chunk_size):
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "PROVIDER",     provider.strip() if provider else "")
    set_key(str(ENV_FILE), "API_BASE_URL", api_base_url.strip())
    set_key(str(ENV_FILE), "MODEL",        model.strip() if model else "")
    set_key(str(ENV_FILE), "API_KEY",      api_key.strip())
    set_key(str(ENV_FILE), "WORK_DIR",     work_dir.strip())
    set_key(str(ENV_FILE), "CHUNK_SIZE",   str(int(chunk_size)))
    return "✅ 設定已儲存"


def refresh_files(work_dir: str):
    srt_files = _list_files(work_dir, SRT_EXTS)
    ref_files = _list_files(work_dir, REF_EXTS)
    return (
        gr.update(choices=srt_files, value=srt_files[0] if srt_files else None),
        gr.update(choices=ref_files, value=[]),
        f"找到 {len(srt_files)} 個 SRT 檔、{len(ref_files)} 個參考資料",
    )


def run_correction(work_dir, srt_filename, ref_filenames, extra_keywords, progress=gr.Progress()):
    """
    生成器函式：逐步回傳 (output_status, progress_log, running_warning)
    先顯示警告，校正結束後隱藏警告。
    """
    WARN_ON  = gr.update(value="⚠️ 校正進行中，請勿關閉頁面或切換至設定頁！", visible=True)
    WARN_OFF = gr.update(value="", visible=False)

    if not srt_filename:
        yield "❌ 請選擇 SRT 檔案", "", WARN_OFF
        return

    api_base_url = _get_setting("API_BASE_URL")
    model        = _get_setting("MODEL")
    api_key      = _get_setting("API_KEY", "")
    chunk_size   = int(_get_setting("CHUNK_SIZE", str(corrector.CHUNK_SIZE)))

    if not api_base_url or not model:
        yield "❌ 請先在「⚙️ 設定」頁面選擇算力來源並儲存設定", "", WARN_OFF
        return

    srt_path = os.path.join(work_dir, srt_filename)
    if not os.path.isfile(srt_path):
        yield f"❌ 找不到 SRT 檔案：{srt_path}", "", WARN_OFF
        return

    # ── 顯示校正中警告 ──────────────────────────────────
    yield "⏳ 準備中，請稍候...", "", WARN_ON

    progress(0.02, desc="讀取 SRT 檔案...")
    with open(srt_path, "r", encoding="utf-8-sig") as f:
        srt_content = f.read()
    total_lines = srt_content.count("\n")

    # 合併參考資料 + 使用者額外關鍵字
    ref_text = ""
    if ref_filenames:
        progress(0.04, desc="讀取參考資料...")
        ref_paths = [os.path.join(work_dir, fn) for fn in ref_filenames]
        ref_text = read_reference_files(ref_paths)
    if extra_keywords and extra_keywords.strip():
        ref_text += f"\n\n【使用者補充關鍵字】\n{extra_keywords.strip()}"

    log_lines = []
    corrected = None

    try:
        # 逐段校正，每段完成後立即更新進度條與日誌
        for pct, msg, result in corrector.correct_iter(
            api_base_url=api_base_url,
            model=model,
            srt_content=srt_content,
            api_key=api_key,
            ref_text=ref_text,
            chunk_size=chunk_size,
        ):
            log_lines.append(msg)
            progress(pct, desc=msg)
            if result is None:
                # 中間進度：即時更新 UI
                yield "⏳ 校正進行中...", "\n".join(log_lines), WARN_ON
            else:
                # 最後一次 yield 帶有完整結果
                corrected = result

    except ValueError as e:
        yield f"❌ 校正驗證失敗：{e}", "\n".join(log_lines), WARN_OFF
        return
    except Exception as e:
        yield f"❌ 校正錯誤：{e}", "\n".join(log_lines), WARN_OFF
        return

    if corrected is None:
        yield "❌ 未取得校正結果", "\n".join(log_lines), WARN_OFF
        return

    progress(0.98, desc="儲存檔案...")
    stem = Path(srt_filename).stem
    output_name = f"{stem}-已修正.SRT"
    output_path = os.path.join(work_dir, output_name)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(corrected)

    progress(1.0, desc="完成！")
    log_lines.append(f"💾 已儲存：{output_path}")

    result_msg = (
        f"✅ 校正完成！\n"
        f"輸出：{output_path}\n"
        f"原始行數：{total_lines}　→　校正後行數：{corrected.count(chr(10))}"
    )
    # ── 隱藏警告，顯示結果 ──────────────────────────────
    yield result_msg, "\n".join(log_lines), WARN_OFF


# ── UI 建構 ───────────────────────────────────────────────
def build_ui():
    saved_provider   = _get_setting("PROVIDER", "lmstudio")
    saved_url        = _get_setting("API_BASE_URL", PROVIDERS["lmstudio"]["url"])
    saved_model      = _get_setting("MODEL", "")
    saved_api_key    = _get_setting("API_KEY", "")
    saved_work_dir   = _get_setting("WORK_DIR", DEFAULT_WORK_DIR)
    saved_chunk_size = int(_get_setting("CHUNK_SIZE", str(corrector.CHUNK_SIZE)))
    saved_need_key   = PROVIDERS.get(saved_provider, PROVIDERS["lmstudio"])["need_key"]

    with gr.Blocks(title="長文本 SRT 字幕校正工具") as app:
        gr.Markdown(
            "# ✏️ 長文本 SRT 字幕校正工具\n"
            "### 雲端免費 AI 做不到的事——完整校正超長課程字幕\n"
            "自動分段處理、合併輸出，支援 PDF 參考資料校正專有名詞。"
        )

        tabs = gr.Tabs(selected=0)
        with tabs:

            # ══════════════════════════════════════════════
            # 設定頁
            # ══════════════════════════════════════════════
            with gr.Tab("⚙️ 設定", id=0):

                gr.Markdown("### 算力來源")
                provider_dd = gr.Dropdown(
                    label="選擇算力來源",
                    choices=PROVIDER_CHOICES,
                    value=saved_provider,
                )
                url_input = gr.Textbox(
                    label="API 端點 URL",
                    value=saved_url,
                    placeholder="http://localhost:1234/v1",
                )
                api_key_input = gr.Textbox(
                    label="API Key",
                    value=saved_api_key,
                    type="password",
                    placeholder=PROVIDERS.get(saved_provider, PROVIDERS["lmstudio"])["key_placeholder"],
                    visible=saved_need_key,
                )

                gr.Markdown("---")
                gr.Markdown(
                    "#### 模型選擇\n"
                    "點 **🔄 取得模型清單** 自動抓取，再從下拉選單選擇。\n"
                    "> ⚠️ **請勿選擇思考型模型**（DeepSeek-R1、QwQ、o1 等），"
                    "這類模型會輸出大量思考過程，破壞 SRT 格式。"
                )
                with gr.Row():
                    model_dropdown = gr.Dropdown(
                        label="模型",
                        choices=[saved_model] if saved_model else [],
                        value=saved_model if saved_model else None,
                        allow_custom_value=True,
                        scale=4,
                    )
                    fetch_model_btn = gr.Button("🔄 取得模型清單", scale=1)

                fetch_status = gr.Textbox(label="", interactive=False, max_lines=1)
                thinking_warning = gr.Textbox(
                    label="⚠️ 模型警告", value="", interactive=False, lines=3, visible=False,
                )

                with gr.Row():
                    test_btn = gr.Button("🔌 測試連線")
                test_status = gr.Textbox(label="連線狀態", interactive=False, max_lines=2)

                gr.Markdown("---")
                gr.Markdown(
                    "### 分段大小\n"
                    "每段字幕數（建議 100～200）。模型 context 較小或速度慢時請調低。"
                )
                chunk_size_input = gr.Slider(
                    label="每段字幕數", minimum=50, maximum=400, step=10, value=saved_chunk_size,
                )

                gr.Markdown("---")
                gr.Markdown("### 工作資料夾")
                with gr.Row():
                    work_dir_input = gr.Textbox(
                        label="資料夾路徑",
                        value=saved_work_dir,
                        placeholder="點擊右側按鈕選取資料夾",
                        scale=4,
                    )
                    folder_btn = gr.Button("📁 選取資料夾", scale=1)

                gr.Markdown("---")
                gr.Markdown("### 外觀")
                gr.HTML(
                    '<button id="darkmode-btn" onclick="toggleDark(); return false;" '
                    'style="padding:8px 16px; cursor:pointer; border-radius:6px; '
                    'border:1px solid #ccc; font-size:0.95em;">'
                    '🌙 切換為深色模式</button>'
                )

                gr.Markdown("---")
                with gr.Row():
                    save_btn = gr.Button("💾 儲存設定", variant="primary", scale=3)
                    goto_btn = gr.Button("▶️ 前往校正", scale=2)
                save_status = gr.Textbox(label="狀態", interactive=False, max_lines=1)

                # ── 設定頁事件 ─────────────────────────────
                provider_dd.change(
                    on_provider_change, inputs=[provider_dd],
                    outputs=[url_input, api_key_input, model_dropdown, fetch_status],
                )
                fetch_model_btn.click(
                    fetch_model_list, inputs=[url_input, api_key_input],
                    outputs=[model_dropdown, fetch_status],
                )
                model_dropdown.change(
                    on_model_change, inputs=[model_dropdown], outputs=[thinking_warning],
                )
                folder_btn.click(pick_work_dir, outputs=[work_dir_input])
                test_btn.click(
                    test_connection, inputs=[url_input, model_dropdown, api_key_input],
                    outputs=[test_status],
                )
                save_btn.click(
                    save_settings,
                    inputs=[provider_dd, url_input, model_dropdown,
                            api_key_input, work_dir_input, chunk_size_input],
                    outputs=[save_status],
                )

            # ══════════════════════════════════════════════
            # 校正頁
            # ══════════════════════════════════════════════
            with gr.Tab("✏️ 開始校正", id=1):

                # 校正中警告（動態顯示）
                running_warning = gr.Markdown(
                    value="",
                    visible=False,
                    elem_classes=["running-warning"],
                )

                with gr.Row():
                    work_dir_display = gr.Textbox(
                        label="工作資料夾",
                        value=saved_work_dir,
                        scale=4,
                        interactive=False,
                    )
                    refresh_btn = gr.Button("🔄 重新整理", scale=1)

                refresh_status = gr.Textbox(label="資料夾狀態", interactive=False, max_lines=1)

                srt_dropdown = gr.Dropdown(
                    label="選擇 SRT 檔案",
                    choices=_list_files(saved_work_dir, SRT_EXTS),
                    value=None, interactive=True,
                )

                with gr.Row():
                    ref_checkboxgroup = gr.CheckboxGroup(
                        label="選擇參考資料（可不選，選了會依此校正專有名詞）",
                        choices=_list_files(saved_work_dir, REF_EXTS),
                        value=[],
                        scale=3,
                    )
                    extra_keywords = gr.Textbox(
                        label="補充關鍵字（每行一個）",
                        placeholder="例如：\nComfyUI\nPinokio\n縣網中心\n邱文盛老師",
                        lines=6,
                        scale=2,
                    )

                gr.Markdown(
                    "> 📌 校正期間請勿關閉頁面。"
                    "每段等待 AI 回應後才更新進度，可開啟 **工作管理員** 或 "
                    "**LM Studio Log** 確認模型正在運作。"
                )

                correct_btn = gr.Button("🚀 開始校正", variant="primary", size="lg")

                output_status = gr.Textbox(label="校正結果", lines=3, interactive=False)
                progress_log  = gr.Textbox(
                    label="📋 處理進度記錄", lines=10, interactive=False,
                    placeholder="校正開始後會在此顯示各段進度...",
                )

                # ── 跨頁事件 ──────────────────────────────
                # 儲存設定後同步工作資料夾到校正頁
                save_btn.click(
                    lambda d: gr.update(value=d),
                    inputs=[work_dir_input],
                    outputs=[work_dir_display],
                )
                # 前往校正按鈕（不管有沒有儲存都能跳）
                goto_btn.click(
                    fn=lambda: gr.update(selected=1),
                    outputs=[tabs],
                )
                # 儲存成功後自動跳至校正頁
                save_btn.click(
                    fn=lambda: gr.update(selected=1),
                    outputs=[tabs],
                )

                # ── 校正頁事件 ─────────────────────────────
                refresh_btn.click(
                    refresh_files, inputs=[work_dir_display],
                    outputs=[srt_dropdown, ref_checkboxgroup, refresh_status],
                )
                correct_btn.click(
                    run_correction,
                    inputs=[work_dir_display, srt_dropdown, ref_checkboxgroup, extra_keywords],
                    outputs=[output_status, progress_log, running_warning],
                )

    return app


if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="127.0.0.1", theme=gr.themes.Soft(), css=CUSTOM_CSS, js=DARKMODE_JS)
