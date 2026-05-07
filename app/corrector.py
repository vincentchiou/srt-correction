"""
corrector.py — 分段校正 SRT 字幕
支援所有 OpenAI 相容 API：LM Studio、Ollama、OpenAI、Google AI Studio、自訂端點
"""
import re
from pathlib import Path

from openai import OpenAI

# 每段最多處理幾個字幕（避免超過模型 context 長度）
CHUNK_SIZE = 150
# 參考資料最多傳入字數
MAX_REF_CHARS = 6000

# 本機社群名單檔案（已加入 .gitignore，不會上傳 GitHub）
_NAMES_FILE = Path(__file__).parent / ".community_names"


def _community_names() -> str:
    """
    從本機 .community_names 讀取社群教師名單。
    回傳格式化字串；檔案不存在或為空時回傳空字串。
    名單會放入 user message（非 system prompt），避免撐爆 context。
    """
    if not _NAMES_FILE.exists():
        return ""
    lines = _NAMES_FILE.read_text(encoding="utf-8").splitlines()
    names = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    if not names:
        return ""
    return "【社群教師名單（請保護以下人名，勿誤改）】\n" + "、".join(names)


# ── System Prompt（前半段） ───────────────────────────────────
_PROMPT_HEAD = """你是繁體中文字幕校對專家，專門處理台灣教師研習的 ASR 語音辨識字幕。

【絕對保護的人名與機構名稱】
以下名稱必須完整保留，禁止任何更改：
- 邱文盛老師（或邱老師）
- 縣網中心
- 其他在參考資料中出現的講師姓名、單位名稱，均依參考資料為準

【台灣教育／科技 AI 領域知名人士】
以下人名為正確寫法，ASR 容易誤識，請依此校正：

▍政府與政策
- 唐鳳（數位發展部部長，英文名 Audrey Tang）
- 鄭英耀（教育部部長）
- 陳良基（前教育部長、前科技部長）
- 潘文忠（前教育部長）
- 吳清山（前教育部長，國家教育研究院）
- 廖俊智（中央研究院院長，台灣人工智慧學校董事長）

▍大學教授（AI／資訊科技領域）
- 李宏毅（台大資訊工程系，深度學習／機器學習 YouTube 課程著名）
- 葉丙成（台大電機系，PaGamO 遊戲化學習，翻轉教室推手）
- 廖世偉（台大資訊工程系，區塊鏈／AI）
- 陳信希（台大資訊工程系，自然語言處理）
- 陳縕儂（台大資訊工程系，機器學習）
- 蔡炎龍（政治大學統計系，AI 教育推廣）
- 吳毅成（陽明交大資訊工程系，AI 遊戲）
- 吳漢銘（輔仁大學，資料科學）
- 蔡芸琤（台師大科技系，STEAM／創客教育）
- 孫春在（清華大學，數位學習）
- 桑慧敏（清華大學，AI 教育）
- 楊朝棟（逢甲大學，AI 應用）
- 溫明輝（輔仁大學，AI 醫療）

▍台灣人工智慧學校
- 陳昇瑋（台灣人工智慧學校創辦人暨首任執行長，已辭世）
- 陳伶志（台灣人工智慧學校現任執行長）
- 魏澤人（AI 學校技術領袖講師）
- 林彥宇（AI 學校技術領袖講師）

▍AI／國際科技
- 李開復（創新工場，著有《AI 新世界》）
- 吳恩達（Andrew Ng，Coursera／deeplearning.ai 創辦人）
- 黃仁勳（Jensen Huang，NVIDIA 執行長）
- 郭台銘（鴻海創辦人，科技教育相關）

▍教育改革與創新教學社群
- 張輝誠（學思達教學法創始人）
- 王政忠（MAPS 教學法，南投爽文國中）
- 林怡彣（閱讀教育推廣）
- 曾明騰（Super 教師，理化教學）
- 盧駿逸（教育改革）
- 劉繼文（科技領域教師社群）

▍國中小科技教育社群
- 張煥泉（國小科技教育）
- 林怡瑄（新竹科學園區實驗中學）
- 蘇淑菁（師大，AI 跨域教師培育）

若字幕中出現近似讀音但有誤的人名，請依參考資料或上下文語意判斷並修正。

"""

# ── System Prompt（後半段） ───────────────────────────────────
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

【嚴格規則】
1. 禁止縮減、合併或刪除任何字幕編號與時間軸
2. 每個字幕的格式必須完全保留：「編號」一行、「時間軸」一行、「文字」一行（或多行），各字幕之間以空行分隔
3. 只修正文字內容；時間軸與編號一字不差地原樣保留
4. 參考資料中的專有名詞請照原樣使用
5. 全部使用繁體中文輸出，禁止出現簡體字
6. 不要顯示思考過程，直接輸出校正後的 SRT，不加任何說明或標題

【可修正的範圍】
- ASR 語音辨識錯誤（同音異字、近音誤識）
- 明顯的錯別字
- 口語贅詞（就是、然後、那個、這樣子、對不對、呃、嗯等填充詞，在不影響句意的情況下可刪除）
- 連續重複三次以上的同一詞語（保留一次即可）
- 英文專有名詞的正確寫法（依上方對照表及參考資料為準）

【禁止修正的範圍】
- 說話者刻意重複的強調語句
- 時間軸格式（00:00:00,000 --> 00:00:00,000）
- 字幕編號（純數字行）
- 人名、機構名（見上方保護清單）

直接輸出修正後的完整 SRT 字幕，不要加任何說明、標題或 Markdown 格式。"""

# system prompt 不含社群名單（名單在 user message 注入，避免超出 context）
SYSTEM_PROMPT = _PROMPT_HEAD + _PROMPT_TAIL

# 社群名單快取（模組載入時讀一次）
_NAMES_CACHE: str = _community_names()


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


def _extract_srt_from_response(text: str) -> str:
    """從模型回應中擷取 SRT 內容，忽略前後多餘說明。"""
    text = _strip_markdown_fence(text)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().isdigit():
            return "\n".join(lines[i:]).strip()
    return text


def _correct_chunk(
    client: OpenAI,
    model: str,
    chunk_text: str,
    ref_text: str,
) -> str:
    """將一段字幕送給 API 校正並回傳結果文字。"""
    # 組合輔助資料（社群名單 + 參考資料），共用截斷預算
    aux = ""
    if _NAMES_CACHE:
        aux += _NAMES_CACHE + "\n\n"
    if ref_text.strip():
        aux += f"【參考資料】\n{ref_text}"
    user_content = ""
    if aux.strip():
        truncated = aux[:MAX_REF_CHARS]
        if len(aux) > MAX_REF_CHARS:
            truncated += "\n...(輔助資料截斷)"
        user_content += truncated + "\n\n"
    user_content += f"【待校正字幕】\n{chunk_text}"

    # 嘗試停用思考模式（部分模型支援）
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=8192,
            extra_body={"thinking": {"type": "disabled"}},  # Anthropic 相容
        )
    except Exception:
        # 不支援 thinking 參數時，退回標準呼叫
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=8192,
        )

    raw = response.choices[0].message.content or ""
    return _extract_srt_from_response(raw)


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

        chunk_text     = "\n\n".join(chunk)
        corrected_text = _correct_chunk(client, model, chunk_text, ref_text)

        chunk_blocks = re.split(r"\n{2,}", corrected_text.strip())
        corrected_blocks.extend([b.strip() for b in chunk_blocks if b.strip()])

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
