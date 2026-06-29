# Poker Hands Analyzer

一个面向 Bovada hand history 的本地扑克复盘与玩家池分析项目。第一版目标是把原始手牌安全地导入本地 DuckDB，建立可追踪的复盘队列，导出经过脱敏的 GTOWizard 手牌，并为后续 MDA、node 统计、range 聚合留下清晰扩展点。

## 核心原则

- **不修改 Bovada 原始目录**：不会移动、重命名、删除，也不会在原始目录旁边写 sidecar 文件。
- **所有真实数据只进 `dataset/`**：DuckDB、Parquet、JSONL、导出文件、日志、临时文件都放在项目根目录的 `dataset/` 下。
- **`dataset/` 不进 git**：仓库只保存代码、配置模板、测试 fixture 和文档。
- **增量导入**：通过本项目自己的 DuckDB import ledger 记录文件 hash、路径、状态和导入时间。
- **手牌去重**：同一文件不会重复导入；同一手牌重复出现在不同文件里时，主表按 hand id/hash 去重。
- **GTOWizard 本地导出**：第一版不假设 GTOWizard API 存在，只生成本地脱敏 hand history 和 manifest，供手动上传和手动标记结果。

## 项目结构

```text
poker-hands-analyzer/
  config/                  # 配置模板、node 定义模板
  src/pokermda/            # Python package
  tests/                   # pytest tests and fixtures
  notebooks/               # 本地探索笔记说明
  dataset/                 # 本地数据目录，已 gitignore
```

`src/pokermda/` 的主要模块：

- `config/`：读取本地配置，统一管理路径。
- `ingest/`：扫描 Bovada txt、import ledger、hand block split、Bovada parser、parse error。
- `db/`：DuckDB 连接、schema 和迁移入口。
- `normalize/`：把 bronze raw block 解析成 hands、participants、actions、player facts。
- `features/`：位置、下注线、sizing bucket、board texture、SPR 等特征。
- `spots/`：后续构建可研究的 decision opportunity。
- `nodes/`：MDA node spec、registry、query、aggregate、export。
- `ranges/`：combo index、range matrix、range aggregate、heatmap export。
- `stats/`：频率聚合、置信区间、hero vs pool。
- `review/`：hand scorer、study queue、GTOWizard tracking、notes、drills。
- `exporters/`：GTOWizard 脱敏导出、manifest、格式适配。
- `reports/`：daily/weekly report。

## 环境要求

- Python 3.11+
- DuckDB
- Typer
- Rich
- PyYAML
- pytest

安装开发环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

如果你使用 Codex 内置 Python 或其他解释器，只要能安装 `pyproject.toml` 里的依赖即可。

## 本地配置

复制模板：

```bash
cp config/local.example.yaml config/local.yaml
```

`config/local.yaml` 已被 `.gitignore` 忽略。它不应该保存秘密，只保存本机路径和偏好。

默认示例路径：

```yaml
project_root: "/Users/dongbosun/Desktop/poker手牌复盘/bovada手牌/poker-hands-analyzer"
dataset_dir: "/Users/dongbosun/Desktop/poker手牌复盘/bovada手牌/poker-hands-analyzer/dataset"
bovada_raw_hand_history_dir: "/Users/dongbosun/Bovada.lv Poker/Hand History"
duckdb_path: "/Users/dongbosun/Desktop/poker手牌复盘/bovada手牌/poker-hands-analyzer/dataset/db/poker.duckdb"
```

## 初始化

```bash
pokermda init
```

初始化会创建：

```text
dataset/
  raw/
    bovada_hand_history -> /Users/dongbosun/Bovada.lv Poker/Hand History
  db/
    poker.duckdb
  lake/
    bronze/raw_hand_blocks/
    silver/hands/
    silver/participants/
    silver/actions/
    silver/results/
    silver/player_hand_facts/
    gold/decision_instances/
    gold/node_instances/
    gold/stat_aggregates/
    gold/range_aggregates/
    gold/review_candidates/
  exports/
    gtowizard/
    review_queue/
    ranges/
  review/
    notes/
    screenshots/
    gtowizard_manual_results/
  logs/
  tmp/duckdb/
  ledger/
```

