#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鹅鸭杀游戏AI分析模块

基于LangGraph实现，分析玩家发言记录，推理身份关系。
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
from dataclasses import dataclass, field
import logging
from dotenv import load_dotenv

# LangGraph和OpenAI导入
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class Record:
    """发言记录"""
    timestamp: str
    text: str
    emotion: str
    speaker: str
    duration: float
    round: int


@dataclass
class PlayerInfo:
    """玩家信息"""
    id: str
    name: str


@dataclass
class PlayerAnalysis:
    """单个玩家的分析结果"""
    playerId: str
    playerName: str
    identityGuess: str  # "goose", "duck", "neutral", "unknown"
    confidence: float  # 0-1
    reasoning: str
    suspiciousPoints: List[str] = field(default_factory=list)
    trustworthyPoints: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    """玩家之间的关系"""
    from_player: str
    to_player: str
    relation_type: str  # "ally", "enemy", "neutral", "suspicious"
    evidence: str


@dataclass
class AnalysisResult:
    """完整分析结果"""
    round: int
    timestamp: str
    playerAnalysis: List[PlayerAnalysis]
    relationshipMap: List[Relationship]
    summary: str


# LangGraph State定义
class AnalysisState(TypedDict):
    """分析工作流状态"""
    records: List[Record]
    players: List[PlayerInfo]
    round: int
    client: Optional[AsyncOpenAI]
    prepared_text: Optional[str]
    analysis_json: Optional[Dict]
    final_result: Optional[AnalysisResult]
    error: Optional[str]


