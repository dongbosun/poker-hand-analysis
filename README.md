# Poker Hands Analyzer

一个面向 Bovada hand history 的本地扑克复盘与玩家池分析项目。第一版目标是把原始手牌安全地导入本地 DuckDB，建立可追踪的复盘队列，导出经过脱敏的 GTOWizard 手牌，并为后续 MDA、node 统计、range 聚合留下清晰扩展点。

当前阶段优先级：NL10 阶段先服务自己的手牌复盘，然后是自己的 stats，再到玩家池 stats，最后才是 node-lock 剥削和自动挖掘。DuckDB 本地数据库是 source of truth；GTOWizard 是外部分析器，不是本项目的数据主库。

## 核心原则

- **不修改 Bovada 原始目录**：不会移动、重命名、删除，也不会在原始目录旁边写 sidecar 文件。
- **所有真实数据只进 `dataset/`**：DuckDB、Parquet、JSONL、导出文件、日志、临时文件都放在项目根目录的 `dataset/` 下。
- **`dataset/` 不进 git**：仓库只保存代码、配置模板、测试 fixture 和文档。
- **增量导入**：通过本项目自己的 DuckDB import ledger 记录文件 hash、路径、状态和导入时间。
- **手牌去重**：同一文件不会重复导入；同一手牌重复出现在不同文件里时，主表按 hand id/hash 去重。
- **GTOWizard 本地导出**：第一版不假设 GTOWizard API 存在，只生成本地脱敏 hand history 和 manifest，供手动上传和手动标记结果。
- **分析单位分层**：hand 不是唯一分析单位；`participants`、`actions`、`decision_instances` 才是 MDA 和 node 统计的核心。
- **fully-revealed 数据只留本地**：Bovada 的对手 hole cards 可以用于本地玩家池 MDA，但导出 GTOWizard 时必须 sanitize。

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
pokermda scan-raw
pokermda ingest --new-only
```

导入行为：

1. 递归扫描 `bovada_raw_hand_history_dir` 下所有 `.txt` 文件。
2. 对每个文件计算 SHA-256。
3. 查询 DuckDB import ledger。
4. 已成功导入过的文件 hash 会跳过，同时记录当前路径为 duplicate/skipped。
5. 新文件会拆分成 hand block，写入 `raw_hand_blocks`。
6. parser 尝试生成 `hands`、`participants`、`actions`。
7. 解析失败不会终止导入，会写入 `parse_errors` 并继续处理后续手牌。

常用参数：

```bash
pokermda ingest --limit-files 20
pokermda ingest --source-dir "/Users/dongbosun/Bovada.lv Poker/Hand History"
```

`pokermda scan-raw --dry-run` 只扫描和计算 hash，不写 ledger，也不修改 Bovada 原始目录。

## 数据库基本信息

以后需要快速确认数据库状态时运行：

```bash
pokermda profile
```

它会输出：

- DuckDB 里有多少手牌。
- DuckDB 里按 stake level 拆分的手牌数、participants、actions、raw blocks、import files。
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

Stake level 由每手牌 posted big blind 派生：

- BB `$0.05` -> `NL5`
- BB `$0.10` -> `NL10`

旧数据库会在启动命令时自动 backfill `hands.bb_amount` / `hands.sb_amount` / `hands.stake_level`。

## 当前可运行 Stats

```bash
pokermda stats summary
pokermda stats summary --json
pokermda stats summary --level NL5
pokermda stats summary --level NL10
pokermda stats edge
pokermda stats edge --json
pokermda stats edge --level NL5
pokermda stats edge --level NL10
```

当前 stats 定义：

- VPIP：发到牌的 seat 为分母；preflop call / raise / bet / all-in 计入；blind、posts chip、ante、straddle 不计入。
- PFR：发到牌的 seat 为分母；preflop raise 或 all-in(raise) 计入。
- pool：Bovada 匿名数据中的所有非 hero seat 聚合样本，不代表可追踪的单个玩家。
- collected：有 `Hand result` / collected action，不等于净盈利或 bb/100。

`pokermda stats edge` 是用于判断 edge 的正式 pipeline，当前输出：

- Overall winrate / redline / blueline / pot type EV / biggest hands。
- Winrate by position：每个位置的 hands、VPIP、PFR、3bet、net bb、bb/100。
- RFI by position：UTG / MP / CO / BTN / SB open 频率。
- RFI hand class breakdown：按位置和手牌类别看 RFI 后 EV。
- Cold call by position：面对前面 raise 时第一 voluntary action 为 call 的频率。
- BTN cold call deep report：按 opener position 和 hand class 拆 net bb / hand_ids。
- SB first action vs opener：SB complete / call vs raise / raise 按 opener position 拆 EV。
- BB defense vs steal：BB 面对 CO / BTN / SB steal 的 fold / call / 3bet 分布和 EV。
- 3bet by position：面对 open raise 时第一 voluntary action 为 raise/all-in(raise) 的频率。
- 3bet by position vs open position：按 3bettor 位置和 opener 位置交叉。
- 3bet hand class / 3bet pot result / 4bet / squeeze / steal / fold-to-steal。
- Fold to 3bet：open raiser 面对第一手 3bet 后第一反应为 fold 的频率。
- C-bet flop / turn barrel / river barrel：last preflop raiser 在无人 donk 领先下注前的主动下注频率和 EV。
- C-bet deep report：SRP/3BP、IP/OOP、heads-up/multiway、c-bet result tree、facing c-bet response、turn after c-bet。
- Donk / stab vs missed c-bet / check-raise / postflop sizing / facing bet-size defense proxy。
- WTSD / W$SD / WWSF：saw flop 后的摊牌、摊牌赢钱、看 flop 后赢钱质量。
- River call efficiency：river call 手牌的总净 bb / river call 投入 bb。
- River call by size / line：按下注尺度和 villain line 拆 RCE。
- Bluff catch result：river call 且进入 showdown 的子集胜率、净结果和 hand_ids。
- SB limp/complete/call EV：Small Blind 第一 voluntary action bucket 的近似净 bb。
- Starting hand matrix / hand class EV by position / dominated hand leak / pocket pair / suited connector reports。
- Limped pot / isolation raise / multiway / stack depth / session / table-size reports。
- Leak flags：按当前样本自动输出 Top suspected leaks。

每个 rate / EV spot 尽量输出统一字段：

- `opportunities`：机会数，分母。
- `count`：实际发生次数，分子。
- `frequency`：发生频率。
- `net_bb`：该 spot 实际发生时的总输赢。
- `opportunity_net_bb`：该 spot 所有机会的总输赢。
- `bb_per_opportunity`：按机会数标准化的 EV。
- `bb_per_count` / `bb_per_hand`：按实际发生次数或手数标准化的 EV。
- `bb_per_100`：按机会/手数标准化到 100 的赢率。
- `hand_ids`：实际发生该 spot 的手牌 ID，方便复盘。
- `opportunity_hand_ids`：该 spot 机会手牌 ID，主要用于 fold/call/raise 分布排查。
- `sample_warning`：`low_sample` 或 `no_sample`。

位置标准化：

- `Dealer` -> `BTN`
- `Small Blind` -> `SB`
- `Big Blind` -> `BB`
- `UTG+1` -> `MP`
- `UTG+2` -> `CO`

金额口径：

- 每手牌用该手 `post_big_blind` 的金额换算 bb。
- 当前 `net_bb` 为近似值：`collect + returned uncalled - committed chips` 后除以该手 BB。
- postflop sizing 使用动作序列重建的 `pot_before_bb` 近似值，足够做 leak 定位，但不是 solver 级 pot model。
- 暂不支持 all-in adjusted bb/100、精确 rake、value/bluff 自动分类、missed river value 自动判断、fish-in-blinds 标签；这些会在 `unsupported_or_approximate` 中明确标出。
- 这个口径已经足够发现 river call、SB complete/call、BTN cold call、BB resteal、one-and-done c-bet 等大方向 leak；后续如果要做 solver 级 EV，需要继续补完整 pot/stack/facing-bet reconstruction 和 hand-strength classifier。

刷新当前数据库 deep stats：

```bash
pokermda scan-raw
pokermda ingest --new-only
pokermda stats edge
pokermda stats edge --json
```

## 每天复盘流程

推荐日常流程：

Step 0：在 Bovada 客户端/网页导出 hand history，确认文件出现在：

```text
/Users/dongbosun/Bovada.lv Poker/Hand History
```

Step 1：扫描原始目录。

```bash
make scan
```

Step 2：增量入库。

```bash
make ingest
```

Step 3：生成当天复盘队列。

```bash
make queue-review
```

Step 4：导出 GTOWizard 文件。

```bash
make export-gtowizard
```

Step 5：手动打开 GTOWizard，上传命令输出中的：

```text
dataset/exports/gtowizard/<batch>/hands_gtowizard.txt
```

Step 6：上传后本地标记：

```bash
pokermda gtow mark-uploaded --batch <batch_id>
```

Step 7：GTOWizard 分析完成后本地标记：

```bash
pokermda gtow mark-analyzed --batch <batch_id> --status analyzed
```

Step 8：在 GTOWizard 里按 EV loss 排序复盘。

Step 9：复盘完每手牌后本地记录：

```bash
pokermda review mark-done --hand-id <hand_id> --tag river_bluffcatch --note "..."
```

截图、笔记和手动结果可以放在：

```text
dataset/review/gtowizard_manual_results/
dataset/review/screenshots/
dataset/review/notes/
```

也可以跑一键本地流程：

```bash
pokermda daily
```

`daily` 不会上传任何外部服务，也不会跑耗时的全库 node mining。

## GTOWizard 脱敏导出

本项目不会把 Bovada fully revealed 原文直接作为 GTOWizard 导出物。导出器会：

- 保留 hero 手牌、公共牌和行动线。
- 对玩家名做稳定匿名化：`Hero`、`Villain1`、`Villain2` 等。
- 去掉或隐藏非 hero 的 hole cards。
- 去掉 summary 中可能泄露完整摊牌信息的行。
- 生成 `hands_gtowizard.txt`、`manifest.csv` 和 `manifest.json`。
- `manifest.csv` 包含 `hand_id`、`original_site_hand_no`、`exported_hand_no`、offset、hash 等字段，便于手动上传后回填结果。
- 如果某手后续无法被 GTOWizard 识别，应在本地用 `gtow add-result` 或 batch mark 命令记录 unsupported / duplicate / error。

第一版不调用 GTOWizard API。建议先用 20-50 手牌测试 GTOWizard 解析效果，人工检查格式，再扩大导出规模。

## 数据库设计

- `import_files`：文件级 import ledger。按 sha256 和路径记录 discovered/importing/imported/partial/error/skipped_duplicate。
- `raw_hand_blocks`：bronze 层。保存 txt 中切出的原始 hand block，解析失败也保留。
- `hands`：每手牌公共信息，一手一行。
- `participants`：每手牌每个座位一行。6-max 一手通常有 6 行 participants；Bovada fully-revealed 的本地 MDA 价值主要在这里。
- `actions`：每个真实动作一行，带 participant_id、street、全局动作序号和 street 内序号。
- `player_hand_facts`：玩家视角 summary 和 line key，后续用于 stats 和 review scorer。
- `decision_instances`：gold 层核心事实表，每个玩家每次面临决策机会一行。
- `review_candidates` / `study_queue`：本地评分候选和每天复盘入口。
- `gtowizard_export_batches` / `gtowizard_export_hands` / `gtowizard_review_results`：GTOWizard 手动上传和结果追踪。
- `node_definitions` / `node_instances` / `node_aggregates` / `range_aggregates`：后续 MDA、node 和 range heatmap 基础。

公共牌面、桌名、按钮位等公共事实只存在 `hands`；玩家私有信息存在 `participants`；动作序列存在 `actions`；决策机会和 node 归属再进入 gold 表。这样不会把同一手公共信息复制 6 份。

## Node 与 MDA 扩展

`config/node_definitions/` 里有三个示例：

- river overbet
- flop cbet response
- turn barrel response

未来可以通过 YAML 定义 node 条件，再由 `pokermda nodes` 子命令加载、查询、聚合和导出。第一版保留 schema、模块和 CLI 占位，不强行实现复杂 poker edge cases。

node 是一个可重复统计的局面定义，例如“flop c-bet 后防守方响应”或“river 面对 125% pot overbet”。`node_definitions/*.yaml` 描述过滤条件；`node_instances` 记录哪些 decision 命中了 node；`node_aggregates` 聚合 fold/call/raise/bet 频率；`range_aggregates` 以后用于 13x13 hand class heatmap。第一阶段不做复杂 node lock，先积累可靠数据。

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

## 常用命令

```bash
make setup
make test
make init
make scan
make ingest
make status
make queue-review
make export-gtowizard
make daily

pokermda scan-raw --dry-run
pokermda status imports
pokermda stats summary
pokermda profile --json
pokermda gtow batches
pokermda gtow mark-uploaded --batch <batch_id>
pokermda gtow mark-analyzed --batch <batch_id>
pokermda gtow add-result --hand-id <hand_id> --ev-loss-bb 0.42 --label mistake
pokermda review todo
pokermda review mark-done --hand-id <hand_id> --tag cbet --note "..."
```

## Troubleshooting

- DuckDB 初始化失败：确认 `dataset/db/` 可写，或删除/备份损坏的 `dataset/db/poker.duckdb` 后重新 `pokermda init`。
- symlink 失败：不影响导入，配置里的 `bovada_raw_hand_history_dir` 会直接指向原始目录。
- 路径有中文、空格或 `$`：YAML 里用引号；代码内部统一用 `pathlib.Path`。
- 解析失败：原始 block 仍在 `raw_hand_blocks`，错误在 `parse_errors`；不会丢手牌。
- 重复导入：按 sha256 和 raw hand hash 去重；重复文件会被 skipped_duplicate 或 imported hash 跳过。
- 重复导出：`gtowizard_export_hands` 会记录已经导出的 hand；需要重导时可指定单手或清理本地 ignored 数据库。
- GTOWizard 不识别某些手牌：先在 `manifest.csv` 中定位 hand，再用 `gtow add-result` 标记 unsupported / format_error，并保留样本用于 exporter 测试。

## Roadmap

- Phase 1：文件扫描、ledger、hand block split、基础 parser、GTOW export tracking。
- Phase 2：更完整 Bovada parser、participants/actions/line_builder、review scorer。
- Phase 3：hero stats、daily/weekly report。
- Phase 4：pool MDA、decision_instances、range heatmap。
- Phase 5：node mining、strategy exploit candidate。
