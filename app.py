import io
import traceback
from pathlib import Path

import pandas as pd
import streamlit as st

from agent_core import run_analysis_agent


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data.csv"


def load_default_data() -> pd.DataFrame | None:
    if DEFAULT_DATA_PATH.exists():
        try:
            return pd.read_csv(DEFAULT_DATA_PATH)
        except Exception:
            return None
    return None


def main() -> None:
    st.set_page_config(page_title="自动化数据分析师", layout="wide")

    st.title("🔍 自动化数据分析师 (Data Analyst Agent)")
    st.markdown(
        """
利用自然语言，自动生成并执行 Python 数据分析代码。  

1. **上传一份 Excel/CSV 数据集，或使用内置示例数据**  
2. **用中文/英文描述你的问题**（例如：`帮我分析一下上个月各个地区的销售转化率并画出趋势图`）  
3. Agent 会自动编写、运行代码，并返回 **结果表格与可视化图表**。
        """
    )

    with st.sidebar:
        st.header("数据设置")
        uploaded_file = st.file_uploader("上传 Excel/CSV 文件", type=["csv", "xlsx", "xls"])
        use_example = st.checkbox("使用示例数据 data.csv", value=not bool(uploaded_file))

    df: pd.DataFrame | None = None
    data_name = ""

    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            data_name = uploaded_file.name
        except Exception as e:
            st.error(f"读取上传文件失败：{e}")

    if df is None and use_example:
        df = load_default_data()
        data_name = "data.csv（示例数据）"

    if df is None:
        st.warning("请上传数据文件，或勾选左侧的“使用示例数据 data.csv”。")
        return

    st.subheader("当前数据预览")
    st.caption(f"数据源：{data_name}")
    st.dataframe(df.head(20), use_container_width=True)

    st.markdown("---")
    st.subheader("自然语言提问")
    question = st.text_area(
        "请输入你的分析需求：",
        value="帮我分析一下各个地区的销售转化率随时间的变化，并画出趋势图。",
        height=120,
    )

    col_run, col_clear = st.columns([2, 1])
    with col_run:
        run_clicked = st.button("🚀 运行分析", type="primary", use_container_width=True)
    with col_clear:
        clear_clicked = st.button("清空输出", use_container_width=True)

    if clear_clicked:
        st.session_state.pop("agent_result", None)
        st.experimental_rerun()

    if not run_clicked:
        if "agent_result" in st.session_state:
            render_result(st.session_state["agent_result"])
        return

    if not question.strip():
        st.error("请输入你的分析需求。")
        return

    with st.spinner("正在调用 Agent 自动编写并执行分析代码，请稍候..."):
        try:
            result = run_analysis_agent(df, question)
            st.session_state["agent_result"] = result
        except Exception as e:
            st.error("Agent 运行过程中出现未捕获的异常。")
            st.exception(e)
            return

    render_result(st.session_state["agent_result"])


def render_result(result: dict) -> None:
    st.markdown("---")
    st.subheader("分析结果")

    if "thoughts" in result and result["thoughts"]:
        with st.expander("Agent 思考过程 / 系统提示", expanded=False):
            st.markdown(result["thoughts"])

    if "stdout" in result and result["stdout"]:
        st.markdown("**代码输出（stdout）**")
        st.code(result["stdout"], language="bash")

    if "summary" in result and result["summary"]:
        st.markdown("**文本结论**")
        st.markdown(result["summary"])

    plots = result.get("plots", [])
    if plots:
        st.markdown("**图表展示**")
        cols = st.columns(2)
        for i, fig in enumerate(plots):
            with cols[i % 2]:
                st.pyplot(fig, clear_figure=False)

    tables = result.get("tables", [])
    if tables:
        st.markdown("**数据表格输出**")
        for idx, t in enumerate(tables, start=1):
            st.caption(f"表格 {idx}")
            st.dataframe(t, use_container_width=True)

    if "raw_code" in result and result["raw_code"]:
        with st.expander("查看最终执行的 Python 代码", expanded=False):
            st.code(result["raw_code"], language="python")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()

