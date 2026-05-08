"""
corrector.py — 分段校正 SRT 字幕
支援所有 OpenAI 相容 API：LM Studio、Ollama、OpenAI、Google AI Studio、自訂端點

最佳化：只傳文字給模型（去除時間軸），回傳後由程式補回，
可節省約 50% output token，大幅提升校正速度。
"""
import re

from openai import OpenAI

# 每段最多處理幾個字幕（避免超過模型 context 長度）
CHUNK_SIZE = 150
# 參考資料最多傳入字數
MAX_REF_CHARS = 6000


# ── System Prompt（前半段） ───────────────────────────────────
_PROMPT_HEAD = """你是繁體中文字幕校對專家，專門處理台灣教師研習的 ASR 語音辨識字幕。

【絕對保護的人名與機構名稱】
以下名稱必須完整保留，禁止任何更改：
- 邱文盛老師（或邱老師）
- 縣網中心
- 其他在參考資料中出現的講師姓名、單位名稱，均依參考資料為準

"""

# ── System Prompt（後半段，純文字模式）───────────────────────────────────
_PROMPT_TAIL = """
【AI 科技工具與平台（保留英文原始大小寫）】
對話型 AI／模型：
- ChatGPT、GPT-4o、GPT-4、GPT-3.5、o1、o3
- Claude、Claude 3.5 Sonnet、Claude 4、Anthropic
- Gemini、Gemini 2.0 Flash、Gemini 1.5 Pro、Google DeepMind
- LLaMA、LLaMA 3、Meta AI
- Mistral、Mixtral
- DeepSeek、DeepSeek-V3、DeepSeek-R1
- Qwen（通義千問）、Qwen 2.5
- Phi-3、Phi-4（Microsoft）
- Grok（xAI）

圖像生成：
- Stable Diffusion、SDXL、FLUX
- Midjourney
- DALL-E 3
- Sora、Runway、Kling（可靈）、即夢

影音處理：
- Whisper（OpenAI 語音辨識）、WhisperX
- ElevenLabs（語音合成）
- HeyGen（AI 換臉影片）

開發工具／平台：
- ComfyUI、Automatic1111（A1111）
- Pinokio
- LM Studio
- Ollama
- Cursor、GitHub Copilot、Codeium
- Hugging Face
- Perplexity
- Claude Code
- n8n、Make（自動化流程）
- Zapier

公司名稱：
- OpenAI、Anthropic、Google、Meta、Microsoft、NVIDIA、AMD
- Hugging Face、Stability AI、Mistral AI、xAI
- 台灣 AI 新創：ASUS（華碩）、Acer（宏碁）、TSMC（台積電）、MediaTek（聯發科）

【AI 中文術語對照（ASR 容易誤識）】
以下為正確繁體中文用法：
- 提示詞工程（Prompt Engineering）→ 非「提示詞工成」
- 生成式 AI（Generative AI）→ 非「生成市 AI」
- 大型語言模型（LLM）→ 非「大型語言模特兒」
- 向量資料庫（Vector Database）
- 檢索增強生成（RAG）
- 微調（Fine-tuning）→ 非「微條」
- 幻覺（Hallucination，指 AI 產生錯誤資訊）
- 多模態（Multimodal）
- 嵌入（Embedding）→ 非「嵌入式」（除非確實指嵌入式系統）
- 工作流程（Workflow）
- 代理（Agent）→ 非「代劑」
- 上下文（Context）→ 非「上下文件」
- 權重（Weight）→ 在 AI 語境中，非「重量」
- 模型量化（Quantization）→ 非「量子化」
- Token（不翻譯）→ 非「土肯」
- GPU、VRAM、CUDA（全大寫，不翻譯）
- API、MCP、RAG、LoRA（全大寫縮寫，不翻譯）
- 神經網路（Neural Network）→ 非「神經網絡」（台灣慣用「網路」）
- 自然語言處理（NLP）
- 電腦視覺（Computer Vision）
- 強化學習（Reinforcement Learning）

【輸入與輸出格式】
- 輸入格式：[序號]\n字幕文字（可多行）
- 輸出格式：與輸入完全相同的 [序號]\n校正後文字
- 各條目之間以空行分隔
- 時間軸由程式自動處理，你只需輸出文字

【嚴格規則】
1. 禁止新增、刪除或合併任何條目，每個 [序號] 都必須出現在輸出中
2. 序號 [N] 原樣保留，不可更改
3. 只校正文字內容
4. 參考資料中的專有名詞請照原樣使用
5. 全部使用繁體中文輸出，禁止出現簡體字
6. 不要顯示思考過程，直接輸出校正後的內容，不加任何說明或標題

【可修正的範圍】
- ASR 語音辨識錯誤（同音異字、近音誤識）
- 明顯的錯別字
- 口語贅詞（就是、然後、那個、這樣子、對不對、呃、嗯等填充詞，在不影響句意的情況下可刪除）
- 連續重複三次以上的同一詞語（保留一次即可）
- 英文專有名詞的正確寫法（依上方對照表及參考資料為準）

【禁止修正的範圍】
- 說話者刻意重複的強調語句
- 人名、機構名（見上方保護清單）

直接輸出校正後的完整內容，各條目之間以空行分隔，不加任何說明。"""

