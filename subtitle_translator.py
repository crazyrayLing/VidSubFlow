import sys
import os
import srt
import torch
from tqdm import tqdm
from transformers import MarianMTModel, MarianTokenizer

# ==============================
# 配置更快的模型
# ==============================
model_name = "Helsinki-NLP/opus-mt-en-zh"  # 英译中
print("loading...", flush=True)
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)
model.eval()
device = "cpu"  # 如果有GPU，可以改成 "cuda"
model.to(device)
print("Loading complete", flush=True)

# ==============================
# 翻译函数
# ==============================
def translate_text_local(text):
    encoded = tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(device)
    with torch.no_grad():
        generated_tokens = model.generate(
            **encoded,
            max_length=512,
            num_beams=4
        )
    translated = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
    return translated

# ==============================
# 翻译 SRT 文件
# ==============================
def translate_subtitle_file_local(input_srt_path):
    if not os.path.exists(input_srt_path):
        print(f"文件不存在: {input_srt_path}", flush=True)
        return

    with open(input_srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    subtitles = list(srt.parse(srt_content))
    for idx, sub in enumerate(tqdm(subtitles, desc="翻译进度")):
        translated = translate_text_local(sub.content)
        sub.content = f"{sub.content}\n{translated}"
    
        # 输出进度百分比
        progress_percent = (idx + 1) / len(subtitles) * 100
        print(f"PROGRESS: {progress_percent}", flush=True)

    output_path = os.path.splitext(input_srt_path)[0] + "_zh.srt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt.compose(subtitles))

    print(f"\n翻译完成，输出文件：{output_path}", flush=True)

# ==============================
# 命令行入口
# ==============================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python subtitle_translator_marian.py <字幕文件路径.srt>", flush=True)
        sys.exit(1)

    input_path = sys.argv[1]
    translate_subtitle_file_local(input_path)
