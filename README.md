# 🎮 GGD-AI | 鹅鸭杀AI发言助手

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react" alt="React 18">
  <img src="https://img.shields.io/badge/Tauri-2.0-FFC131?logo=tauri" alt="Tauri 2.0">
  <img src="https://img.shields.io/badge/Rust-1.70-orange?logo=rust" alt="Rust">
  <img src="https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi" alt="FastAPI">
</p>

<p align="center">
  <b>智能识别游戏发言 | 实时语音转文字 | 玩家自动追踪 | 情绪分析</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-blue.svg" alt="Platform">
</p>

---

## 📖 项目简介

**GGD-AI** 是一款专为《鹅鸭杀》(Goose Goose Duck) 设计的智能发言辅助工具。通过计算机视觉和语音识别技术，自动识别游戏中正在发言的玩家，并将语音实时转换为文字，帮助玩家更好地记录和分析游戏对话。

### ✨ 核心功能

| 功能 | 描述 |
|------|------|
| 🔍 **智能画面识别** | 基于OpenCV模板匹配，实时检测发言玩家标识 |
| 🎙️ **实时语音识别** | 使用FunASR模型，中文识别准确率高 |
| 📝 **自动文字记录** | 发言内容自动转录并按玩家分类存储 |
| 😊 **情绪分析** | 简单的情感极性分析，识别可疑发言 |
| 🖥️ **窗口捕获** | 支持后台窗口截图，无需前置游戏 |
| 🔄 **轮数管理** | 支持多轮游戏记录，数据分轮次展示 |
| 📊 **可视化界面** | Fluent Design风格UI，毛玻璃效果 |

---

## 🛠️ 技术栈

### 后端技术
```
┌─────────────────────────────────────────────────────────┐
│  Python 3.12                                            │
│  ├── FastAPI          - REST API & WebSocket           │
│  ├── FunASR           - 中文语音识别 (Paraformer-zh)    │
│  ├── OpenCV           - 图像处理与模板匹配              │
│  ├── PyAudio          - 音频流捕获                    │
│  ├── PyWin32          - Windows API 窗口操作          │
│  └── NumPy            - 数值计算                      │
└─────────────────────────────────────────────────────────┘
```

### 前端技术
```
┌─────────────────────────────────────────────────────────┐
│  Tauri + React 18                                       │
│  ├── TypeScript       - 类型安全                       │
│  ├── Vite             - 构建工具                       │
│  ├── Fluent Design    - 微软风格UI                     │
│  └── WebSocket Client - 实时通信                       │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 实现原理

### 架构图
```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   鹅鸭杀     │      │  GGD-AI     │      │   用户界面   │
│   游戏窗口   │──────▶│   后端服务   │◀─────▶│  (Tauri+React)│
└─────────────┘      └──────┬──────┘      └─────────────┘
                            │
           ┌────────────────┼────────────────┐
           ▼                ▼                ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ 屏幕捕获    │ │ 音频捕获    │ │ 语音识别    │
    │ (WinAPI)   │ │ (VB-Cable) │ │ (FunASR)   │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 核心流程

1. **窗口选择** 📋
   - 使用Tkinter GUI展示所有可见窗口
   - 支持双击高亮确认目标窗口

2. **画面监控** 🖼️
   - 每0.5秒捕获游戏画面（PrintWindow API支持后台）
   - OTSU二值化 + 连通域分析提取发言卡片
   - 模板匹配识别玩家编号（01-13）

3. **音频捕获** 🎧
   - 捕获VB-Cable虚拟声卡输出
   - VAD语音活动检测，过滤静音
   - 累积音频缓冲直到玩家切换

4. **语音识别** 🗣️
   - FunASR模型：Paraformer-zh + FSMN-VAD + CT-Punc
   - 支持中文标点自动恢复
   - 实时转录并关联当前发言玩家

5. **数据同步** 🔄
   - WebSocket实时推送新记录到前端
   - 自动保存JSON格式游戏记录

---

## 💎 技术亮点

### 1. 双模态融合识别
```python
# 画面识别发言玩家 + 语音识别内容
def _on_digit_change(self, new_digit, old_digit):
    # 玩家切换时触发语音缓冲区识别
    if self.audio_analyzer:
        self.audio_analyzer.set_speaker(new_digit, self.current_round)
```
将**计算机视觉**与**语音识别**结合，实现"谁说了什么"的精准记录。

### 2. 模板匹配优化
```python
# 基于连通域特征的卡片定位
if (total_square * 0.01 < square < total_square * 0.02 and
    white_ratio > 0.7 and 2.0 < w / h < 3.0):
    # 在卡片顶部区域进行模板匹配
    card_top = img_gray[y:int(y + h*0.3), x:int(x + w*0.15)]
```
通过**几何特征预筛选** + **局部模板匹配**，实现高精度玩家标识识别。

