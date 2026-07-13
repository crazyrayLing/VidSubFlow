import sys
import os
from faster_whisper import WhisperModel
from datetime import timedelta
import srt
import ffmpeg
import time
from concurrent.futures import ThreadPoolExecutor
import threading

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

if len(sys.argv) < 2:
    print("请提供视频文件路径")
    sys.exit(1)

video_path = sys.argv[1]

if not os.path.exists(video_path):
    print(f"视频文件不存在: {video_path}")
    sys.exit(1)

output_dir = "outsrt"
os.makedirs(output_dir, exist_ok=True)

video_name = os.path.splitext(os.path.basename(video_path))[0]
output_srt = os.path.join(output_dir, f"{video_name}.srt")

print(f"正在分析视频: {video_name}")

# 获取视频时长
probe = ffmpeg.probe(video_path)
total_duration = float(probe["format"]["duration"])
print(f"视频总时长: {timedelta(seconds=total_duration)}")

# 优化：使用更小的模型或量化版本加速
model = WhisperModel(
    "small.en",
    device="cpu",
    compute_type="int8",  # 使用int8量化加速
    download_root="./models",
    cpu_threads=4,  # 设置CPU线程数
    num_workers=1
)

# 优化：设置更少的beam size加速
segments, info = model.transcribe(
    video_path, 
    word_timestamps=True,
    beam_size=3,  # 减少beam size加速
    best_of=3,
    temperature=0.0
)

sentence_end_punctuations = {'.', '?', '!', '。', '？', '！', ',', ';', ':', '，', '；', '：'}
force_break_punctuations = {'.', '?', '!', '。', '？', '！', ';', ':', '；', '：'}
subs = []

def clean_text(text):
    return " ".join(text.split())

def create_subtitle_chunk(words_chunk):
    start = words_chunk[0].start
    end = words_chunk[-1].end
    start_td = timedelta(seconds=start)
    end_td = timedelta(seconds=end)
    text = clean_text(" ".join(w.word for w in words_chunk))
    return srt.Subtitle(index=len(subs) + 1, start=start_td, end=end_td, content=text)

def split_chunk_by_max_pause(chunk_words, min_len=10, max_len=18):
    """根据最长停顿切分 chunk_words，只有单词数 >14 时才执行"""
    if len(chunk_words) <= 14:
        return [chunk_words]
    
    end_index = min(len(chunk_words), max_len)
    max_gap = 0
    split_idx = min_len
    for i in range(min_len - 1, end_index - 1):
        gap = chunk_words[i+1].start - chunk_words[i].end
        if gap > max_gap:
            max_gap = gap
            split_idx = i+1
    first_part = chunk_words[:split_idx]
    second_part = chunk_words[split_idx:]
    return [first_part, second_part]

# 优化：批量处理chunk，减少函数调用开销
def process_chunks(chunks_list):
    """批量处理chunks列表"""
    result = []
    for cw in chunks_list:
        parts = split_chunk_by_max_pause(cw, min_len=10, max_len=18)
        if len(parts) == 1:
            result.append(create_subtitle_chunk(parts[0]))
        else:
            result.append(create_subtitle_chunk(parts[0]))
            # 将剩余部分加入待处理列表
            for part in parts[1:]:
                result.extend(process_chunks([part]))
    return result

chunk_words = []
last_punct_index = -1
current_progress = 0.0
start_time = time.time()
last_update_time = start_time

print("开始语音识别和字幕生成...")
sys.stdout.flush()

# 预分配列表以提升性能
subs = []
chunk_words = []

for seg in segments:
    if seg.words:
        for w in seg.words:
            chunk_words.append(w)
            
            # 记录最近标点位置
            if w.word and w.word[-1] in sentence_end_punctuations:
                last_punct_index = len(chunk_words) - 1
            
            # 1. 长句 >10 个单词并遇到任意标点断句
            if len(chunk_words) > 10 and last_punct_index != -1:
                first_chunk = chunk_words[:last_punct_index + 1]
                rest_chunk = chunk_words[last_punct_index + 1:]
                
                # 处理前半部分
                chunks_to_process = [first_chunk]
                while chunks_to_process:
                    cw = chunks_to_process.pop(0)
                    parts = split_chunk_by_max_pause(cw, min_len=10, max_len=18)
                    if len(parts) == 1:
                        subs.append(create_subtitle_chunk(parts[0]))
                    else:
                        subs.append(create_subtitle_chunk(parts[0]))
                        chunks_to_process.insert(0, parts[1])
                
                chunk_words = rest_chunk
                last_punct_index = -1
                # 更新剩余 chunk 中的标点位置
                for i, cw in enumerate(chunk_words):
                    if cw.word and cw.word[-1] in sentence_end_punctuations:
                        last_punct_index = i
            
            # 2. 即使不足 10 个单词，只要出现非逗号标点也断句
            elif w.word and w.word[-1] in force_break_punctuations:
                chunks_to_process = [chunk_words]
                while chunks_to_process:
                    cw = chunks_to_process.pop(0)
                    parts = split_chunk_by_max_pause(cw, min_len=10, max_len=18)
                    if len(parts) == 1:
                        subs.append(create_subtitle_chunk(parts[0]))
                    else:
                        subs.append(create_subtitle_chunk(parts[0]))
                        chunks_to_process.insert(0, parts[1])
                chunk_words = []
                last_punct_index = -1
            
            # 优化：更新进度显示，包含剩余时间估计
            progress = w.end
            if progress > current_progress:
                current_progress = progress
                percent = (current_progress / total_duration) * 100
                
                # 计算剩余时间
                current_time = time.time()
                if current_time - last_update_time > 0.5:  # 每0.5秒更新一次
                    elapsed = current_time - start_time
                    if percent > 0:
                        total_estimated = elapsed / (percent / 100)
                        remaining = total_estimated - elapsed
                        remaining_str = str(timedelta(seconds=int(remaining)))
                    else:
                        remaining_str = "计算中..."
                    
                    elapsed_str = str(timedelta(seconds=int(elapsed)))
                    
                    # 生成进度条
                    bar_length = 30
                    filled = int(bar_length * percent / 100)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    print(f"\r进度: [{bar}] {percent:.1f}% | "
                          f"已用: {elapsed_str} | "
                          f"剩余: {remaining_str} | "
                          f"字幕数: {len(subs)}", 
                          end="", flush=True)
                    last_update_time = current_time

# 处理剩余未切割的单词
if chunk_words:
    chunks_to_process = [chunk_words]
    while chunks_to_process:
        cw = chunks_to_process.pop(0)
        parts = split_chunk_by_max_pause(cw, min_len=6, max_len=18)
        if len(parts) == 1:
            subs.append(create_subtitle_chunk(parts[0]))
        else:
            subs.append(create_subtitle_chunk(parts[0]))
            chunks_to_process.insert(0, parts[1])

print("\n正在保存字幕文件...")

# 优化：写入文件使用缓冲区
with open(output_srt, "w", encoding="utf-8", buffering=8192) as f:
    f.write(srt.compose(subs))

# 显示完成信息
total_time = time.time() - start_time
print(f"\n✅ 字幕生成完成!")
print(f"📁 输出文件: {output_srt}")
print(f"📝 字幕数量: {len(subs)}")
print(f"⏱️  总耗时: {str(timedelta(seconds=int(total_time)))}")
print(f"📊 平均速度: {total_duration/total_time:.2f}x (实时)")