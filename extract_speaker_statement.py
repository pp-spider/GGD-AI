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
    def __init__(self, on_new_record=None, auto_save=True, preloaded_model=None):
        """
        初始化音频分析器

        Args:
            on_new_record: 当有新记录时的回调函数，接收record字典
            auto_save: 是否自动保存到JSON文件（每次识别后立即保存）
            preloaded_model: 预加载的 FunASR 模型实例（可选，用于避免重复加载模型）
        """
        # 音频参数
        self.format = pyaudio.paInt16
        self.channels = 2  # 立体声（鹅鸭杀游戏语音是立体声）
        self.rate = 44100
        self.chunk = 1024

        # 使用VB-Cable Output作为输入设备
        self.device_index = self._find_vbcable_device()

        # 使用预加载的模型或重新加载
        if preloaded_model is not None:
            print("使用预加载的 FunASR 模型")
            self.funasr_model = preloaded_model
        else:
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

        self.is_recording = False

        # 分析结果存储
        self.conversation_log = []
        self._log_lock = threading.Lock()

        # 当前发言玩家（由外部画面监控更新）
        self._current_speaker = "unknown"
        self._speaker_lock = threading.Lock()

        # 音频缓冲区（用于累积语音，直到玩家切换）
        self._audio_buffer = []
        self._buffer_lock = threading.Lock()

        # 回调和自动保存
        self.on_new_record = on_new_record
        self.auto_save = auto_save
        self._save_lock = threading.Lock()

    def _find_vbcable_device(self):
        """查找VB-Cable Output设备索引"""
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if "CABLE Output" in dev['name'] and dev['hostApi'] == 0:
                print(f"找到捕获设备: {dev['name']} (索引: {i})")
                return i
        raise Exception("未找到VB-Cable Output设备，请先安装虚拟声卡")

    def set_speaker(self, speaker, round_num: int = 1):
        """
        设置当前发言玩家（由外部画面监控调用）
        当玩家切换时，触发累积语音的立即识别

        Args:
            speaker: 玩家标识，如 '02', '06' 等
            round_num: 当前轮数，默认为1
        """
        with self._speaker_lock:
            if speaker != self._current_speaker:
                print(f"[AudioAnalyzer] 发言玩家更新: {self._current_speaker} -> {speaker}")

                # 玩家切换时，将之前累积的语音转文字
                buffer_copy = None
                with self._buffer_lock:
                    if len(self._audio_buffer) > 0:
                        # 复制缓冲区并清空
                        buffer_copy = self._audio_buffer.copy()
                        self._audio_buffer = []

                # 在锁外异步处理，避免阻塞
                if buffer_copy:
                    # 使用切换前的玩家标识进行识别
                    prev_speaker = self._current_speaker if self._current_speaker != "unknown" else speaker
                    threading.Thread(
                        target=self._process_speech,
                        args=(buffer_copy, prev_speaker, round_num),
                        daemon=True
                    ).start()

                # 更新当前玩家
                self._current_speaker = speaker

    def get_speaker(self):
        """获取当前发言玩家"""
        with self._speaker_lock:
            return self._current_speaker

    def vad_detect(self, audio_data):
        """简单的语音活动检测(VAD)"""
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        volume = np.abs(audio_np).mean()
        # 阈值需要根据实际环境调整
        return volume > 500

    def transcribe_audio(self, audio_frames):
        """将音频帧转换为文字 - 使用 FunASR"""
        if not audio_frames:
            return ""

        # 将音频帧合并
        audio_data = b''.join(audio_frames)

        # 保存为临时wav文件
        temp_dir = "test_audio"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f"temp_audio_{int(time.time()*1000)}.wav")

        with wave.open(temp_file, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.rate)
            wf.writeframes(audio_data)

        try:
            # 使用 FunASR 进行语音识别
            result = self.funasr_model.generate(
                input=temp_file,
                batch_size_s=300,
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
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    def analyze_emotion(self, text):
        """简单的情绪分析（可使用更复杂的模型）"""
        negative_words = ['杀', '狼', '怀疑', '假的', '骗', '刀']
        positive_words = ['信', '好', '帮', '保', '村民']

        score = sum(1 for w in negative_words if w in text) - \
                sum(1 for w in positive_words if w in text)

        return "suspicious" if score > 0 else "trust" if score < 0 else "neutral"

    def _process_speech(self, audio_frames, speaker, round_num: int = 1):
        """
        处理语音并保存

        Args:
            audio_frames: 音频帧列表
            speaker: 发言玩家
            round_num: 当前轮数，默认为1
        """
        duration = len(audio_frames) * self.chunk / self.rate
        print(f"[语音识别] 处理: {duration:.1f}秒, 玩家: {speaker}, 轮数: {round_num}")

        text = self.transcribe_audio(audio_frames)

        if text:
            emotion = self.analyze_emotion(text)
            timestamp = time.strftime("%H:%M:%S")

            record = {
                "timestamp": timestamp,
                "text": text,
                "emotion": emotion,
                "speaker": speaker,
                "duration": round(duration, 2),
                "round": round_num
            }

            with self._log_lock:
                self.conversation_log.append(record)

            print(f"[{timestamp}] [第{round_num}轮] [{speaker}] {emotion}: {text}")

            # 触发回调
            if self.on_new_record:
                self.on_new_record(record)

            # 立即自动保存
            if self.auto_save:
                self._save_to_file("game_analysis.json")

    def _save_to_file(self, filename):
        """保存日志到文件"""
        with self._log_lock:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_log, f, ensure_ascii=False, indent=2)
        print(f"[AudioAnalyzer] 分析结果已保存至 {filename}")

    def continuous_recording(self):
        """持续录音，累积语音直到玩家切换"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk
        )

        print("开始监听游戏语音... (玩家切换时触发识别)")

        try:
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)

                # VAD检测：只累积有语音的数据
                if self.vad_detect(data):
                    with self._buffer_lock:
                        self._audio_buffer.append(data)

        except KeyboardInterrupt:
            print("停止录制")
        finally:
            # 处理剩余语音（使用当前玩家）
            buffer_to_process = None
            with self._buffer_lock:
                if self._audio_buffer:
                    buffer_to_process = self._audio_buffer.copy()
                    self._audio_buffer = []

            if buffer_to_process:
                speaker = self.get_speaker()
                self._process_speech(buffer_to_process, speaker)

            stream.stop_stream()
            stream.close()
            p.terminate()

    def start(self):
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self.continuous_recording)
        self.recording_thread.daemon = True
        self.recording_thread.start()

    def stop(self, round_num: int = 1):
        """
        停止录音，并触发最后剩余语音的识别

        Args:
            round_num: 当前轮数，用于标记识别结果
        """
        print("[AudioAnalyzer] 正在停止录音...")
        self.is_recording = False

        # 等待录音线程结束（finally块会处理部分剩余语音）
        if hasattr(self, 'recording_thread') and self.recording_thread:
            self.recording_thread.join(timeout=3)  # 最多等待3秒

        # 兜底处理：确保缓冲区被处理（防止finally块未完全处理）
        self._flush_remaining_buffer(round_num)

        print("[AudioAnalyzer] 录音已停止")

    def _flush_remaining_buffer(self, round_num: int = 1):
        """
        强制处理剩余的音频缓冲区
        在停止监听时调用，确保最后一段语音被识别

        Args:
            round_num: 当前轮数
        """
        buffer_to_process = None
        with self._buffer_lock:
            if self._audio_buffer:
                buffer_len = len(self._audio_buffer)
                buffer_to_process = self._audio_buffer.copy()
                self._audio_buffer = []
                print(f"[AudioAnalyzer] 强制处理剩余缓冲区: {buffer_len} 帧")

        if buffer_to_process:
            speaker = self.get_speaker()
            # 同步处理，确保在stop返回前完成识别
            self._process_speech(buffer_to_process, speaker, round_num)
            print(f"[AudioAnalyzer] 剩余语音处理完成，发言人: {speaker}")

    def save_log(self, filename="game_analysis.json"):
        """手动保存日志"""
        self._save_to_file(filename)

    def get_conversation_log(self):
        """获取当前对话日志"""
        with self._log_lock:
            return self.conversation_log.copy()


# 运行
if __name__ == "__main__":
    def on_new_record(record):
        print(f"新记录回调: {record}")

    analyzer = GooseGooseDuckAudioAnalyzer(
        on_new_record=on_new_record,
        auto_save=True
    )

    # 模拟外部更新speaker（测试玩家切换）
    def test_update_speaker():
        import random
        speakers = ["02", "06", "10", "unknown"]
        time.sleep(5)  # 先等5秒
        while analyzer.is_recording:
            time.sleep(random.uniform(5, 10))  # 随机5-10秒切换
            speaker = random.choice(speakers)
            analyzer.set_speaker(speaker)

    try:
        analyzer.start()
        # 启动测试线程
        test_thread = threading.Thread(target=test_update_speaker)
        test_thread.daemon = True
        test_thread.start()

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        analyzer.stop()
        analyzer.save_log()
