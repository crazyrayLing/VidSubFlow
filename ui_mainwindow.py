from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTextEdit, QComboBox,
    QListWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QWidget
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class Ui_MainWindow:
    def setupUi(self, MainWindow: QWidget):
        MainWindow.setWindowTitle("YouTube 视频下载器和字幕生成器")
        MainWindow.resize(900, 700)

        main_layout = QVBoxLayout(MainWindow)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题
        title_label = QLabel("YouTube 视频下载和字幕生成工具")
        title_label.setFont(QFont("微软雅黑", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 输入区域（多行）
        url_layout = QVBoxLayout()
        url_head = QHBoxLayout()
        url_label = QLabel("视频链接（支持批量，一行一个）：")
        url_label.setFont(QFont("微软雅黑", 12))
        url_head.addWidget(url_label)
        url_head.addStretch()
        url_layout.addLayout(url_head)

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("在此粘贴一个或多个链接（每行一个）")
        self.url_input.setFont(QFont("微软雅黑", 11))
        self.url_input.setMinimumHeight(90)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # 清晰度选择
        quality_layout = QHBoxLayout()
        quality_label = QLabel("选择清晰度:")
        quality_label.setFont(QFont("微软雅黑", 12))
        self.quality_combo = QComboBox()
        self.quality_combo.setFont(QFont("微软雅黑", 12))
        self.quality_combo.addItems(["1080p", "720p", "480p", "360p"])
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        main_layout.addLayout(quality_layout)

        # 按钮组
        btn_layout = QHBoxLayout()
        self.download_button = QPushButton("下载视频（批量）")
        self.download_button.setStyleSheet(
            "QPushButton {background-color: #0078d7; color: white; padding: 8px 16px; border-radius: 5px;}"
            "QPushButton:hover {background-color: #005a9e;}"
        )
        self.refresh_list_button = QPushButton("刷新视频列表")
        self.refresh_list_button.setStyleSheet(
            "QPushButton {background-color: #28a745; color: white; padding: 8px 16px; border-radius: 5px;}"
            "QPushButton:hover {background-color: #1e7e34;}"
        )
        btn_layout.addWidget(self.download_button)
        btn_layout.addWidget(self.refresh_list_button)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 视频列表
        list_label = QLabel("选择要生成字幕的视频（可多选）：")
        list_label.setFont(QFont("微软雅黑", 12))
        main_layout.addWidget(list_label)
        self.video_list_widget = QListWidget()
        self.video_list_widget.setSelectionMode(QListWidget.MultiSelection)
        self.video_list_widget.setFont(QFont("微软雅黑", 11))
        main_layout.addWidget(self.video_list_widget, stretch=1)

        # 自动模式
        self.auto_pipeline_checkbox = QCheckBox("自动流水线模式（下载→生成→翻译→融合）")
        self.auto_pipeline_checkbox.setFont(QFont("微软雅黑", 12))
        main_layout.addWidget(self.auto_pipeline_checkbox)

        # 流水线按钮（进度条用按钮填充）
        pipeline_layout = QHBoxLayout()
        self.subtitle_button = QPushButton("生成选中视频字幕（批量）")
        self.subtitle_translate_button = QPushButton("翻译选中字幕（批量）")
        self.subtitle_fuse_button = QPushButton("融合选中视频字幕（单个/当前）")
        for btn in (self.subtitle_button, self.subtitle_translate_button, self.subtitle_fuse_button):
            btn.setFont(QFont("微软雅黑", 12))
            btn.setStyleSheet(self._get_pipeline_btn_style("idle"))
            btn.setMinimumHeight(50)
            pipeline_layout.addWidget(btn)
        main_layout.addLayout(pipeline_layout)

        # 输出日志
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setStyleSheet("background-color: #f5f5f5;")
        main_layout.addWidget(self.output_text, stretch=1)

    def _get_pipeline_btn_style(self, state):
        styles = {
            "idle": "background-color: #6c757d; color: white; border-radius: 6px;",
            "active": "background-color: #007bff; color: white; border-radius: 6px;",
            "done": "background-color: #28a745; color: white; border-radius: 6px;"
        }
        return f"QPushButton {{{styles[state]}}} QPushButton:hover {{opacity: 0.9;}}"
