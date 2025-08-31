import sys
import shutil
import os
import re
import glob
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QProcess, QThread, pyqtSignal, Qt
from ui_mainwindow import Ui_MainWindow
from fusion import process_video_with_subtitles

VIDEO_DIR = os.path.join(os.getcwd(), "video")
SUBTITLE_SCRIPT = "subtitle_generator.py"
SUBTITLE_TRANSLATE_SCRIPT = "subtitle_translator.py"


def find_subtitle_for_video(video_filename):
    video_name = os.path.splitext(video_filename)[0]
    standard_path = os.path.join("outsrt", f"{video_name}.srt")
    if os.path.exists(standard_path):
        return standard_path

    if not os.path.exists("outsrt"):
        return None
    outsrt_files = os.listdir("outsrt")
    video_name_simple = re.sub(r'[^\w]', '', video_name).lower()

    for f in outsrt_files:
        if not f.endswith(".srt"):
            continue
        f_simple = re.sub(r'[^\w]', '', os.path.splitext(f)[0]).lower()
        if video_name_simple == f_simple:
            return os.path.join("outsrt", f)
    return None


class FuseThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str, bool)

    def __init__(self, Vname, font_path):
        super().__init__()
        self.Vname = Vname
        self.font_path = font_path

    def run(self):
        try:
            def log_callback(msg):
                self.log_signal.emit(msg)

            def progress_callback(percent):
                self.log_signal.emit(f"PROGRESS:{percent}")

            process_video_with_subtitles(
                self.Vname,
                self.font_path,
                log_callback=log_callback,
                progress_callback=progress_callback
            )
            self.finished_signal.emit(self.Vname, True)
        except Exception as e:
            self.log_signal.emit(f"错误: {e}")
            self.finished_signal.emit(self.Vname, False)


def clean_filename(filename):
    filename = re.sub(r'[^A-Za-z0-9_\u4e00-\u9fff\s]', '', filename)
    filename = filename.strip()
    first_word = filename.split()[0] if filename else "video"
    return first_word


def find_latest_video_file(directory):
    video_extensions = ['*.mp4', '*.mkv', '*.webm', '*.avi', '*.mov']
    files = []
    for ext in video_extensions:
        files.extend(glob.glob(os.path.join(directory, ext)))
    if not files:
        return None
    return max(files, key=lambda x: os.path.getctime(x))


