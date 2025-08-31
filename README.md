# 🎬 VideoSubFusion

**VideoSubFusion** 是一个基于 **PyQt5** 的视频字幕处理工具，支持以下功能：

- 🎤 使用 **faster-whisper** 自动生成字幕  
- 🌍 使用 **MarianMT (transformers)** 翻译字幕  
- 🎞️ 使用 **ffmpeg** 将字幕与视频融合  
- ✂️ 支持字幕分割与管理  
- 🖥️ 提供简洁易用的 **GUI 界面**  

适合视频制作者、内容创作者，以及需要快速生成/翻译字幕的用户。  

---

## 🔧 环境要求

- Python **3.9+**（推荐，因 `faster-whisper`、`torch` 兼容性考虑）  
- 已安装 [**FFmpeg**](https://ffmpeg.org/download.html) 并配置到 `PATH`  

---

## ⚙️ Installation & Usage

```bash
# 克隆项目
git clone https://github.com/crazyrayLing/VideoSubFusion.git
cd VideoSubFusion

# (可选) 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows

# 安装依赖（指定版本）
pip install "PyQt5==5.15.11" "ffmpeg-python>=0.2.0" "faster-whisper==1.2.0" \
"nltk>=3.8.1" "tqdm>=4.65.0" "torch>=2.0.0" "transformers>=4.38.2" \
"sentencepiece>=0.1.99" "srt>=3.5.3"

# 检查 ffmpeg 是否安装成功
ffmpeg -version

# 启动程序
python app.py
