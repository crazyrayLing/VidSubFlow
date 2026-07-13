import sys
import os
import srt
import re
import time
from tqdm import tqdm
from openai import OpenAI

# ==============================
# 修复 Windows 控制台编码问题
# ==============================
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==============================
# DeepSeek API 配置（使用官方 SDK）
# ==============================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-999")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 初始化客户端
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# 优化后的配置
CONTEXT_WINDOW = 25  # 适中的窗口大小
MAX_RETRY = 2  # 最大重试次数
CACHE_ENABLED = True  # 启用缓存，避免重复翻译

# ==============================
# 翻译缓存（避免重复翻译相同内容）
# ==============================
translation_cache = {}

def get_cache_key(texts):
    """生成缓存键"""
    return "||".join(texts)

# ==============================
# DeepSeek 翻译函数（优化 token 使用）
# ==============================
def translate_with_context(subtitle_texts, context_before="", context_after="", retry_count=0):
    """
    使用DeepSeek API进行上下文翻译（优化 token 消耗）
    """
    # 检查缓存
    cache_key = get_cache_key(subtitle_texts)
    if CACHE_ENABLED and cache_key in translation_cache:
        print(f"[缓存命中] 使用缓存的翻译结果", flush=True)
        return translation_cache[cache_key]
    
    # 精简的提示词（减少 token）
    system_prompt = "你是专业的字幕翻译专家。请逐条翻译英文为中文，保持口语化和自然流畅。"
    
    # 优化用户提示
    user_prompt = f"请翻译以下 {len(subtitle_texts)} 条英文字幕为中文：\n\n"
    for i, text in enumerate(subtitle_texts, 1):
        user_prompt += f"{i}. {text}\n"
    
    # 只在有上下文时添加（节省 token）
    if context_before:
        user_prompt = f"前文内容（仅供参考）：{context_before[:150]}\n\n" + user_prompt
    if context_after:
        user_prompt = user_prompt + f"\n\n后文内容（仅供参考）：{context_after[:150]}"
    
    # 添加格式要求（简洁明确）
    user_prompt += "\n\n请严格按照以下格式输出翻译结果：\n1. 翻译1\n2. 翻译2\n...\n只输出翻译内容，不要添加额外说明。"

    try:
        # 动态调整 max_tokens（根据输入长度）
        estimated_tokens = len(user_prompt) // 4 + len(subtitle_texts) * 50
        max_tokens = min(4000, max(500, estimated_tokens))
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # 降低随机性，保证一致性
            max_tokens=max_tokens,
            stream=False
        )
        
        translation = response.choices[0].message.content.strip()
        translated_lines = [line.strip() for line in translation.split('\n') if line.strip()]
        
        # 清理可能存在的序号
        cleaned_lines = []
        for line in translated_lines:
            # 匹配各种序号格式：1. 1、1) 等
            cleaned = re.sub(r'^\d+[\.、\)）]\s*', '', line)
            cleaned = re.sub(r'^第\d+条[、\.\s]', '', cleaned)
            if cleaned:
                cleaned_lines.append(cleaned)
        
        # 如果行数匹配，缓存结果
        if len(cleaned_lines) == len(subtitle_texts):
            translation_cache[cache_key] = cleaned_lines
            return cleaned_lines
        
        # 行数不匹配时的智能处理
        print(f"警告：行数不匹配 - 翻译结果 {len(cleaned_lines)} 行 vs 原文 {len(subtitle_texts)} 行", flush=True)
        
        # 尝试智能修复
        fixed_result = smart_fix_translation(cleaned_lines, subtitle_texts)
        if fixed_result:
            translation_cache[cache_key] = fixed_result
            return fixed_result
        
        # 如果修复失败且未超过重试次数
        if retry_count < MAX_RETRY:
            print(f"重试翻译 (尝试 {retry_count + 2})...", flush=True)
            time.sleep(0.5)
            return translate_with_context(
                subtitle_texts, 
                context_before[:100] if context_before else "", 
                context_after[:100] if context_after else "", 
                retry_count + 1
            )
        
        # 最终备用方案：逐条翻译
        print("使用备用方案：逐条翻译", flush=True)
        return translate_individually(subtitle_texts)
        
    except Exception as e:
        print(f"API错误：{e}", flush=True)
        if retry_count < MAX_RETRY:
            time.sleep(1)
            return translate_with_context(
                subtitle_texts, 
                context_before[:100] if context_before else "", 
                context_after[:100] if context_after else "", 
                retry_count + 1
            )
        return translate_individually(subtitle_texts)

