- ## 🎬 VideoSubFusion

  VideoSubFusion 是一个基于 **PyQt5** 的视频字幕处理工具，支持以下功能：

  - 使用 **faster-whisper** 进行语音识别，自动生成字幕  
  - 使用 **MarianMT (transformers)** 进行字幕翻译  
  - 使用 **ffmpeg** 将字幕与视频融合  
  - 支持字幕分割、调整与管理  
  - 提供简洁易用的 GUI 界面  

  该工具适合视频制作者、内容创作者以及需要快速生成/翻译字幕的用户。

## 🔧 环境要求

- Python **3.9+**（推荐，因 `faster-whisper`、`torch` 兼容性考虑）  
- 已安装 **FFmpeg** 并配置到 `PATH`  

## 📦 依赖安装

请确保使用 **Python 3.9+**。建议先创建虚拟环境：

```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
pip install "PyQt5==5.15.11"
pip install "ffmpeg-python>=0.2.0"
pip install "faster-whisper==1.2.0"
pip install "nltk>=3.8.1"
pip install "tqdm>=4.65.0"
pip install "torch>=2.0.0"
pip install "transformers>=4.38.2"
pip install "sentencepiece>=0.1.99"
pip install "srt>=3.5.3"
```