SYSTEM_PROMPT = _PROMPT_HEAD + _PROMPT_TAIL


def fetch_models(api_base_url: str, api_key: str = "") -> list[str]:
    """從 API 端點取得可用模型清單。"""
    try:
        client = OpenAI(
            base_url=api_base_url.rstrip("/"),
            api_key=api_key.strip() or "no-key",
        )
        models = client.models.list()
        return sorted([m.id for m in models.data])
    except Exception:
        return []


def _parse_blocks(srt_text: str) -> list:
    """將 SRT 文字拆分為字幕區塊列表。"""
    raw_blocks = re.split(r"\n{2,}", srt_text.strip())
    return [b.strip() for b in raw_blocks if b.strip()]


def _split_chunks(blocks: list, chunk_size: int) -> list:
    """將字幕區塊均分為若干段。"""
    return [blocks[i: i + chunk_size] for i in range(0, len(blocks), chunk_size)]


def _strip_markdown_fence(text: str) -> str:
    """移除模型可能回傳的 Markdown code fence。"""
    text = re.sub(r"^```[^\n]*\n", "", text.strip())
    text = re.sub(r"\n```$", "", text.strip())
    return text.strip()


def _extract_text_only(blocks: list) -> tuple[str, dict]:
    """
    從 SRT 區塊提取純文字（去除時間軸）。
    回傳：(傳給模型的文字字串, {序號: 時間軸} 對照表)
    """
    timestamp_map = {}
    text_parts = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        seq = lines[0].strip()
        if len(lines) >= 3 and "-->" in lines[1]:
            # 標準 SRT 格式：序號、時間軸、文字
            timestamp_map[seq] = lines[1].strip()
            text = "\n".join(lines[2:]).strip()
        elif len(lines) >= 2:
            # 缺少時間軸的異常格式，盡力處理
            timestamp_map[seq] = ""
            text = "\n".join(lines[1:]).strip()
        else:
            continue
        text_parts.append(f"[{seq}]\n{text}")
    return "\n\n".join(text_parts), timestamp_map


def _reassemble_srt(original_blocks: list, corrected_text: str, timestamp_map: dict) -> list:
    """
    將模型回傳的 [序號]\n文字 格式，與原始時間軸合併，重建完整 SRT 區塊。
    若某序號未出現在模型輸出中，保留原始區塊。
    """
    # 解析模型輸出的 [N]\n文字 格式
    corrected_map = {}
    pattern = re.compile(r'\[(\d+)\]\s*\n(.*?)(?=\n\s*\[\d+\]|\Z)', re.DOTALL)
    for m in pattern.finditer(_strip_markdown_fence(corrected_text)):
        corrected_map[m.group(1).strip()] = m.group(2).strip()

    result = []
    for block in original_blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        seq = lines[0].strip()
        timestamp = timestamp_map.get(seq, "")
        if seq in corrected_map and timestamp:
            result.append(f"{seq}\n{timestamp}\n{corrected_map[seq]}")
        else:
            # 找不到對應序號或無時間軸，保留原始
            result.append(block.strip())
    return result


