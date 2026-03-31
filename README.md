## 自动化数据分析师（Data Analyst Agent）

**一句话说明**：  
上传一份 Excel / CSV，直接用自然语言提问，Agent 自动编写并执行 Python 代码，返回分析结论、表格和图表。

---

### 1. 项目亮点

- **自然语言问数据**：不用写 SQL / Python，直接用中文/英文提问。
- **自动写代码并执行**：Agent 基于大模型自动生成 Python 分析脚本，并在本地沙盒里执行。
- **可视化开箱即用**：支持基于 `matplotlib` 的折线图、柱状图等图表自动生成。
- **结果可复用**：界面展示最终执行代码，方便你拷贝到笔记本或生产环境复用。

---

### 2. 环境准备与运行

- **Python 版本**：建议 3.10+

在本仓库根目录下：

```bash
cd "Data Analyst Agent"
pip install -r requirements.txt
```

启动 Web 界面：

```bash
streamlit run app.py
```

浏览器将自动打开一个页面（默认 `http://localhost:8501`），即可开始使用。

---

### 3. 智谱清言（GLM）配置

本项目默认接入 **智谱清言 GLM-4.6V-Flash** 模型，用于自动生成分析代码。

1. 在项目目录下创建（或编辑）`.env` 文件，写入：

   ```env
   ZHIPUAI_API_KEY=你的智谱清言API密钥
   ```

2. 关键代码位于 `agent_core.py`：

   - 使用 `python-dotenv` 自动加载 `.env`
   - 使用 `zhipuai` 官方 SDK 调用：

   ```python
   from zhipuai import ZhipuAI

   client = ZhipuAI(api_key=os.getenv("ZHIPUAI_API_KEY"))
   response = client.chat.completions.create(
       model="glm-4.6v-flash",
       messages=[
           {"role": "system", "content": "你是一个专业的数据分析 Python Agent，只输出可直接执行的 Python 代码。"},
           {"role": "user", "content": prompt},
       ],
       temperature=0.1,
   )
   ```

> 如果你不使用智谱清言，也可以在 `agent_core.py` 中自行替换为 OpenAI / DeepSeek 等其它模型调用方式。

---

### 4. 使用方式

1. **准备数据**
   - 在左侧侧边栏上传一份 **CSV / Excel** 文件，或  
   - 直接使用仓库中自带的示例文件 `data.csv`（已在界面左侧提供勾选）。

2. **自然语言提问**
   在文本框中输入你的问题，例如：

   - “帮我分析一下上个月各个地区的销售转化率并画出趋势图”
   - “按地区汇总销售额，画一个柱状图，并给出结论”

3. 点击 **“运行分析”** 按钮，等待 Agent：
   - 自动生成 Python 分析代码
   - 在本地沙盒环境中执行
   - 输出：
     - 文本结论（Summary）
     - 中间结果表格（Tables）
     - 可视化图表（Charts）
     - 标准输出（stdout）与最终代码（便于调试与复用）

---

### 5. Agent 约定与执行沙盒

在 `agent_core.py` 中，对大模型生成的代码有以下约束：

- **数据输入**：
  - 已经存在一个 `pandas.DataFrame` 变量：`df`
  - 代码必须直接操作这个 `df`，不要重新读文件。
- **绘图**：
  - 使用 `matplotlib.pyplot`（已通过 `plt` 传入），必要时可以导入 `seaborn`
  - 项目在执行前统一设置了支持中文的字体，避免中文乱码。
- **必须输出的变量**：
  - `summary_text: str`：对本次分析的自然语言总结（建议中文）
  - `result_tables: list[pd.DataFrame]`：重要结果表格（可以为空列表）
  - `plt`：`matplotlib.pyplot` 对象（保持可用）
- **禁止行为**：
  - 再次读取原始数据文件（例如对同一数据源重复 `read_csv`）
  - 使用 `input()` 等阻塞式交互调用

执行流程：

1. `build_prompt` 会根据 `df` 的列名、类型和前 5 行样本，构造一段详细 Prompt。
2. `call_llm_to_generate_code` 调用大模型，返回一段纯 Python 代码字符串。
3. `execute_generated_code` 在受控环境中 `exec` 这段代码，并收集：
   - 控制台输出（stdout）
   - 所有 matplotlib 图表
   - 大模型代码里定义的 `summary_text` 和 `result_tables`

---

### 6. 目录结构

- `app.py`：Streamlit Web 界面入口，负责文件上传、提问、展示结果。
- `agent_core.py`：Agent 核心逻辑
  - Prompt 构建（根据 DataFrame 结构和用户问题）
  - 调用大模型生成 Python 代码
  - 在本地沙盒中执行代码，收集输出 / 图表 / 表格
- `data.csv`：示例数据（日期、地区、访问量、转化单量、销售额）
- `requirements.txt`：Python 依赖清单
- `.env`：本地环境变量文件（存放 `ZHIPUAI_API_KEY`，不会被提交到 Git，因为已在 `.gitignore` 中忽略）
- `.gitignore`：Git 忽略配置

---

### 7. 路线图与可扩展方向

- **错误自愈**：将执行错误回传给大模型，自动重写和修复代码。
- **分析模板库**：预设常见 BI 问题（如漏斗分析、留存分析、AB 实验对比）的一键 Prompt。
- **报告导出**：将文本 + 图表导出为 PDF / PPTX，生成完整分析报告。
- **安全与隔离**：
  - 限制可用标准库与第三方库，减少潜在危险操作
  - 使用 `ast` / 静态分析工具，对大模型生成的代码做安全审计