### 3. 模型预加载与复用
```python
# 只加载一次模型，避免重复启动开销
self._preloaded_model = await loop.run_in_executor(None, self._load_model)
# 后续启动直接复用
result = await loop.run_in_executor(
    None,
    lambda: self.monitor.start(preloaded_model=self._preloaded_model)
)
```
通过**模型预加载**机制，将启动时间从数十秒缩短到秒级。

### 4. 线程安全设计
```python
# 多线程环境下的事件队列
async def process_events():
    while True:
        while not event_queue.empty():
            event = event_queue.get_nowait()
            await manager.broadcast(event)
        await asyncio.sleep(0.1)
```
使用**异步事件队列**实现同步回调与异步WebSocket的无缝对接。

### 5. Fluent Design UI
```css
/* 毛玻璃效果 */
.acrylic-card {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```
采用微软**Fluent Design System**设计语言，呈现现代感的视觉效果。

---

## 🚀 快速开始

### 环境要求
- Windows 10/11
- Python 3.12
- VB-Cable虚拟声卡
- Node.js 18+
- Rust 1.70+

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/GGD-AI.git
cd GGD-AI

# 2. 创建Python环境
conda create -n ggd-ai python=3.12
conda activate ggd-ai

# 3. 安装Python依赖
pip install -r requirements.txt

# 4. 安装Node依赖
npm install

# 5. 运行开发版本
npm run start
```

### 使用流程

1. **安装VB-Cable**：下载并安装 [VB-Cable](https://vb-audio.com/Cable/) 虚拟声卡
2. **设置音频输出**：将鹅鸭杀游戏音频输出设置为"CABLE Input"
3. **启动程序**：运行 `npm run start`
4. **选择窗口**：在弹出的窗口列表中选择鹅鸭杀游戏
5. **开始监听**：点击"开始监听"按钮

---

## 📁 项目结构

```
GGD-AI/
├── 📂 src/                     # Python后端核心
│   ├── main.py                 # 服务入口
│   ├── api_server.py           # FastAPI服务
│   ├── monitor_controller.py   # 监控控制器
│   └── game_analysis.json      # 游戏记录数据
│
├── 📂 frontend/                # 前端代码
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/         # UI组件
│   │   ├── contexts/           # React Context
│   │   ├── hooks/              # 自定义Hooks
│   │   └── styles/             # 样式文件
│   └── index.html
│
├── 📂 src-tauri/               # Tauri桌面端
│   ├── Cargo.toml
│   └── src/
│
├── 📂 template_imgs/           # 玩家数字模板
│   ├── 01.png ~ 13.png
│
├── 📂 ffmpeg-8.0.1/            # FFmpeg工具
│
├── extract_speaker_num.py      # 画面识别模块
├── extract_speaker_statement.py # 语音分析模块
├── main_monitor.py             # 监控主控
├── screen_monitor.py           # 屏幕监控
└── window_selector.py          # 窗口选择器
```

---

## 📊 数据示例

```json
[
  {
    "timestamp": "12:15:09",
    "text": "来了兄弟，我在那边看了半天...",
    "emotion": "trust",
    "speaker": "11",
    "duration": 15.33,
    "round": 1
  },
  {
    "timestamp": "12:15:52",
    "text": "我开局遇到了赣州小丑...",
    "emotion": "trust",
    "speaker": "12",
    "duration": 34.6,
    "round": 1
  }
]
```

---

## 🛣️ 开发计划

- [x] 基础语音识别
- [x] 玩家标识检测
- [x] WebSocket实时通信
- [x] Fluent Design UI
- [ ] AI智能推理分析
- [ ] 声纹识别区分玩家
- [ ] 游戏角色自动推断
- [ ] 历史数据统计分析

---

## 🤝 贡献指南

欢迎提交Issue和PR！

```bash
# 提交PR流程
1. Fork 本仓库
2. 创建特性分支 (git checkout -b feature/AmazingFeature)
3. 提交更改 (git commit -m 'Add some AmazingFeature')
4. 推送分支 (git push origin feature/AmazingFeature)
5. 创建 Pull Request
```

---

## 📜 开源协议

本项目基于 [MIT](LICENSE) 协议开源。

---

## 🙏 致谢

- [FunASR](https://github.com/alibaba-damo-academy/FunASR) - 阿里巴巴开源语音识别工具包
- [Tauri](https://tauri.app/) - 跨平台桌面应用框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架

---

<p align="center">
  Made with ❤️ by GGD-AI Team
</p>