def _correct_chunk(
    client: OpenAI,
    model: str,
    chunk_blocks: list,
    ref_text: str,
) -> list:
    """
    將一段字幕（純文字模式）送給 API 校正，回傳校正後的 SRT 區塊列表。
    去除時間軸後送出，可節省約 50% output token。
    """
    text_only, timestamp_map = _extract_text_only(chunk_blocks)

    user_content = ""
    if ref_text.strip():
        truncated = ref_text[:MAX_REF_CHARS]
        if len(ref_text) > MAX_REF_CHARS:
            truncated += "\n...(參考資料截斷)"
        user_content += f"【參考資料】\n{truncated}\n\n"
    user_content += f"【待校正字幕】\n{text_only}"
    # /no_think 讓 Qwen3 系列在 chat template 層關閉思考模式
    user_content += "\n/no_think"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    base_params = dict(model=model, messages=messages, temperature=0.1, max_tokens=8192)

    # 依序嘗試停用思考模式（不同模型支援不同格式）
    response = None
    for extra_body in [
        {"chat_template_kwargs": {"enable_thinking": False}},  # Qwen3 / LM Studio
        {"thinking": {"type": "disabled"}},                    # Anthropic
    ]:
        try:
            response = client.chat.completions.create(**base_params, extra_body=extra_body)
            break
        except Exception:
            continue

    if response is None:
        # 標準呼叫（不帶任何思考控制參數）
        response = client.chat.completions.create(**base_params)

    raw = response.choices[0].message.content or ""
    return _reassemble_srt(chunk_blocks, raw, timestamp_map)


def correct_iter(
    api_base_url: str,
    model: str,
    srt_content: str,
    api_key: str = "",
    ref_text: str = "",
    chunk_size: int = CHUNK_SIZE,
):
    """
    Generator 版校正函式，每段完成後 yield 一次，讓 UI 即時更新。
    每次 yield: (進度比例 0~1, 訊息字串, 最終結果或 None)
    最後一次 yield 的第三個值為完整 SRT 字串。
    """
    client = OpenAI(
        base_url=api_base_url.rstrip("/"),
        api_key=api_key.strip() or "no-key",
    )

    blocks = _parse_blocks(srt_content)
    original_count = len(blocks)
    chunks = _split_chunks(blocks, chunk_size)
    total_chunks = len(chunks)

    yield 0.05, f"📋 共 {original_count} 個字幕，分成 {total_chunks} 段處理", None

    corrected_blocks = []

    for i, chunk in enumerate(chunks):
        seg_num   = i + 1
        seg_start = i * chunk_size + 1
        seg_end   = min((i + 1) * chunk_size, original_count)
        pct_start = 0.10 + 0.85 * (i / total_chunks)
        pct_end   = 0.10 + 0.85 * ((i + 1) / total_chunks)

        yield pct_start, f"🔄 第 {seg_num}/{total_chunks} 段（字幕 {seg_start}～{seg_end}）...", None

        corrected_chunk = _correct_chunk(client, model, chunk, ref_text)
        corrected_blocks.extend(corrected_chunk)

        yield pct_end, f"✅ 第 {seg_num}/{total_chunks} 段完成", None

    # 驗證字幕數量
    result = "\n\n".join(corrected_blocks) + "\n"
    result_count = len(_parse_blocks(result))
    deviation = abs(result_count - original_count) / max(original_count, 1)
    if deviation > 0.05:
        raise ValueError(
            f"校正結果異常：原始 {original_count} 個字幕，"
            f"校正後 {result_count} 個，偏差 {deviation:.1%}（超過 5%）。\n"
            f"建議縮小每段字幕數（目前 {chunk_size}），或確認模型有正確遵守格式規則。"
        )

    yield 0.97, "💾 合併完成，準備儲存...", result
