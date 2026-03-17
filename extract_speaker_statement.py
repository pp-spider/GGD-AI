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
    def __init__(self, on_new_record=None, auto_save=True, segment_duration=5.0):
        """
        初始化音频分析器

        Args:
            on_new_record: 当有新记录时的回调函数，接收record字典
            auto_save: 是否自动保存到JSON文件（每次分段识别后立即保存）
            segment_duration: 分段识别时长（秒），默认3秒
        """
        # 音频参数
        self.format = pyaudio.paInt16
        self.channels = 2  # 立体声（鹅鸭杀游戏语音是立体声）
        self.rate = 44100
        self.chunk = 1024

        # 分段时长
        self.segment_duration = segment_duration
        self.segment_chunks = int(self.rate * segment_duration / self.chunk)

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

        self.is_recording = False

        # 分析结果存储
        self.conversation_log = []
        self._log_lock = threading.Lock()

        # 当前发言玩家（由外部画面监控更新）
        self._current_speaker = "unknown"
        self._speaker_lock = threading.Lock()

        # 音频缓冲区（用于累积语音）
        self._audio_buffer = []
        self._buffer_lock = threading.Lock()
        self._speaker_changed = False  # 标记玩家是否切换
        self._last_speaker = "unknown"

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

    def set_speaker(self, speaker):
        """
        设置当前发言玩家（由外部画面监控调用）
        当玩家切换时，触发剩余语音的立即识别

        Args:
            speaker: 玩家标识，如 '02', '06' 等
        """
        with self._speaker_lock:
            if speaker != self._current_speaker:
                print(f"[AudioAnalyzer] 发言玩家更新: {self._current_speaker} -> {speaker}")
                # 标记玩家切换，触发剩余语音识别
                with self._buffer_lock:
                    self._speaker_changed = True
                    self._last_speaker = self._current_speaker
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

    def _process_segment(self, audio_frames, speaker, is_flush=False):
        """
        处理一个语音片段

        Args:
            audio_frames: 音频帧列表
            speaker: 发言玩家
            is_flush: 是否为强制刷新（玩家切换时）
        """
        if not audio_frames:
            return

        duration = len(audio_frames) * self.chunk / self.rate
        flush_tag = "[强制识别]" if is_flush else ""
        print(f"{flush_tag}处理语音片段: {duration:.1f}秒, 玩家: {speaker}")

        text = self.transcribe_audio(audio_frames)

        if text:
            emotion = self.analyze_emotion(text)
            timestamp = time.strftime("%H:%M:%S")

            record = {
                "timestamp": timestamp,
                "text": text,
                "emotion": emotion,
                "speaker": speaker,
                "duration": round(duration, 2)
            }

            with self._log_lock:
                self.conversation_log.append(record)

            print(f"[{timestamp}] [{speaker}] {emotion}: {text}")

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
        """持续录音并分段识别"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk
        )

        print(f"开始监听游戏语音... (分段识别: {self.segment_duration}秒)")

        chunk_counter = 0
        is_speaking = False
        silence_count = 0

        try:
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)

                # VAD检测
                has_voice = self.vad_detect(data)

                if has_voice:
                    is_speaking = True
                    silence_count = 0
                else:
                    silence_count += 1
                    # 如果静音超过2秒，认为说话暂停
                    if silence_count > 86:  # 约2秒
                        is_speaking = False

                # 累积音频帧
                with self._buffer_lock:
                    self._audio_buffer.append(data)
                    chunk_counter += 1

                    # 检查是否需要强制识别（玩家切换）
                    if self._speaker_changed and len(self._audio_buffer) > 0:
                        # 使用切换前的玩家标识
                        speaker = self._last_speaker if self._last_speaker != "unknown" else self._current_speaker
                        buffer_copy = self._audio_buffer.copy()
                        self._audio_buffer = []
                        self._speaker_changed = False
                        chunk_counter = 0

                        # 在锁外处理，避免阻塞
                        threading.Thread(
                            target=self._process_segment,
                            args=(buffer_copy, speaker, True),
                            daemon=True
                        ).start()

                    # 常规分段识别（满3秒且有语音）
                    elif chunk_counter >= self.segment_chunks and is_speaking:
                        speaker = self.get_speaker()
                        buffer_copy = self._audio_buffer.copy()
                        self._audio_buffer = []
                        chunk_counter = 0

                        # 在锁外处理，避免阻塞
                        threading.Thread(
                            target=self._process_segment,
                            args=(buffer_copy, speaker, False),
                            daemon=True
                        ).start()

        except KeyboardInterrupt:
            print("停止录制")
        finally:
            # 处理剩余语音
            with self._buffer_lock:
                if self._audio_buffer:
                    speaker = self.get_speaker()
                    self._process_segment(self._audio_buffer, speaker, True)

            stream.stop_stream()
            stream.close()
            p.terminate()

    def start(self):
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self.continuous_recording)
        self.recording_thread.daemon = True
        self.recording_thread.start()

    def stop(self):
        self.is_recording = False
        if hasattr(self, 'recording_thread') and self.recording_thread:
            self.recording_thread.join()

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
        auto_save=True,
        segment_duration=5.0  # 3秒分段
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
