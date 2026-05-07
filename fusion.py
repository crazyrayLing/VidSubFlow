import os
import subprocess
import re
from split import split_srt  # 你的分割字幕模块

os.environ["PATH"] += r";C:\ffmpeg\bin"  # ffmpeg路径，根据实际改

def run_ffmpeg_with_progress(command, log_callback=None, progress_callback=None):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = None
    for line in process.stderr:
        line = line.strip()
        if log_callback:
            log_callback(line)
        # 获取视频总时长
        if duration is None:
            m = re.search(r'Duration: (\d+):(\d+):([\d\.]+)', line)
            if m:
                h, m_, s = map(float, m.groups())
                duration = h*3600 + m_*60 + s
        # 获取当前时间
        m2 = re.search(r'time=(\d+):(\d+):([\d\.]+)', line)
        if m2 and duration:
            h, m_, s = map(float, m2.groups())
            current_time = h*3600 + m_*60 + s
            percent = int((current_time / duration) * 100)
            if progress_callback:
                progress_callback(percent)
    process.wait()
    if process.returncode != 0:
        raise RuntimeError("FFmpeg 执行失败")

def get_codec_and_ext(input_ext):
    input_ext = input_ext.lower()
    if input_ext in ['.mp4', '.mov', '.m4v']:
        return "libx264", ".mp4"
    elif input_ext in ['.webm']:
        return "libvpx-vp9", ".webm"
    elif input_ext in ['.mkv']:
        return "libx264", ".mkv"
    elif input_ext in ['.flv']:
        return "flv", ".flv"
    elif input_ext in ['.avi']:
        return "mpeg4", ".avi"
    else:
        return "libx264", ".mp4"

def add_subtitles(input_video_file, srt_file, output_file, font_file=None,
                  subtitle_color='white', font_size=24, margin_v=21,Italic=0,
                  log_callback=None, progress_callback=None):
    if font_file:
        subtitle_filter = f"subtitles={srt_file}:fontsdir={os.path.dirname(font_file)}:" \
                          f"force_style='FontName={os.path.basename(font_file)}," \
                          f"PrimaryColour={subtitle_color},FontSize={font_size},MarginV={margin_v},Italic={Italic},Bold=1'"
    else:
        subtitle_filter = f"subtitles={srt_file}:" \
                          f"force_style='PrimaryColour={subtitle_color},FontSize={font_size},MarginV={margin_v},Italic={Italic},Bold=1'"

    _, input_ext = os.path.splitext(input_video_file)
    codec, output_ext = get_codec_and_ext(input_ext)
    output_file = os.path.splitext(output_file)[0] + output_ext
    audio_codec = "libopus" if output_ext == ".webm" else "aac"

    command = [
        "ffmpeg",
        "-i", input_video_file,
        "-vf", subtitle_filter,
        "-c:v", codec,
        "-crf", "23",
        "-preset", "ultrafast",
        "-c:a", audio_codec,
        "-y", output_file
    ]

    if log_callback:
        log_callback(f"正在添加字幕到视频: {os.path.basename(output_file)}")
    
    run_ffmpeg_with_progress(command, log_callback=log_callback, progress_callback=progress_callback)

    if log_callback:
        log_callback(f"字幕添加成功: {output_file}")
    return output_file



def convert_to_mp4(input_video, log_callback=None):
    base_name = os.path.splitext(input_video)[0]
    output_video = base_name + ".mp4"

    command = [
        "ffmpeg",
        "-i", input_video,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "ultrafast",
        "-y",
        output_video
    ]

    if log_callback:
        log_callback(f"正在转换为 MP4: {os.path.basename(input_video)}")

    result = subprocess.run(command)

    if result.returncode != 0:
        raise Exception("视频转换失败")

    # 删除原文件
    os.remove(input_video)

    if log_callback:
        log_callback(f"原视频已删除: {os.path.basename(input_video)}")
        log_callback(f"转换完成: {os.path.basename(output_video)}")

    return output_video


def process_video_with_subtitles(Vname, font_file=None, log_callback=None, progress_callback=None):
    video_dir = "video"
    exts = ['.mp4', '.mkv', '.webm', '.flv', '.avi']

    input_video_file = None

    for ext in exts:
        candidate = os.path.join(video_dir, Vname + ext)

        if os.path.exists(candidate):
            input_video_file = candidate
            break

    if input_video_file is None:
        if log_callback:
            log_callback(f"未找到名为 {Vname} 的视频文件！")
        return

    # =========================
    # 非 MP4 自动转换
    # =========================
    _, ext = os.path.splitext(input_video_file)

    if ext.lower() != ".mp4":
        input_video_file = convert_to_mp4(
            input_video_file,
            log_callback=log_callback
        )

    input_srt = f"outsrt/{Vname}_zh.srt"
    output_srt_en = f"outsrt/{Vname}_en.srt"
    output_srt_cn = f"outsrt/{Vname}_cn.srt"

    if log_callback:
        log_callback("开始分割字幕文件...")

    split_srt(input_srt, output_srt_en, output_srt_cn)

    if log_callback:
        log_callback("字幕文件分割完成。")

    # =========================
    # 中文字幕
    # =========================
    srt_file_cn = output_srt_cn
    output_file_cn = os.path.join(video_dir, f"{Vname}_cn")

    output_file_cn = add_subtitles(
        input_video_file,
        srt_file_cn,
        output_file_cn,
        font_file,
        subtitle_color='&H00FFFFFF',
        font_size=16,
        margin_v=40,
        Italic=0,
        log_callback=log_callback,
        progress_callback=progress_callback
    )

    # =========================
    # 英文字幕
    # =========================
    srt_file_en = output_srt_en
    output_file_en = os.path.join(video_dir, f"{Vname}_final")

    output_file_en = add_subtitles(
        output_file_cn,
        srt_file_en,
        output_file_en,
        font_file,
        subtitle_color='&H00FFFF00',
        font_size=12,
        margin_v=38,
        Italic=0,
        log_callback=log_callback,
        progress_callback=progress_callback
    )

    if log_callback:
        log_callback(f"最终输出文件: {output_file_en}")

