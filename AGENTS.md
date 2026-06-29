# AGENTS.md

给未来 Codex/agent 的开发规则。本项目处理真实扑克手牌数据，首要目标是安全、可追踪、可扩展。

## Project mission

Build a local-first Bovada hand history review and MDA system. Daily review and safe GTOWizard export come first; advanced node mining and exploit candidates should grow on top of reliable ingestion, normalized tables, and tests.

## 数据安全边界

- 绝对不要修改、移动、重命名、删除 `/Users/dongbosun/Bovada.lv Poker/Hand History` 下的任何文件。
- 不要在 Bovada 原始目录或其子目录写 sidecar、marker、cache、log。
- 所有运行时数据必须写入项目根目录的 `dataset/`。
- `dataset/` 已 gitignore。不要把真实手牌、DuckDB、Parquet、JSONL、导出文件、日志或截图提交进 git。
- `config/local.yaml` 已 gitignore。配置模板可以提交，真实本地配置不要提交。
- Do not upload, paste, or exfiltrate real hand histories unless the user explicitly asks for a specific export workflow.
- Use fixture files under `tests/fixtures/`; never add real hand histories to tests.
- Do not run long full imports on real data unless the user explicitly asks. Prefer `scan-raw --dry-run` before real ingest.

## 技术约定

- Python 3.11+。
- 用 `pathlib.Path` 处理所有路径，兼容中文路径、空格和 `$` 字符。
- 主库是 DuckDB，不要把 PostgreSQL 或云数据库作为第一版依赖。
- Do not introduce cloud services, remote databases, or GTOWizard API assumptions without explicit user request.
- CLI 使用 Typer，终端输出使用 Rich。
- 配置使用 YAML 模板，运行时通过 dataclass 表达 settings。
- 测试使用 pytest。

## 架构约定

- `ingest/` 只负责发现文件、ledger、split、初级 parse。
- `normalize/` 负责把 parser 输出写入规范化表。
- `features/` 负责纯计算特征，不直接依赖 CLI。
- `spots/` 负责发现可研究机会点。
- `nodes/` 负责 node spec、实例构建、查询、聚合。
- `ranges/` 负责 combo/range 聚合与可视化导出。
- `review/` 负责 study queue、scoring、GTOWizard tracking、notes。
- `exporters/` 负责输出文件，所有 GTOWizard 导出必须脱敏。

## Parser 策略

- MVP parser 只需要覆盖常见 Bovada 文本结构。
- 遇到未知行不要失败，保留 raw_line。
- 遇到整手无法识别时写入 `parse_errors`，导入流程继续。
- 同一手牌重复出现时，按 `bovada_hand_number` 或 `hand_hash` 去重。
- 不要在 parser 中实现复杂统计逻辑。统计应放在 `features/`、`spots/`、`nodes/` 或 `stats/`。
- Parser must be conservative: preserve raw hand blocks exactly and log parse errors instead of dropping data.
- Parser changes require tests with fake/non-sensitive fixture hands.

## DuckDB 与 schema

- schema 的来源是 `src/pokermda/db/schema.sql`。
- `pokermda init` 应创建数据库并应用 schema。
- 新增表、列或索引时，同步更新测试与 README。
- ledger 必须记录 file hash 和 source path，不能依赖外部目录 marker。
- Schema/migration changes must be explicit and should be validated on a fresh temp DuckDB in tests.

## GTOWizard 导出

- 不要导出 fully revealed Bovada 原文。
- 必须使用 `exporters/sanitizer.py` 生成 hero-perspective 文本。
- 每批导出必须生成 `hands_gtowizard.txt`、`manifest.csv` 和 `manifest.json`。
- 第一版只支持手动上传和手动标记状态，不假设 GTOWizard API。
- Before changing the GTOWizard export format, update tests and README.

## 代码风格

- 先读现有模块再改动。
- 小步提交、测试优先覆盖高风险路径。
- 避免无关重构。
- 新增功能要带最小可运行测试。
- 报错信息要能帮助用户定位缺失依赖、配置路径或格式问题。
- At the end of each development session, summarize changed files, commands run, what works, known limitations, and recommended next steps.

## 常用命令

```bash
python -m pip install -e ".[dev]"
pokermda init
pokermda scan-raw --dry-run
pokermda ingest --new-only --limit-files 20
pokermda queue-review --top 50
pokermda export-gtowizard --limit 20
pokermda status imports
pytest
```
