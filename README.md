# AIOS-NP

AIOS-NP 是一个基于 AIOS 的新闻 Agent 系统。项目从竞赛型多智能体流水线重构而来，现在的重点是：

- 用 `apps/news_app` 统一编排新闻工作流
- 用 AIOS kernel 提供 LLM / storage / memory runtime
- 用 ecosystem service 提供 dashboard、run API、report API、dynamic agent registry
- 用 editorial gates 和 workflow memory 提高新闻生成质量

如果你准备系统学习这个项目，优先看：

- `项目文档.md`
- `apps/news_app/pipeline.py`
- `apps/news_app/ecosystem.py`
- `apps/news_app/service.py`
- `runtime_support/artifacts.py`
- `runtime_support/memory.py`
- `agents/maker_agent/agent.py`

## 当前主入口

运行一次工作流：

```bash
cd /home/ubuntu/owen/AIOS-NP
./.conda-env/bin/python run_news_app.py --mode serial
./.conda-env/bin/python run_news_app.py --mode parallel
```

启动 AIOS kernel：

```bash
bash ./scripts/start_local_kernel.sh
```

启动 ecosystem service：

```bash
bash ./scripts/start_news_ecosystem.sh
```

## 工作流阶段

主阶段顺序由 `config.json` 定义：

```json
["hot_api", "sort", "search", "generate", "review", "report"]
```

含义如下：

1. `hot_api`：抓取多平台热榜
2. `sort`：分类、去重、重路由
3. `search`：为热点补充搜索证据材料
4. `generate`：生成标题、摘要、正文，并做 generation gate
5. `review`：审阅、优化、事实核查
6. `report`：汇总成日报，输出 TXT / JSON / HTML

## 核心目录

```text
AIOS-NP/
├── aios/                  AIOS kernel 能力层
├── cerebrum/              SDK / API 层
├── apps/news_app/         新闻业务应用层
├── agents/                各类 agent 实现
├── runtime_support/       artifact store / workflow memory
├── tests/                 当前正式单测
├── scripts/               启动、自检、辅助脚本
├── run_news_app.py        推荐 CLI 入口
├── parallel_pipeline.py   旧并行入口，现为兼容包装
└── serial_pipeline.py     旧串行入口，现为兼容包装
```

## 线上服务入口

- AIOS kernel: `http://127.0.0.1:8001`
- news ecosystem: `http://127.0.0.1:8010`

常用接口：

- `/health`
- `/dashboard`
- `/api/ecosystem/runs`
- `/api/ecosystem/state/latest`
- `/api/ecosystem/metrics/latest`
- `/api/ecosystem/reports/latest/html`
- `/api/agents`

## 开发建议

如果你准备继续整理这个仓库并上传 GitHub，建议先做三件事：

1. 使用 `.gitignore` 屏蔽 `intermediate/`、`output/`、`ecosystem/` 等运行产物
2. 保持 `项目文档.md` 作为唯一主说明文档，避免多份重构文档继续分叉
3. 上传前重新跑一遍：

```bash
./.conda-env/bin/python -m unittest discover -s tests -q
./.conda-env/bin/python scripts/news_app_doctor.py
```

1. **克隆项目**
```bash
git clone <repository-url>
cd AIOS-NP
```

2. **安装依赖**
```bash
./scripts/setup_local_env.sh
```

3. **配置模型**
```bash
# 将模型文件放置在 model/ 目录下
# 确保模型路径在 config.json 中正确配置
```

4. **启动AIOS内核**
```bash
./scripts/start_local_kernel.sh
```

提示：
- 这套项目本机建议使用 Python 3.10。
- 启动内核只解决 AIOS 服务本身；真正发起 LLM 请求前，还需要有一个 OpenAI 兼容模型服务跑在 `http://localhost:5711/v1`，或按你的实际地址修改 [aios/config/config.yaml](./aios/config/config.yaml)。
- 外部 API 密钥建议写到 `.env.local`，可以从 [.env.local.example](./.env.local.example) 复制。
- 如果你用第三方 OpenAI 兼容接口，可以直接在 `.env.local` 里设置 `OPENAI_API_KEY`、`AIOS_LLM_MODEL`、`AIOS_LLM_BACKEND=openai`、`AIOS_LLM_BASE_URL`，不必再改代码。

5. **运行新闻生成流水线**

#### 并行流水线（推荐）
```bash
python parallel_pipeline.py --zh_api_key YOUR_API_KEY --tavily_api_key YOUR_TAVILY_KEY
```

