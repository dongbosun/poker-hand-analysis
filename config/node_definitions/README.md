# Node Definitions

Node definition YAML files describe repeatable poker situations for MDA and frequency aggregation.

第一版只提供示例格式。后续 `pokermda nodes build/query/aggregate` 会读取这些 spec，把 normalized hand/action 数据转换成 node instances 和 stat aggregates。

建议字段：

- `id`：稳定唯一 id。
- `description`：人类可读说明。
- `street`：preflop/flop/turn/river。
- `filters`：pot type、position、action sequence、board texture、sizing 等条件。
- `metrics`：需要聚合的频率或 sizing。

