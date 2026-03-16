import pyaudio
import wave
import numpy as np
from collections import deque
import time
import threading
import json
import os
import sys

# 添加 FFmpeg 到 PATH（如果存在项目目录中的 ffmpeg）
ffmpeg_dir = os.path.join(os.path.dirname(__file__), "ffmpeg-8.0.1-essentials_build", "bin")
if os.path.exists(ffmpeg_dir) and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

# FunASR 导入
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


class GooseGooseDuckAudioAnalyzer:
    def __init__(self):
        # 音频参数
        self.format = pyaudio.paInt16
        self.channels = 2  # 立体声（鹅鸭杀游戏语音是立体声）
        self.rate = 44100
        self.chunk = 1024

        # 使用VB-Cable Output作为输入设备
        self.device_index = self._find_vbcable_device()

        # 初始化 FunASR 模型（用于语音转文字）
        print("加载 FunASR 模型...")
        # 自动下载模型到本地缓存
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)

        # 使用 Paraformer-zh 模型（中文识别效果最佳）
        # 同时加载 VAD 和标点恢复模型，形成完整链路
        self.funasr_model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            # 可选：指定本地缓存路径
            # model_path=model_dir,
        )
        print("FunASR 模型加载完成！")

        # 音频缓冲区（滑动窗口，5秒）
        self.audio_buffer = deque(maxlen=int(self.rate * 5 / self.chunk))
        self.is_recording = False

        # 分析结果存储
        self.conversation_log = []

    def _find_vbcable_device(self):
        """查找VB-Cable Output设备索引"""
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if "CABLE Output" in dev['name'] and dev['hostApi'] == 0:
                print(f"找到捕获设备: {dev['name']} (索引: {i})")
                return i
        raise Exception("未找到VB-Cable Output设备，请先安装虚拟声卡")

    def vad_detect(self, audio_data):
        """简单的语音活动检测(VAD)"""
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        volume = np.abs(audio_np).mean()
        # 阈值需要根据实际环境调整
        return volume > 500

    def transcribe_audio(self, audio_frames):
        """将音频帧转换为文字 - 使用 FunASR"""
        # 将音频帧合并
        audio_data = b''.join(audio_frames)

        # 保存为临时wav文件
        temp_file = "test_audio/temp_audio.wav"
        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.rate)
            wf.writeframes(audio_data)

        try:
            # 使用 FunASR 进行语音识别
            # FunASR 自动处理 VAD、语音识别和标点恢复
            result = self.funasr_model.generate(
                input=temp_file,
                # 使用batch推理（如果有多段音频）
                batch_size_s=300,
                # 输出带时间戳的结果
                return_raw_text=True,
            )

            # 提取识别文本
            if result and len(result) > 0:
                text = result[0].get("text", "").strip()
                # 应用后处理优化（标点、格式等）
                text = rich_transcription_postprocess(text)
                return text
            return ""

        except Exception as e:
            print(f"语音识别出错: {e}")
            return ""

    def analyze_emotion(self, text):
        """简单的情绪分析（可使用更复杂的模型）"""
        # 这里可以接入OpenAI API或其他情绪分析模型
        # 示例：关键词检测
        negative_words = ['杀', '狼', '怀疑', '假的', '骗', '刀']
        positive_words = ['信', '好', '帮', '保', '村民']

        score = sum(1 for w in negative_words if w in text) - \
                sum(1 for w in positive_words if w in text)

        return "suspicious" if score > 0 else "trust" if score < 0 else "neutral"

    def continuous_recording(self):
        """持续录音并分析"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk
        )

        print("开始监听游戏语音...")
        silence_count = 0
        speech_frames = []
        is_speaking = False

        try:
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)

                # VAD检测
                if self.vad_detect(data):
                    if not is_speaking:
                        print("检测到语音开始...")
                        is_speaking = True
                    speech_frames.append(data)
                    silence_count = 0
                else:
                    silence_count += 1
                    if is_speaking:
                        speech_frames.append(data)

                    # 如果静音超过1秒（约43个chunk），认为说话结束
                    if is_speaking and silence_count > 43:
                        if len(speech_frames) > 20:  # 至少0.5秒的语音
                            print("语音段结束，开始识别...")
                            text = self.transcribe_audio(speech_frames)

                            if text:
                                print(text)
                                emotion = self.analyze_emotion(text)
                                timestamp = time.strftime("%H:%M:%S")

                                record = {
                                    "timestamp": timestamp,
                                    "text": text,
                                    "emotion": emotion,
                                    "speaker": "unknown"  # 后面讲如何区分玩家
                                }
                                self.conversation_log.append(record)
                                print(f"[{timestamp}] {emotion}: {text}")

                        is_speaking = False
                        speech_frames = []
                        silence_count = 0

        except KeyboardInterrupt:
            print("停止录制")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def start(self):
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self.continuous_recording)
        self.recording_thread.start()

    def stop(self):
        self.is_recording = False
        self.recording_thread.join()

    def save_log(self, filename="game_analysis.json"):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_log, f, ensure_ascii=False, indent=2)
        print(f"分析结果已保存至 {filename}")


# 运行
if __name__ == "__main__":
    analyzer = GooseGooseDuckAudioAnalyzer()
    try:
        analyzer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        analyzer.stop()
        analyzer.save_log()
