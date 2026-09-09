---
name: graphiti-cli
description: A CLI tool for [Graphiti](https://github.com/getzep/graphiti) (a temporal knowledge graph framework).
---

# graphiti-cli

A CLI tool for [Graphiti](https://github.com/getzep/graphiti) (a temporal knowledge graph framework). The entry command is `graphiti-cli` (use `uv run graphiti-cli` in the source tree).

## Core rule: check --help before using any command

**Never guess flags from memory.** Before using any command, run its `--help` first to see the exact usage:

```bash
graphiti-cli --help                   # list top-level commands
graphiti-cli <command> --help         # inspect a command group (e.g. episode, search)
graphiti-cli <command> <sub> --help   # inspect a concrete command's flags (e.g. episode add)
```

## Command map

| Command | Purpose |
|---------|---------|
| `config` | Read/write the config file (`~/.graphiti-cli/settings.json`): `show` to view, `set` to write items one by one (llm/embedder/reranker/falkordb) |
| `episode` | Manage `EpisodeNode`: add/get/list/delete |
| `node` | Manage `EntityNode`: add/get/list/patch/delete |
| `edge` | Manage `EntityEdge`: add/get/list/patch/delete |
| `triplet` | Write a triplet (source node, edge, target node) in one shot, bypassing entity/relationship extraction; note that it still makes LLM calls for edge dedup/validation, and if a `--source-uuid`/`--target-uuid` does not exist in the graph, the node is resolved by name via the LLM and the uuid may be replaced |
| `search` | Hybrid search with attribute and time-range filters |

## Typical workflow

1. **First use**: configure services via `config set llm/embedder/reranker/database` (OpenAI-compatible endpoints + FalkorDB), then verify with `config show`.
2. **Ingest raw text**: `episode add` (supports `--content -` to read from stdin); entities and relations are extracted by the LLM automatically.
3. **Write structured knowledge precisely**: `triplet` writes a triplet directly, bypassing entity/relationship extraction (note: it still makes LLM calls for edge dedup/validation; see the command map above).
4. **Query**: `search` for hybrid retrieval; or `node get`/`edge get` to read by UUID directly, `node list`/`edge list` to list per partition.

## Behavior semantics not visible in --help

- **All output is JSON**, ready for `jq` and other pipelines. `search` outputs `{"nodes": [...], "edges": [...]}` by default; with `--only-node`/`--only-edge` only the corresponding key is present.
- **Graph partitions (`--group-id`)**: on FalkorDB each group_id maps to a graph of the same name.
  - `episode add` is the only path that creates a new partition; every other command's `--group-id` requires the partition to already exist, otherwise it errors out.
  - Omitting `--group-id` uses the default partition (the configured `database`). UUID-based reads/writes/patches/deletes must use the same `--group-id` as the write, otherwise the data is not found in the default partition.
- **Reserved `--attribute` keys**: builtin field names such as `uuid`/`name`/`group_id`/`summary`/`created_at` cannot be used as attribute keys (the reserved lists for nodes and edges differ slightly; see the command's error message); conflicts raise an error.
- **`config set` only overwrites explicitly passed items**; unspecified settings remain unchanged.