class GooseGooseDuckAIAnalyzer:
    """鹅鸭杀AI分析器 - 基于大模型"""

    # 系统Prompt
    SYSTEM_PROMPT = """你是一位鹅鸭杀游戏分析专家，擅长通过分析玩家发言来推理身份。

【游戏规则】
- 鹅（好人阵营）：需要完成任务或找出所有鸭子获胜
- 鸭子（坏人阵营）：需要隐藏身份，通过击杀鹅和破坏任务获胜
- 中立角色：有各自的独立获胜条件

【分析维度】
1. 发言逻辑一致性
2. 信息的真实性
3. 与其他玩家的互动模式
4. 情绪变化
5. 投票倾向

你必须以JSON格式输出分析结果，不要输出任何其他文字。"""

    # LLM分析Prompt
    ANALYSIS_PROMPT = """请分析以下鹅鸭杀游戏第{round}轮的发言记录，推理每位玩家的身份和相互关系。

【玩家信息】
{players_info}

【发言记录】
{records_text}

请输出以下JSON格式的分析结果：
{{
    "playerAnalysis": [
        {{
            "playerId": "玩家编号",
            "playerName": "玩家名称",
            "identityGuess": "goose|duck|neutral|unknown",
            "confidence": 0.0-1.0,
            "reasoning": "详细的推理说明（100字以内）",
            "suspiciousPoints": ["可疑点1", "可疑点2"],
            "trustworthyPoints": ["可信点1"]
        }}
    ],
    "relationshipMap": [
        {{
            "from": "玩家A编号",
            "to": "玩家B编号",
            "type": "ally|enemy|suspicious|neutral",
            "evidence": "关系证据说明"
        }}
    ],
    "summary": "总体分析总结（200字以内），包括本轮关键发现和建议"
}}

注意事项：
1. identityGuess只能是：goose（鹅/好人）、duck（鸭子/坏人）、neutral（中立）、unknown（未知）
2. confidence表示置信度，0.0-1.0之间
3. relationshipMap中type只能是：ally（同盟）、enemy（敌对）、suspicious（可疑）、neutral（中立）
4. 如果信息不足，identityGuess可以是unknown，confidence设低一些
5. 只输出JSON，不要有任何其他文字"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化分析器

        Args:
            api_key: /OpenAI API密钥，如果不提供则尝试从环境变量获取
            base_url: API基础URL，用于等兼容OpenAI接口的服务
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL")
        self.model = os.getenv("DEEPSEEK_MODEL")
        self._analysis_results: Dict[int, AnalysisResult] = {}
        self._client: Optional[AsyncOpenAI] = None
        self._graph = self._build_graph()

    def _get_client(self) -> Optional[AsyncOpenAI]:
        """获取或创建OpenAI客户端"""
        if self._client is None and self.api_key:
            try:
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                logger.info("[LLM] OpenAI客户端初始化成功")
            except Exception as e:
                logger.error(f"[LLM] 客户端初始化失败: {e}")
        return self._client

    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(AnalysisState)

        # 添加节点
        workflow.add_node("data_prep", self._data_prep_node)
        workflow.add_node("llm_analysis", self._llm_analysis_node)
        workflow.add_node("parse_result", self._parse_result_node)
        workflow.add_node("output", self._output_node)

        # 设置入口点
        workflow.set_entry_point("data_prep")

        # 添加边
        workflow.add_edge("data_prep", "llm_analysis")
        workflow.add_edge("llm_analysis", "parse_result")
        workflow.add_edge("parse_result", "output")
        workflow.add_edge("output", END)

        return workflow.compile()

    def _data_prep_node(self, state: AnalysisState) -> AnalysisState:
        """数据准备节点"""
        try:
            records = state["records"]
            players = state["players"]
            round_num = state["round"]

            # 构建玩家信息文本
            players_info = "\n".join([f"- {p.id}: {p.name}" for p in players])

            # 构建发言记录文本
            records_lines = []
            for r in records:
                player_name = next((p.name for p in players if p.id == r.speaker), f"玩家{r.speaker}")
                records_lines.append(
                    f"[{r.timestamp}] 玩家{r.speaker} ({player_name})\n"
                    f"  情绪: {r.emotion}, 时长: {r.duration:.1f}s\n"
                    f"  内容: {r.text}"
                )
            records_text = "\n".join(records_lines)

            state["prepared_text"] = self.ANALYSIS_PROMPT.format(
                round=round_num,
                players_info=players_info,
                records_text=records_text
            )
            logger.info(f"[DataPrep] 数据准备完成：{len(records)}条记录，{len(players)}位玩家")

        except Exception as e:
            logger.error(f"[DataPrep] 数据准备失败: {e}")
            state["error"] = str(e)

        return state

    async def _llm_analysis_node_async(self, state: AnalysisState) -> AnalysisState:
        """LLM分析节点 - 异步版本"""
        try:
            if state.get("error"):
                return state

            client = self._get_client()
            if client is None:
                logger.warning("[LLM] 未配置API密钥")
                state["error"] = "未配置 API密钥"
                return state

            prepared_text = state["prepared_text"]
            logger.info("[LLM] 开始调用大模型分析...")

            # 调用 API
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prepared_text}
                ],
                temperature=0.3,
                max_tokens=4096
            )

            content = response.choices[0].message.content
            logger.info(f"[LLM] 大模型返回内容长度: {len(content)}")

            # 尝试提取JSON
            try:
                json_start = content.find("{")
                json_end = content.rfind("}")
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start:json_end + 1]
                    analysis_json = json.loads(json_str)
                    state["analysis_json"] = analysis_json
                    logger.info("[LLM] JSON解析成功")
                else:
                    raise ValueError("未找到JSON内容")
            except json.JSONDecodeError as e:
                logger.error(f"[LLM] JSON解析失败: {e}")
                logger.error(f"[LLM] 原始内容: {content[:500]}...")
                state["error"] = f"JSON解析失败: {e}"

        except Exception as e:
            logger.error(f"[LLM] 调用失败: {e}")
            state["error"] = str(e)

        return state

    def _llm_analysis_node(self, state: AnalysisState) -> AnalysisState:
        """LLM分析节点 - 同步包装"""
        # 创建新的事件循环来运行异步代码
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环已经在运行，使用run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self._llm_analysis_node_async(state), loop
                )
                return future.result()
            else:
                return loop.run_until_complete(self._llm_analysis_node_async(state))
        except RuntimeError:
            # 没有事件循环，创建一个新的
            return asyncio.run(self._llm_analysis_node_async(state))

    def _parse_result_node(self, state: AnalysisState) -> AnalysisState:
        """结果解析节点"""
        try:
            if state.get("error") or not state.get("analysis_json"):
                return state

            analysis_json = state["analysis_json"]
            round_num = state["round"]

            # 解析玩家分析
            player_analysis_list = []
            for pa in analysis_json.get("playerAnalysis", []):
                player_analysis_list.append(PlayerAnalysis(
                    playerId=pa.get("playerId", ""),
                    playerName=pa.get("playerName", ""),
                    identityGuess=pa.get("identityGuess", "unknown"),
                    confidence=pa.get("confidence", 0.0),
                    reasoning=pa.get("reasoning", ""),
                    suspiciousPoints=pa.get("suspiciousPoints", []),
                    trustworthyPoints=pa.get("trustworthyPoints", [])
                ))

            # 解析关系图
            relationships = []
            for rel in analysis_json.get("relationshipMap", []):
                relationships.append(Relationship(
                    from_player=rel.get("from", ""),
                    to_player=rel.get("to", ""),
                    relation_type=rel.get("type", "neutral"),
                    evidence=rel.get("evidence", "")
                ))

            # 创建结果
            result = AnalysisResult(
                round=round_num,
                timestamp=datetime.now().isoformat(),
                playerAnalysis=player_analysis_list,
                relationshipMap=relationships,
                summary=analysis_json.get("summary", "")
            )

            state["final_result"] = result
            logger.info("[Parse] 结果解析成功")

        except Exception as e:
            logger.error(f"[Parse] 结果解析失败: {e}")
            state["error"] = str(e)

        return state

    def _output_node(self, state: AnalysisState) -> AnalysisState:
        """输出节点"""
        if state.get("error"):
            logger.error(f"[Output] 分析过程出错: {state['error']}")
        return state

    async def analyze_round(
        self,
        records: List[Record],
        players: List[PlayerInfo],
        round_num: int
    ) -> AnalysisResult:
        """分析指定轮次的游戏数据"""
        logger.info(f"[Analyze] 开始分析第{round_num}轮，{len(records)}条记录")

        # 检查是否有API密钥
        if not self.api_key:
            logger.warning("[Analyze] 未配置 API密钥")
            return self._create_fallback_result(records, players, round_num, "未配置 API密钥")

        # 初始化状态
        initial_state: AnalysisState = {
            "records": records,
            "players": players,
            "round": round_num,
            "client": None,
            "prepared_text": None,
            "analysis_json": None,
            "final_result": None,
            "error": None
        }

        # 执行工作流
        try:
            result_state = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._graph.invoke(initial_state)
            )

            if result_state.get("error"):
                logger.error(f"[Analyze] 分析过程出错: {result_state['error']}")
                return self._create_fallback_result(
                    records, players, round_num,
                    f"AI分析失败: {result_state['error']}"
                )

            final_result = result_state.get("final_result")
            if final_result:
                self._analysis_results[round_num] = final_result
                return final_result
            else:
                return self._create_fallback_result(records, players, round_num, "无分析结果")

        except Exception as e:
            logger.error(f"[Analyze] 分析执行失败: {e}")
            return self._create_fallback_result(records, players, round_num, str(e))

    def _create_fallback_result(
        self,
        records: List[Record],
        players: List[PlayerInfo],
        round_num: int,
        error_msg: str = ""
    ) -> AnalysisResult:
        """创建备用分析结果"""
        player_analysis_list = [
            PlayerAnalysis(
                playerId=p.id,
                playerName=p.name,
                identityGuess="unknown",
                confidence=0.0,
                reasoning=f"AI分析不可用: {error_msg}" if error_msg else "分析过程出错",
                suspiciousPoints=[],
                trustworthyPoints=[]
            )
            for p in players
        ]

        return AnalysisResult(
            round=round_num,
            timestamp=datetime.now().isoformat(),
            playerAnalysis=player_analysis_list,
            relationshipMap=[],
            summary=f"第{round_num}轮AI分析失败。{error_msg}" if error_msg else f"第{round_num}轮分析失败，请检查 API配置。"
        )

    def get_cached_result(self, round_num: int) -> Optional[AnalysisResult]:
        """获取缓存的分析结果"""
        return self._analysis_results.get(round_num)

    def save_result_to_file(self, result: AnalysisResult, output_dir: str = "analysis_results"):
        """保存分析结果到文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"round_{result.round}.json")

            data = {
                "round": result.round,
                "timestamp": result.timestamp,
                "playerAnalysis": [
                    {
                        "playerId": p.playerId,
                        "playerName": p.playerName,
                        "identityGuess": p.identityGuess,
                        "confidence": p.confidence,
                        "reasoning": p.reasoning,
                        "suspiciousPoints": p.suspiciousPoints,
                        "trustworthyPoints": p.trustworthyPoints
                    }
                    for p in result.playerAnalysis
                ],
                "relationshipMap": [
                    {
                        "from": r.from_player,
                        "to": r.to_player,
                        "type": r.relation_type,
                        "evidence": r.evidence
                    }
                    for r in result.relationshipMap
                ],
                "summary": result.summary
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"[Save] 分析结果已保存到: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"[Save] 保存结果失败: {e}")
            return None


# 全局分析器实例（单例模式）
_analyzer_instance: Optional[GooseGooseDuckAIAnalyzer] = None


def get_analyzer(api_key: Optional[str] = None, base_url: Optional[str] = None) -> GooseGooseDuckAIAnalyzer:
    """获取全局分析器实例"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = GooseGooseDuckAIAnalyzer(api_key, base_url)
    return _analyzer_instance


async def analyze_game_round(
    records_data: List[Dict[str, Any]],
    players_data: List[Dict[str, str]],
    round_num: int
) -> Dict[str, Any]:
    """便捷函数：分析游戏轮次"""
    # 转换数据格式
    records = [
        Record(
            timestamp=r.get("timestamp", ""),
            text=r.get("text", ""),
            emotion=r.get("emotion", "neutral"),
            speaker=r.get("speaker", "?"),
            duration=r.get("duration", 0.0),
            round=r.get("round", round_num)
        )
        for r in records_data
    ]

    players = [
        PlayerInfo(id=p.get("id", ""), name=p.get("name", ""))
        for p in players_data
    ]

    analyzer = get_analyzer()
    result = await analyzer.analyze_round(records, players, round_num)

    # 保存结果
    analyzer.save_result_to_file(result)

    # 返回字典格式
    return {
        "round": result.round,
        "timestamp": result.timestamp,
        "playerAnalysis": [
            {
                "playerId": p.playerId,
                "playerName": p.playerName,
                "identityGuess": p.identityGuess,
                "confidence": p.confidence,
                "reasoning": p.reasoning,
                "suspiciousPoints": p.suspiciousPoints,
                "trustworthyPoints": p.trustworthyPoints
            }
            for p in result.playerAnalysis
        ],
        "relationshipMap": [
            {
                "from": r.from_player,
                "to": r.to_player,
                "type": r.relation_type,
                "evidence": r.evidence
            }
            for r in result.relationshipMap
        ],
        "summary": result.summary
    }


if __name__ == "__main__":
    # 测试代码
    test_records = [
        Record(timestamp="12:00:01", text="我是好人，大家相信我", emotion="neutral", speaker="01", duration=5.0, round=1),
        Record(timestamp="12:00:10", text="我怀疑02号，他刚才行为可疑", emotion="suspicious", speaker="03", duration=8.0, round=1),
        Record(timestamp="12:00:20", text="我不是坏人，03号在乱咬人", emotion="angry", speaker="02", duration=6.0, round=1),
    ]

    test_players = [
        PlayerInfo(id="01", name="小明"),
        PlayerInfo(id="02", name="小红"),
        PlayerInfo(id="03", name="小刚"),
    ]

    analyzer = GooseGooseDuckAIAnalyzer()
    result = asyncio.run(analyzer.analyze_round(test_records, test_players, 1))

    print(f"\n分析结果（第{result.round}轮）：")
    print(f"总结: {result.summary}")
    print("\n玩家分析:")
    for p in result.playerAnalysis:
        print(f"  {p.playerId} ({p.playerName}): {p.identityGuess} (置信度: {p.confidence:.2f})")
        print(f"    推理: {p.reasoning}")
