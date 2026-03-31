from __future__ import annotations

import contextlib
import io
import os
import textwrap
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List

import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
import pandas as pd
from dotenv import load_dotenv
from zhipuai import ZhipuAI


PANDAS_ALIAS = "df"


@dataclass
class AgentResult:
    raw_code: str
    stdout: str
    summary: str
    plots: List[Any]
    tables: List[pd.DataFrame]
    thoughts: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_code": self.raw_code,
            "stdout": self.stdout,
            "summary": self.summary,
            "plots": self.plots,
            "tables": self.tables,
            "thoughts": self.thoughts,
        }


SYSTEM_INSTRUCTION = textwrap.dedent(
    f"""
    你是一个专业的数据分析 Python Agent，接收用户的自然语言问题和一个 pandas.DataFrame（变量名为 `{PANDAS_ALIAS}`）。

    **你的唯一输出应该是一段可以直接执行的 Python 代码**，不要包含任何解释性文字、Markdown 或注释块的外层说明。

    要求：
    1. 直接使用已存在的 DataFrame 变量 `{PANDAS_ALIAS}`，不要重新读取文件。
    2. 所有绘图请使用 matplotlib 或 seaborn，调用 plt.show() 之前的所有图像会被自动捕获。
    3. 将最重要的文字结论保存到变量 `summary_text`（str）。
    4. 如有关键表格结果，请收集为 pandas.DataFrame 放入列表 `result_tables`。
    5. 请**不要**调用 input()、也不要进行阻塞式交互。
    6. 代码末尾必须保证存在以下三个变量：
       - `summary_text`: str，对分析的简洁文字总结（可使用中文）。
       - `result_tables`: list[pandas.DataFrame]，可为空列表。
       - `plt`: matplotlib.pyplot 模块（已导入）。

    只返回可以执行的 Python 代码本体，不要写任何其它说明文字。
    """
)


def build_prompt(user_question: str, df: pd.DataFrame) -> str:
    sample_info = df.head(5).to_markdown()
    schema_lines = [f"- {col}: {dtype}" for col, dtype in df.dtypes.items()]
    schema_str = "\n".join(schema_lines)

    return textwrap.dedent(
        f"""
        {SYSTEM_INSTRUCTION}

        ----------------
        下面是当前数据表 `{PANDAS_ALIAS}` 的列信息和前 5 行示例：

        列及类型：
        {schema_str}

        数据示例（前 5 行）：
        {sample_info}

        ----------------
        用户的分析需求如下（可以用中文）： 
        {user_question}
        """
    )


def call_llm_to_generate_code(prompt: str) -> str:
    """
    使用智谱清言 GLM-4.6V-Plus 模型，将 Prompt 转换为可执行的 Python 代码。

    要求：
    - 只返回 Python 代码本体，不包含 ```python / ``` 等代码块标记。
    - 代码中直接操作已有的 DataFrame 变量 `df`。
    """
    # 加载 .env（如果已经在外部加载，多次调用也不会有副作用）
    load_dotenv()

    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未找到 ZHIPUAI_API_KEY 环境变量。请在 .env 中设置 ZHIPUAI_API_KEY=你的APIKey，"
            "并确保运行前已加载 .env（或直接在系统环境变量中设置）。"
        )

    client = ZhipuAI(api_key=api_key)

    response = client.chat.completions.create(
        model="glm-4.6v-flash",
        messages=[
            {
                "role": "system",
                "content": "你是一个专业的数据分析 Python Agent，只输出可直接执行的 Python 代码。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content

    # 智谱的 content 可能是 list 或 str，不同 SDK 版本略有差异，这里做一下兼容处理
    if isinstance(content, list):
        # 新版 SDK 可能返回 [{"type": "text", "text": "...."}]
        code = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    else:
        code = str(content)

    # 去掉可能出现的 Markdown 代码块包裹
    code = code.strip()
    if code.startswith("```"):
        # 去掉 ```python 或 ``` 开头
        first_newline = code.find("\n")
        if first_newline != -1:
            code = code[first_newline + 1 :]
        # 去掉末尾 ```
        if code.endswith("```"):
            code = code[: -3]
        code = code.strip()

    return code


def _setup_chinese_font() -> None:
    """
    为 matplotlib 设置一个支持中文的字体，避免中文变成方框。
    在 macOS 上优先使用 PingFang SC / Songti SC。
    """
    candidate_fonts = ["PingFang SC", "Songti SC", "STHeiti", "SimHei"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidate_fonts:
        if name in available:
            rcParams["font.family"] = name
            rcParams["axes.unicode_minus"] = False
            break


def execute_generated_code(df: pd.DataFrame, code: str) -> AgentResult:
    global_ns: Dict[str, Any] = {
        PANDAS_ALIAS: df,
        "pd": pd,
        "plt": plt,
    }
    local_ns: Dict[str, Any] = {}

    stdout_buffer = io.StringIO()

    # 全局设置一次中文字体
    _setup_chinese_font()

    with contextlib.redirect_stdout(stdout_buffer):
        exec(code, global_ns, local_ns)

    summary_text = local_ns.get("summary_text", "")
    if not isinstance(summary_text, str):
        summary_text = str(summary_text)

    result_tables = local_ns.get("result_tables", [])
    if not isinstance(result_tables, list):
        result_tables = [result_tables]

    tables: List[pd.DataFrame] = []
    for t in result_tables:
        if isinstance(t, pd.DataFrame):
            tables.append(t)

    figures: List[Any] = []
    for fig_num in plt.get_fignums():
        figures.append(plt.figure(fig_num))

    stdout_value = stdout_buffer.getvalue()

    return AgentResult(
        raw_code=code,
        stdout=stdout_value,
        summary=summary_text,
        plots=figures,
        tables=tables,
    )


def run_analysis_agent(df: pd.DataFrame, user_question: str) -> Dict[str, Any]:
    """
    顶层封装：构建 prompt -> 调用 LLM 生成代码 -> 执行代码。
    目前只做单轮生成与执行；你可以自行扩展为多轮错误重试。
    """
    prompt = build_prompt(user_question, df)

    try:
        code = call_llm_to_generate_code(prompt)
    except Exception as e:
        tb = traceback.format_exc()
        raise RuntimeError(f"调用大模型生成代码失败：{e}\n{tb}") from e

    try:
        result = execute_generated_code(df, code)
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        error_msg = f"执行生成代码时出错：{e}\n\nTraceback:\n{tb}"
        return AgentResult(
            raw_code=code,
            stdout=error_msg,
            summary="生成的分析代码在执行时发生错误，请根据错误信息调整 prompt 或代码实现。",
            plots=[],
            tables=[],
            thoughts=prompt,
        ).to_dict()

    result.thoughts = f"以下是本次生成代码时使用的系统提示与上下文：\n\n{prompt}"
    return result.to_dict()