def smart_fix_translation(translated_lines, original_texts):
    """
    智能修复翻译结果
    """
    if len(translated_lines) == 1:
        # 尝试按标点分割
        for pattern in [r'[。！？.!?]', r'[，、,;]']:
            parts = re.split(pattern, translated_lines[0])
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= len(original_texts) * 0.8:
                # 如果分割数量接近，进行智能合并
                result = []
                step = max(1, len(parts) // len(original_texts))
                for i in range(0, len(parts), step):
                    merged = "".join(parts[i:i+step])
                    if merged:
                        result.append(merged)
                if len(result) >= len(original_texts) * 0.8:
                    # 补齐到相同数量
                    while len(result) < len(original_texts):
                        result.append(result[-1] if result else "")
                    return result[:len(original_texts)]
    
    # 如果行数差距不大，尝试合并或拆分
    if abs(len(translated_lines) - len(original_texts)) <= 3:
        if len(translated_lines) < len(original_texts):
            # 复制最后一条补齐
            while len(translated_lines) < len(original_texts):
                translated_lines.append(translated_lines[-1])
            return translated_lines[:len(original_texts)]
        else:
            # 合并多余的行
            while len(translated_lines) > len(original_texts):
                translated_lines[-2] += " " + translated_lines[-1]
                translated_lines.pop()
            return translated_lines
    
    return None

def translate_individually(subtitle_texts):
    """
    逐条翻译（备用方案）
    """
    print("使用逐条翻译模式...", flush=True)
    results = []
    
    for i, text in enumerate(subtitle_texts):
        try:
            # 单条翻译（带简单上下文）
            context = ""
            if i > 0:
                context += f"前文：{subtitle_texts[i-1][:50]}"
            if i < len(subtitle_texts) - 1:
                context += f"后文：{subtitle_texts[i+1][:50]}"
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是翻译专家。请将英文翻译为中文，保持口语化。"},
                    {"role": "user", "content": f"{context}\n\n翻译以下句子：\n{text}"}
                ],
                temperature=0.2,
                max_tokens=300,
                stream=False
            )
            translation = response.choices[0].message.content.strip()
            results.append(translation)
            time.sleep(0.1)  # 减少等待时间
            
        except Exception as e:
            print(f"翻译失败：{e}", flush=True)
            results.append(f"[待翻译] {text}")
    
    return results

def translate_with_context_optimized(subtitle_texts):
    """
    优化版逐条翻译（保留上下文）
    """
    print("使用优化逐条翻译...", flush=True)
    results = []
    
    for i, text in enumerate(subtitle_texts):
        try:
            # 批量处理：每5条合并一次请求
            if i % 5 == 0 and i + 5 <= len(subtitle_texts):
                batch = subtitle_texts[i:i+5]
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "翻译为中文，每条一行。"},
                        {"role": "user", "content": f"翻译：\n" + "\n".join(batch)}
                    ],
                    temperature=0.2,
                    max_tokens=500,
                    stream=False
                )
                batch_results = response.choices[0].message.content.strip().split('\n')
                for j, result in enumerate(batch_results):
                    if result.strip():
                        results.append(result.strip())
                i += 4  # 跳过已处理的
                time.sleep(0.2)
                continue
            
            # 单条翻译（带简单上下文）
            context = ""
            if i > 0:
                context += f"前文：{subtitle_texts[i-1][:30]}"
            if i < len(subtitle_texts) - 1:
                context += f"后文：{subtitle_texts[i+1][:30]}"
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "翻译英文为中文。"},
                    {"role": "user", "content": f"{context}\n{text}"}
                ],
                temperature=0.2,
                max_tokens=200,
                stream=False
            )
            translation = response.choices[0].message.content.strip()
            results.append(translation)
            time.sleep(0.1)  # 减少等待时间
            
        except Exception as e:
            print(f"翻译失败：{e}", flush=True)
            results.append(f"[待翻译] {text}")
    
    return results