class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # 队列与状态
        self.video_path = None               # 最近一次下载完成的视频路径
        self.total_size = None
        self.subtitle_queue = []             # 生成字幕的待处理视频路径列表
        self.translate_queue = []            # 翻译字幕的待处理srt列表
        self.download_queue = []             # 批量链接下载队列（字符串URL）
        self.downloaded_video_paths = []     # 本轮批量中新下载的视频路径
        self.current_process = None
        self.translate_process = None
        self.process = None
        self.fuse_threads = []

        # 自动模式：下载->字幕->翻译->融合
        self.auto_mode_enabled = False
        self.ui.auto_pipeline_checkbox.stateChanged.connect(self.toggle_auto_mode)

        # 绑定按钮
        self.ui.download_button.clicked.connect(self.start_download_batch)
        self.ui.refresh_list_button.clicked.connect(self.load_video_list)
        self.ui.subtitle_button.clicked.connect(lambda: self.generate_subtitles_for_selected(auto=False))
        self.ui.subtitle_translate_button.clicked.connect(lambda: self.translate_subtitles_for_selected(auto=False))
        self.ui.subtitle_fuse_button.clicked.connect(self.fuse_selected_subtitles)

        self.load_video_list()

    def toggle_auto_mode(self, state):
        self.auto_mode_enabled = state == Qt.Checked
        self.ui.output_text.append(f"自动流水线模式 {'开启' if self.auto_mode_enabled else '关闭'}")

    # ---------- 进度按钮UI ----------
    def update_button_progress(self, button, percent, base_text):
        button.setText(f"{base_text} {int(percent)}%")
        button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28a745,
                    stop:{percent/100} #28a745,
                    stop:{percent/100} #ffffff,
                    stop:1 #ffffff
                );
                color: white;
                border-radius: 6px;
            }}
        """)

    def reset_button(self, button, text, color):
        button.setText(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #555555;
            }}
        """)

    # ---------- 字幕融合 ----------
    def fuse_selected_subtitles(self):
        if not hasattr(self, 'video_path') or not self.video_path:
            selected_items = self.ui.video_list_widget.selectedItems()
            if not selected_items:
                self.ui.output_text.append("错误：请先选择一个视频文件")
                return
            self.video_path = os.path.join(VIDEO_DIR, selected_items[0].text())

        font_path = "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf"
        Vname = os.path.splitext(os.path.basename(self.video_path))[0]
        self.ui.output_text.append(f"开始处理: {Vname}")

        thread = FuseThread(Vname, font_path)
        thread.log_signal.connect(self.handle_fuse_log)

        def on_finished(name, success):
            if success:
                self.ui.output_text.append(f"{name} 字幕融合完成！")
            else:
                self.ui.output_text.append(f"{name} 字幕融合失败！")
            self.reset_button(self.ui.subtitle_fuse_button, "融合选中视频字幕", "#6f42c1")
            self.set_buttons_enabled(True)

        thread.finished_signal.connect(on_finished)
        self.fuse_threads.append(thread)
        self.set_buttons_enabled(False)
        thread.start()

    def handle_fuse_log(self, msg):
        if msg.startswith("PROGRESS:"):
            try:
                percent = int(msg.split("PROGRESS:")[1])
                self.update_button_progress(self.ui.subtitle_fuse_button, percent, "融合选中视频字幕")
            except:
                pass
        else:
            self.ui.output_text.append(msg)

    # ---------- 视频列表 ----------
    def load_video_list(self):
        self.ui.video_list_widget.clear()
        if not os.path.exists(VIDEO_DIR):
            os.makedirs(VIDEO_DIR)
        video_files = [f for f in os.listdir(VIDEO_DIR)
                       if f.lower().endswith(('.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov'))]
        if not video_files:
            self.ui.output_text.append("video/ 目录暂无视频文件。")
            return
        for vf in sorted(video_files):
            self.ui.video_list_widget.addItem(vf)
        self.ui.output_text.append(f"加载到 {len(video_files)} 个视频文件。")

    def check_ytdlp_installed(self):
        return shutil.which("yt-dlp") is not None

    # ======================= 批量下载 =======================
    def start_download_batch(self):
        """从多行文本框读取多条链接，进入下载队列并顺序处理。"""
        urls_text = self.ui.url_input.toPlainText().strip()
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        if not urls:
            self.ui.output_text.append("错误：请输入至少一个视频链接（每行一个）！")
            return
        if not self.check_ytdlp_installed():
            self.ui.output_text.append("错误：未检测到 yt-dlp，请先安装。\n安装命令: pip install yt-dlp")
            return

        self.download_queue = urls[:]  # 拷贝
        self.downloaded_video_paths = []
        self.ui.output_text.append(f"批量下载任务数: {len(self.download_queue)}")
        self.set_buttons_enabled(False)
        self.process_next_download()

    def process_next_download(self):
        """顺序弹出URL，调用yt-dlp下载；单进程串行，便于定位输出文件。"""
        if not self.download_queue:
            self.ui.output_text.append("[完成] 所有视频下载完成！")
            self.reset_button(self.ui.download_button, "下载视频", "#0078d7")
            self.load_video_list()

            # 批量下载完成后，如开启自动模式，则批量进入字幕生成队列
            if self.auto_mode_enabled and self.downloaded_video_paths:
                self.subtitle_queue = self.downloaded_video_paths[:]
                names = [os.path.basename(p) for p in self.subtitle_queue]
                self.ui.output_text.append(f"[自动模式] 开始批量生成字幕，共 {len(names)} 个：\n" + "\n".join(names))
                self.process_next_subtitle()
            else:
                self.set_buttons_enabled(True)
            return

        url = self.download_queue.pop(0)
        self.ui.output_text.append(f"开始下载视频: {url}")
        self.update_button_progress(self.ui.download_button, 0, "下载视频")

        quality_map = {
            "1080p": "bv[height<=1080]+ba/b[height<=1080]",
            "720p": "bv[height<=720]+ba/b[height<=720]",
            "480p": "bv[height<=480]+ba/b[height<=480]",
            "360p": "bv[height<=360]+ba/b[height<=360]",
        }
        quality = quality_map.get(self.ui.quality_combo.currentText(),
                                  "bv[height<=720]+ba/b[height<=720]")

        os.makedirs(VIDEO_DIR, exist_ok=True)
        cmd = [
            "yt-dlp",
            "-f", quality,
            "-o", os.path.join(VIDEO_DIR, "%(title)s.%(ext)s"),
            url
        ]
        self.video_path = None
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_output)
        self.process.finished.connect(self.download_finished)
        self.process.start(cmd[0], cmd[1:])

    def read_output(self):
        text_data = self.process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
        err_data = self.process.readAllStandardError().data().decode("utf-8", errors="ignore")
        output = text_data + err_data
        if output:
            self.ui.output_text.append(output)

        # 粗略从分片日志估计下载进度
        frag_match = re.search(r"\(frag\s+(\d+)/(\d+)\)", output)
        if frag_match:
            current_frag = int(frag_match.group(1))
            total_frag = int(frag_match.group(2))
            progress_percent = int((current_frag / total_frag) * 100) if total_frag else 0
            self.update_button_progress(self.ui.download_button, progress_percent, "下载视频")

    def download_finished(self):
        latest_video = find_latest_video_file(VIDEO_DIR)
        if latest_video:
            self.video_path = latest_video
            self.ui.output_text.append(f"检测到最新视频文件: {os.path.basename(latest_video)}")

            dir_name = os.path.dirname(latest_video)
            old_name = os.path.basename(latest_video)
            name, ext = os.path.splitext(old_name)

            new_name = clean_filename(name) + ext
            new_path = os.path.join(dir_name, new_name)

            try:
                if new_path != latest_video:
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(latest_video, new_path)
                    self.video_path = new_path
                self.ui.output_text.append(f"已重命名文件: {os.path.basename(self.video_path)}")
            except Exception as e:
                self.ui.output_text.append(f"重命名失败: {e}")

            self.ui.output_text.append("下载完成！")
            # 记录到本轮批量下载列表中
            if self.video_path and os.path.exists(self.video_path):
                self.downloaded_video_paths.append(self.video_path)
        else:
            self.ui.output_text.append("未找到下载的视频文件。")

        # 继续下一个下载任务
        self.reset_button(self.ui.download_button, "下载视频", "#0078d7")
        self.process_next_download()

    # ======================= 生成字幕（批处理） =======================
    def generate_subtitles_for_selected(self, auto=False):
        self.subtitle_queue = [os.path.join(VIDEO_DIR, item.text())
                               for item in self.ui.video_list_widget.selectedItems()]
        if not self.subtitle_queue:
            self.ui.output_text.append("错误：请先选择至少一个视频文件")
            return
        self.set_buttons_enabled(False)
        self.process_next_subtitle()

    def process_next_subtitle(self):
        if not self.subtitle_queue:
            self.ui.output_text.append("[完成] 所有字幕生成完成！")
            self.reset_button(self.ui.subtitle_button, "生成选中视频字幕", "#dc3545")
            if self.auto_mode_enabled:
                self.auto_start_translation_batch()
            else:
                self.set_buttons_enabled(True)
            return

        video_file = self.subtitle_queue.pop(0)
        self.ui.output_text.append(f"正在生成字幕: {os.path.basename(video_file)}")
        self.update_button_progress(self.ui.subtitle_button, 0, "生成选中视频字幕")
        self.current_process = QProcess(self)
        self.current_process.setProcessChannelMode(QProcess.MergedChannels)
        self.current_process.readyReadStandardOutput.connect(self.handle_subtitle_output)
        self.current_process.finished.connect(self.subtitle_process_finished)
        self.current_process.start(sys.executable, [SUBTITLE_SCRIPT, video_file])

    def handle_subtitle_output(self):
        if self.current_process:
            output = self.current_process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            if output:
                self.ui.output_text.append(output)
            for line in output.splitlines():
                if line.startswith("PROGRESS:"):
                    try:
                        percent = float(line.split("PROGRESS:")[1].strip())
                        self.update_button_progress(self.ui.subtitle_button, percent, "生成选中视频字幕")
                    except:
                        pass

    def subtitle_process_finished(self, exitCode, exitStatus):
        if exitCode == 0:
            self.ui.output_text.append("[完成] 当前视频字幕生成成功")
        else:
            self.ui.output_text.append(f"[失败] 当前视频字幕生成失败，退出代码：{exitCode}")
        self.process_next_subtitle()

    # ======================= 翻译字幕（批处理） =======================
    def translate_subtitles_for_selected(self, auto=False):
        self.translate_queue = []
        for item in self.ui.video_list_widget.selectedItems():
            subtitle_path = find_subtitle_for_video(item.text())
            if subtitle_path and os.path.exists(subtitle_path):
                self.translate_queue.append(subtitle_path)
        if not self.translate_queue:
            self.ui.output_text.append("没有找到任何字幕文件进行翻译")
            return
        self.set_buttons_enabled(False)
        self.process_next_translate()

    def process_next_translate(self):
        if not self.translate_queue:
            self.ui.output_text.append("[完成] 所有字幕翻译完成！")
            self.reset_button(self.ui.subtitle_translate_button, "翻译选中字幕", "#17a2b8")
            if self.auto_mode_enabled:
                self.fuse_selected_subtitles()
            else:
                self.set_buttons_enabled(True)
            return

        srt_file = self.translate_queue.pop(0)
        self.ui.output_text.append(f"正在翻译字幕: {os.path.basename(srt_file)}")
        self.update_button_progress(self.ui.subtitle_translate_button, 0, "翻译选中字幕")
        self.translate_process = QProcess(self)
        self.translate_process.setProcessChannelMode(QProcess.MergedChannels)
        self.translate_process.readyReadStandardOutput.connect(self.handle_translate_output)
        self.translate_process.finished.connect(self.translate_process_finished)
        self.translate_process.start(sys.executable, [SUBTITLE_TRANSLATE_SCRIPT, srt_file])

    def handle_translate_output(self):
        if self.translate_process:
            output = self.translate_process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            if output:
                self.ui.output_text.append(output)
            for line in output.splitlines():
                if line.startswith("PROGRESS:"):
                    try:
                        percent = int(float(line.split("PROGRESS:")[1].strip()))
                        self.update_button_progress(self.ui.subtitle_translate_button, percent, "翻译选中字幕")
                    except:
                        pass

    def translate_process_finished(self):
        self.process_next_translate()

    def auto_start_translation_batch(self):
        """自动模式：将刚生成字幕的视频批量转成翻译队列。"""
        # 从下载得到的视频名推断字幕文件
        srt_list = []
        for vpath in self.downloaded_video_paths:
            base = os.path.basename(vpath)
            srt = find_subtitle_for_video(base)
            if srt and os.path.exists(srt):
                srt_list.append(srt)
        if srt_list:
            self.translate_queue = srt_list
            self.ui.output_text.append(f"[自动模式] 开始批量翻译字幕，共 {len(self.translate_queue)} 个")
            self.process_next_translate()
        else:
            self.set_buttons_enabled(True)

    # ---------- 按钮状态 ----------
    def set_buttons_enabled(self, enabled: bool):
        self.ui.download_button.setEnabled(enabled)
        self.ui.subtitle_button.setEnabled(enabled)
        self.ui.subtitle_translate_button.setEnabled(enabled)
        self.ui.subtitle_fuse_button.setEnabled(enabled)
        self.ui.refresh_list_button.setEnabled(enabled)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = YouTubeDownloader()
    win.show()
    sys.exit(app.exec_())
