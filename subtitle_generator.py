import sys
import os
import nltk
from faster_whisper import WhisperModel
from datetime import timedelta
import srt
import ffmpeg

if len(sys.argv) < 2:
    print("请提供视频文件路径")
    sys.exit(1)

video_path = sys.argv[1]

if not os.path.exists(video_path):
    print(f"视频文件不存在: {video_path}")
    sys.exit(1)

nltk.download('punkt', quiet=True)

output_dir = "outsrt"
os.makedirs(output_dir, exist_ok=True)

video_name = os.path.splitext(os.path.basename(video_path))[0]
output_srt = os.path.join(output_dir, f"{video_name}.srt")

# 获取视频时长
probe = ffmpeg.probe(video_path)
total_duration = float(probe["format"]["duration"])

# 加载模型
model = WhisperModel("small.en", device="cpu")
segments, info = model.transcribe(video_path, word_timestamps=True)

sentence_end_punctuations = {'.', '?', '!', '。', '？', '！', ',', ';', ':', '，', '；', '：'}
force_break_punctuations = {'.', '?', '!', '。', '？', '！', ';', ':', '；', '：'}  # 非逗号的强制断句标点
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

def split_chunk_by_max_pause(chunk_words, min_len=10, max_len=30):
    """根据最长停顿切分 chunk_words，只有单词数 >16 时才执行"""
    if len(chunk_words) <= 16:
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

chunk_words = []
last_punct_index = -1
current_progress = 0.0

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
                # 对前半部分按最长停顿切分
                chunks_to_process = [first_chunk]
                while chunks_to_process:
                    cw = chunks_to_process.pop(0)
                    parts = split_chunk_by_max_pause(cw, min_len=10, max_len=30)
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
                    parts = split_chunk_by_max_pause(cw, min_len=10, max_len=30)
                    if len(parts) == 1:
                        subs.append(create_subtitle_chunk(parts[0]))
                    else:
                        subs.append(create_subtitle_chunk(parts[0]))
                        chunks_to_process.insert(0, parts[1])
                chunk_words = []
                last_punct_index = -1

            # 输出进度
            progress = w.end
            if progress > current_progress:
                current_progress = progress
                percent = (current_progress / total_duration) * 100
                print(f"PROGRESS: {percent:.2f}")
                sys.stdout.flush()

# 处理剩余未切割的单词
if chunk_words:
    chunks_to_process = [chunk_words]
    while chunks_to_process:
        cw = chunks_to_process.pop(0)
        parts = split_chunk_by_max_pause(cw, min_len=6, max_len=20)
        if len(parts) == 1:
            subs.append(create_subtitle_chunk(parts[0]))
        else:
            subs.append(create_subtitle_chunk(parts[0]))
            chunks_to_process.insert(0, parts[1])

with open(output_srt, "w", encoding="utf-8") as f:
    f.write(srt.compose(subs))

print(f"字幕生成完成: {output_srt}")