# ==============================
# 翻译 SRT 文件（优化版）
# ==============================
def translate_subtitle_file_with_context(input_srt_path):
    if not os.path.exists(input_srt_path):
        print(f"文件不存在: {input_srt_path}", flush=True)
        return

    if DEEPSEEK_API_KEY == "your-api-key-here":
        print("错误：请设置 DEEPSEEK_API_KEY 环境变量", flush=True)
        return

    # 读取SRT文件
    with open(input_srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    subtitles = list(srt.parse(srt_content))
    total = len(subtitles)
    
    if total == 0:
        print("未找到有效的字幕条目", flush=True)
        return

    print(f"开始翻译，共 {total} 条字幕", flush=True)
    print(f"上下文窗口：{CONTEXT_WINDOW} 条，缓存：{'启用' if CACHE_ENABLED else '禁用'}", flush=True)

    # 存储所有翻译结果
    translated_contents = [""] * total
    translated_count = 0

    # 分批翻译（优化上下文重叠）
    for start_idx in tqdm(range(0, total, CONTEXT_WINDOW), desc="翻译"):
        end_idx = min(start_idx + CONTEXT_WINDOW, total)
        
        # 提取当前批次的字幕文本
        batch_texts = [sub.content for sub in subtitles[start_idx:end_idx]]
        
        # 精简上下文（只取关键信息）
        context_before = ""
        context_after = ""
        
        if start_idx > 0:
            prev_idx = max(0, start_idx - 3)  # 减少上下文数量
            prev_texts = [subtitles[i].content for i in range(prev_idx, start_idx)]
            # 只保留最后2条作为上下文
            if len(prev_texts) > 2:
                prev_texts = prev_texts[-2:]
            context_before = " ".join(prev_texts)
        
        if end_idx < total:
            next_idx = min(total, end_idx + 3)
            next_texts = [subtitles[i].content for i in range(end_idx, next_idx)]
            if len(next_texts) > 2:
                next_texts = next_texts[:2]
            context_after = " ".join(next_texts)

        # 调用翻译
        translated_batch = translate_with_context(batch_texts, context_before, context_after)
        
        # 保存翻译结果
        for i, trans in enumerate(translated_batch):
            if i < len(batch_texts):
                translated_contents[start_idx + i] = trans
        
        translated_count += len(batch_texts)
        
        # 输出进度（减少日志频率）
        if translated_count % (CONTEXT_WINDOW * 2) == 0 or translated_count == total:
            progress_percent = (translated_count / total) * 100
            print(f"\nPROGRESS: {progress_percent:.1f}% ({translated_count}/{total})", flush=True)

    # 更新字幕内容 - 将英文和中文分开，或双语显示
    for idx, sub in enumerate(subtitles):
        if translated_contents[idx] and not translated_contents[idx].startswith("[待翻译]") and not translated_contents[idx].startswith("[翻译失败]"):
            # 双语显示：英文在上，中文在下
            sub.content = f"{sub.content}\n{translated_contents[idx]}"
        else:
            sub.content = f"{sub.content}\n[翻译失败]"

    # 输出文件
    output_path = os.path.splitext(input_srt_path)[0] + "_zh.srt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt.compose(subtitles))

    print(f"\n[完成] 输出文件：{output_path}", flush=True)
    print(f"翻译 {total} 条字幕，使用 {len(translation_cache)} 条缓存", flush=True)

# ==============================
# 命令行入口
# ==============================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python subtitle_translator_deepseek.py <字幕文件路径.srt>", flush=True)
        print("\n设置 API Key：")
        print("  Windows: set DEEPSEEK_API_KEY=your-key")
        print("  Linux/Mac: export DEEPSEEK_API_KEY='your-key'")
        sys.exit(1)

    input_path = sys.argv[1]
    translate_subtitle_file_with_context(input_path)