初始化会尝试在 `dataset/raw/bovada_hand_history` 创建指向 Bovada 原始目录的 symlink。失败时不会中断，导入仍然可以直接使用配置里的 `bovada_raw_hand_history_dir`。

## 导入流程

```bash
pokermda ingest
```

导入行为：

1. 递归扫描 `bovada_raw_hand_history_dir` 下所有 `.txt` 文件。
2. 对每个文件计算 SHA-256。
3. 查询 DuckDB import ledger。
4. 已成功导入过的文件 hash 会跳过，同时记录当前路径为 duplicate/skipped。
5. 新文件会拆分成 hand block，写入 `bronze_raw_hand_blocks`。
6. parser 尝试生成 `hands`、`participants`、`actions`。
7. 解析失败不会终止导入，会写入 `parse_errors` 并继续处理后续手牌。

常用参数：

```bash
pokermda ingest --limit-files 20
pokermda ingest --source-dir "/Users/dongbosun/Bovada.lv Poker/Hand History"
```

## 数据库基本信息

以后需要快速确认数据库状态时运行：

```bash
pokermda profile
```

它会输出：

- DuckDB 里有多少手牌。
- bronze raw hand blocks 数量。
- parse error 数量。
- Bovada 原始目录里有多少 `.txt` 文件。
- 按文件 hash 判断已经完成入库的原始文件数。
- 按文件 hash 判断尚未入库的原始文件数。
- import ledger 中 imported / skipped duplicate / failed 文件路径数量。

机器可读输出：

```bash
pokermda profile --json
```

## 每天复盘流程

推荐日常流程：

1. 在 Bovada 客户端导出所有 hands。
2. 在本项目运行：

```bash
pokermda ingest
```

3. 生成或更新复盘队列：

```bash
pokermda queue build --limit 50
pokermda queue list
```

4. 导出待研究手牌到 GTOWizard：

```bash
pokermda gtowizard export --limit 20
```

5. 打开 `dataset/exports/gtowizard/`，手动上传脱敏后的 txt 到 GTOWizard。
6. 学习后把结果、截图、笔记放到：

```text
dataset/review/gtowizard_manual_results/
dataset/review/screenshots/
dataset/review/notes/
```

7. 手动标记导出结果：

```bash
pokermda gtowizard mark --export-id EXPORT_ID --status reviewed --notes "river call too loose"
```

8. 后续 MDA 和 node 分析会读取同一个 DuckDB，不需要重新解析原始文件。

## GTOWizard 脱敏导出

本项目不会把 Bovada fully revealed 原文直接作为 GTOWizard 导出物。导出器会：

- 保留 hero 手牌、公共牌和行动线。
- 对玩家名做稳定匿名化：`Hero`、`Villain1`、`Villain2` 等。
- 去掉或隐藏非 hero 的 hole cards。
- 去掉 summary 中可能泄露完整摊牌信息的行。
- 生成 `manifest.json`，记录导出时间、hand id、sanitizer version、源 hand hash，不包含完整原文。

## Node 与 MDA 扩展

`config/node_definitions/` 里有三个示例：

- river overbet
- flop cbet response
- turn barrel response

未来可以通过 YAML 定义 node 条件，再由 `pokermda nodes` 子命令加载、查询、聚合和导出。第一版保留 schema、模块和 CLI 占位，不强行实现复杂 poker edge cases。

## 测试

```bash
pytest
```

或：

```bash
make test
```

如果当前环境还没安装 `duckdb`，与 DuckDB 直接相关的测试会被跳过；安装项目依赖后应完整通过。

## 开发约定

- 全项目路径必须使用 `pathlib.Path`。
- 不要把真实 hand history、数据库、parquet、jsonl、日志、导出物提交进 git。
- Parser 初版只覆盖高频结构，遇到未知格式要写 parse error，不要崩溃。
- 新增表时同步更新 `src/pokermda/db/schema.sql` 和 README。
- 新增用户可执行功能时同步更新 CLI、README 和测试。
