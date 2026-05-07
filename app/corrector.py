"""
corrector.py — 分段校正 SRT 字幕
支援所有 OpenAI 相容 API：LM Studio、Ollama、OpenAI、Google AI Studio、自訂端點
"""
import re
from typing import Callable, Optional

from openai import OpenAI

# 每段最多處理幾個字幕（避免超過模型 context 長度）
CHUNK_SIZE = 150
# 參考資料最多傳入字數
MAX_REF_CHARS = 6000

SYSTEM_PROMPT = """你是繁體中文字幕校對專家，專門處理台灣教師研習的 ASR 語音辨識字幕。

【絕對保護的人名與機構名稱】
以下名稱必須完整保留，禁止任何更改：
- 邱文盛老師（或邱老師）
- 縣網中心
- 其他在參考資料中出現的講師姓名、單位名稱，均依參考資料為準

【嚴格規則】
1. 禁止縮減、合併或刪除任何字幕編號與時間軸
2. 每個字幕的格式必須完全保留：「編號」一行、「時間軸」一行、「文字」一行（或多行），各字幕之間以空行分隔
3. 只修正文字內容；時間軸與編號一字不差地原樣保留
4. 參考資料中的專有名詞請照原樣使用（如 ComfyUI、Pinokio、Claude Code、ChatGPT 等）
5. 全部使用繁體中文輸出，禁止出現簡體字
6. 不要顯示思考過程，直接輸出校正後的 SRT，不加任何說明或標題

【可修正的範圍】
- ASR 語音辨識錯誤（同音異字、近音誤識）
- 明顯的錯別字
- 口語贅詞（就是、然後、那個、這樣子、對不對、呃、嗯等填充詞，在不影響句意的情況下可刪除）
- 連續重複三次以上的同一詞語（保留一次即可）
- 英文專有名詞的正確寫法（依參考資料為準）

【禁止修正的範圍】
- 說話者刻意重複的強調語句
- 時間軸格式（00:00:00,000 --> 00:00:00,000）
- 字幕編號（純數字行）
- 人名、機構名（見上方保護清單）

直接輸出修正後的完整 SRT 字幕，不要加任何說明、標題或 Markdown 格式。"""


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
    user_content = ""
    if ref_text.strip():
        truncated = ref_text[:MAX_REF_CHARS]
        if len(ref_text) > MAX_REF_CHARS:
            truncated += "\n...(參考資料截斷)"
        user_content += f"【參考資料】\n{truncated}\n\n"
    user_content += f"【待校正字幕】\n{chunk_text}"

    # 嘗試停用思考模式（部分模型支援）
    extra_kwargs = {}
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


def correct(
    api_base_url: str,
    model: str,
    srt_content: str,
    api_key: str = "",
    ref_text: str = "",
    chunk_size: int = CHUNK_SIZE,
    progress_callback: Optional[Callable] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    主要校正函式，分段處理後合併輸出。
    - log_callback(msg)：每段完成時回呼，用於顯示詳細進度訊息
    """
    client = OpenAI(
        base_url=api_base_url.rstrip("/"),
        api_key=api_key.strip() or "no-key",
    )

    blocks = _parse_blocks(srt_content)
    original_count = len(blocks)
    chunks = _split_chunks(blocks, chunk_size)
    total_chunks = len(chunks)

    if log_callback:
        log_callback(f"📋 共 {original_count} 個字幕，分成 {total_chunks} 段處理，每段最多 {chunk_size} 個字幕。")
        if total_chunks > 1:
            log_callback("⏳ 長文本校正需要較長時間，可開啟 LM Studio 的 Log 視窗確認模型正在運作。")

    corrected_blocks = []

    for i, chunk in enumerate(chunks):
        seg_num = i + 1
        seg_start = i * chunk_size + 1
        seg_end = min((i + 1) * chunk_size, original_count)

        # 精確進度：留 5% 給讀檔，75% 給校正，20% 給結尾
        pct = 0.05 + 0.90 * (i / total_chunks)
        if progress_callback:
            progress_callback(
                pct,
                desc=f"第 {seg_num}/{total_chunks} 段（字幕 {seg_start}～{seg_end}）",
            )
        if log_callback:
            log_callback(f"🔄 開始校正第 {seg_num}/{total_chunks} 段（字幕 {seg_start}～{seg_end}）...")

        chunk_text = "\n\n".join(chunk)
        corrected_text = _correct_chunk(client, model, chunk_text, ref_text)

        chunk_blocks = re.split(r"\n{2,}", corrected_text.strip())
        corrected_blocks.extend([b.strip() for b in chunk_blocks if b.strip()])

        if log_callback:
            log_callback(f"✅ 第 {seg_num}/{total_chunks} 段完成")

    if progress_callback:
        progress_callback(0.97, desc="合併並儲存結果...")

    # 合併所有段落
    result = "\n\n".join(corrected_blocks) + "\n"

    # 驗證：字幕數量偏差不應超過 5%
    result_count = len(_parse_blocks(result))
    deviation = abs(result_count - original_count) / max(original_count, 1)
    if deviation > 0.05:
        raise ValueError(
            f"校正結果異常：原始 {original_count} 個字幕，"
            f"校正後 {result_count} 個，偏差 {deviation:.1%}（超過 5%）。\n"
            f"建議縮小每段字幕數（目前 {chunk_size}），或確認模型有正確遵守格式規則。"
        )

    return result