#### 串行流水线（效率对比）
```bash
python serial_pipeline.py --zh_api_key YOUR_API_KEY --tavily_api_key YOUR_TAVILY_KEY
```

#### 定时任务（每天0点自动生成）
```bash
# 1. 设置环境变量
export ZH_API_KEY="your_zh_api_key"
export TAVILY_API_KEY="your_tavily_api_key"

# 2. 添加到crontab
crontab -e
# 添加以下行：
# 0 0 * * * /home/ubuntu/owen/AIOS-NP/daily_news_cron.sh

# 3. 手动执行定时脚本
./daily_news_cron.sh
```

### 配置说明

编辑 `config.json` 文件：

```json
{
    "aios_kernel_url": "http://localhost:8001",
    "model_config": {
        "model_path": "./model/qwen2.5-7b",
        "max_tokens": 32768,
        "temperature": 0.7
    },
    "search_config": {
        "tavily_api_key": "your_tavily_key",
        "max_results": 5
    },
    "news_config": {
        "max_length": 500,
        "min_length": 300
    }
}
```

## 📜 脚本说明

### 并行流水线 (`parallel_pipeline.py`)
- **功能**: 主要的新闻生成流水线，采用并行处理
- **特点**: 6个领域并行处理，效率最高
- **适用**: 生产环境，追求最高效率

### 串行流水线 (`serial_pipeline.py`)
- **功能**: 串行版本的新闻生成流水线，用于效率对比
- **特点**: 所有步骤串行执行，便于调试和对比
- **适用**: 调试、效率对比、资源受限环境

### 定时任务脚本 (`daily_news_cron.sh`)
- **功能**: 每天0点自动生成新闻报
- **特点**: 自动检查AIOS内核状态，完整的错误处理
- **适用**: 生产环境自动化部署

## 🔄 工作流程

### 1. 数据获取阶段
- **hot_api_agent**: 从多个平台获取热榜数据
- **sort_agent**: 对热点进行分类整理，生成6个领域文件

### 2. 并行搜索阶段
- **web_search_agent**: 为每个领域并行搜索相关新闻资料
- 使用Tavily Search API获取高质量搜索结果

### 3. 并行生成阶段
- **news_generation_agent**: 为每个领域并行生成新闻
- 子Agent协作：标题↔评判、摘要↔评判、内容↔评判

### 4. 并行审阅阶段
- **workflow_agent**: 组织审阅工作流
- **领域专家**: 提供专业领域优化建议
- **审议Agent**: 进行安全性、结构、叙述、事实核查

### 5. 新闻制作阶段
- **maker_agent**: 收集所有审阅后的新闻
- 生成统一的新闻报告，包含信源信息

## 📊 性能特点

### 并行处理能力
- **6个领域并行**: 科技、民生、商业、社会、娱乐、争议
- **多Agent协作**: 19个Agent协同工作
- **异步执行**: 支持大规模并行处理

### 质量保证
- **多级审议**: 5个审议Agent确保内容质量
- **事实核查**: 基于原始搜索数据的准确性验证
- **专业优化**: 6个领域专家提供专业建议

### 资源优化
- **端侧部署**: 适配7-8B模型，降低部署成本
- **内存管理**: 智能的中间文件存储机制
- **错误恢复**: 自动重试和错误处理机制

## 🛠️ 开发指南

### 添加新领域专家

1. 在 `agents/` 目录下创建新的专家目录
2. 实现专家Agent类，继承基础Agent
3. 在 `workflow_agent.py` 中注册新专家
4. 更新配置文件

### 自定义审议Agent

1. 在 `agents/` 目录下创建新的审议Agent
2. 实现审议逻辑和评分机制
3. 在 `workflow_agent.py` 中集成新Agent
4. 配置审议流程

### 扩展搜索源

1. 修改 `web_search_agent` 添加新的搜索API
2. 实现搜索结果解析逻辑
3. 更新配置文件和API密钥管理

## 📈 监控与调试

### 日志系统
- 每个Agent都有详细的执行日志
- 支持不同级别的日志输出
- 错误追踪和性能监控

### 中间文件
- 所有中间结果都保存在 `intermediate/` 目录
- 便于调试和问题排查
- 支持断点续传

### 性能统计
- 详细的执行时间统计
- 各阶段性能分析
- 资源使用监控

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- AIOS框架团队
- Qwen模型团队
- Tavily Search API
- 所有贡献者

---

**AIOS-NP** - 让AIOS更智能，让新闻生成更高效！ 🚀
