# graphiti-cli

[Graphiti](https://github.com/getzep/graphiti) 时序知识图谱的命令行工具: 配置 OpenAI 兼容模型服务与 FalkorDB, 通过命令管理 episodes / 实体节点 / 关系边 / 事实三元组.

命令分组与 [graphiti MCP Server](https://github.com/getzep/graphiti/blob/main/mcp_server/src/graphiti_mcp_server.py) 工具的对应关系:

| MCP 工具 | CLI 命令 |
| --- | --- |
| `add_memory` | `graphiti-cli episode add` |
| `get_episodes` | `graphiti-cli episode show` |
| `delete_episode` | `graphiti-cli episode delete` |
| `get_episode_entities` | `graphiti-cli episode nodes` / `episode edges` |
| `search_nodes` | `graphiti-cli node search` |
| `search_memory_facts` | `graphiti-cli edge search` |
| `get_entity_edge` | `graphiti-cli edge show` |
| `delete_entity_edge` | `graphiti-cli edge delete` |
| `add_triplet` | `graphiti-cli triplet add` |
| `<未提供>` | `episode patch` / `node add` / `node show` / `node patch` / `node delete` / `edge add` / `edge patch` |

`patch` 系列与 `node`/`edge` 的直写增删改是 CLI 扩展, 基于 graphiti-core 的模型
`save()`/`delete()` 实现, 不经过 LLM 抽取.

## 安装

```bash
uv sync
uv run graphiti-cli --help
```

## 配置

```bash
# 模型服务(OpenAI 兼容端点)
uv run graphiti-cli config set llm --base-url <URL> --model <NAME> --api-key <KEY>
uv run graphiti-cli config set embedder --base-url <URL> --model <NAME> --api-key <KEY> --dim 1024
uv run graphiti-cli config set reranker --base-url <URL> --model <NAME> --api-key <KEY>

# LLM/Reranker 可注入额外请求体字段(如 qwen3 关闭深度思考)
uv run graphiti-cli config set llm --extra-body '{"enable_thinking": false}'

# FalkorDB(Redis 协议)
uv run graphiti-cli config set falkordb --host localhost --port 6379 --database _

# 查看当前配置(api_key/password 默认掩码)
uv run graphiti-cli config show
```

配置持久化在 `~/.graphiti-cli/settings.json`.

## 常用命令

### Episodes(写入信息与溯源查询)

```bash
# 添加 episode 并触发实体/关系抽取(主要写入入口)
uv run graphiti-cli episode add "会议纪要" --content "正文..." --source text
echo "长正文..." | uv run graphiti-cli episode add "会议纪要" --content -

# 列出 / 查看单个
uv run graphiti-cli episode show
uv run graphiti-cli episode show <EPISODE_UUID>

# 修改描述字段(不会触发重新抽取; 需重建图谱请删除后重新添加)
uv run graphiti-cli episode patch <EPISODE_UUID> --name "新名称"

# 删除(仅该 episode 独有的实体与关系会被级联删除)
uv run graphiti-cli episode delete <EPISODE_UUID>

# 溯源: 查看 episode 产出的实体节点 / 关系边
uv run graphiti-cli episode nodes <EPISODE_UUID>...
uv run graphiti-cli episode edges <EPISODE_UUID>...
```

### 实体节点

```bash
# 混合检索(语义 + 关键词), 可按 label 过滤、围绕中心节点重排序
uv run graphiti-cli node search "查询文本" --limit 10 --entity-type Organization

# 直写增删改(不经过 LLM 抽取)
uv run graphiti-cli node add "节点名" --summary "摘要" --attribute KEY=VALUE
uv run graphiti-cli node show <NODE_UUID>
uv run graphiti-cli node patch <NODE_UUID> --summary "新摘要"   # 改名会自动重建名称向量
uv run graphiti-cli node delete <NODE_UUID>
```

### 关系边(事实)

```bash
# 事实检索, 支持关系类型与生效/失效时间区间过滤
uv run graphiti-cli edge search "查询文本" --valid-at-after 2026-01-01

# 在两个已有节点间直写一条边(自动生成事实向量)
uv run graphiti-cli edge add <SOURCE_UUID> <TARGET_UUID> --name "关系名" --fact "事实描述"

uv run graphiti-cli edge show <EDGE_UUID>
uv run graphiti-cli edge patch <EDGE_UUID> --fact "新事实"      # 改 fact 会自动重建事实向量
uv run graphiti-cli edge delete <EDGE_UUID>
```

### 事实三元组(绕过抽取流程)

```bash
# 直写 source -> 关系 -> target, 节点不存在时经 LLM 解析合并
uv run graphiti-cli triplet add "源实体" "关系" "事实描述" "目标实体"
```

## 图分区(group\_id)

`--group-id` 用于多租户/多场景隔离. **FalkorDB 下每个 group\_id 对应一张同名图**:

* `episode add` 写入时指定 `--group-id X` 后, 数据落在图 `X`;
* `episode/node/edge` 的按 UUID 直读与改删、以及 `node/edge add`, 都需要
  `--group-id` 与写入时一致, 否则会在默认图里找不到数据;
* 不传 `--group-id` 时操作默认图(即配置里的 `database`, 通常为 `_`);
* 新分区首次使用前建议先建索引(可在 Python 中对克隆 driver 后调用
  `graphiti.build_indices_and_constraints()`).

所有结果以 JSON 输出, 便于管道处理(`jq` 等).

## 开发

```bash
uv run ruff format src/ && uv run ruff check src/   # lint
uv run pyright src/                                 # 类型检查(strict)
uv run pytest                                       # 测试
```
