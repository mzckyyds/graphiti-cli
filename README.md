# Graphiti CLI

**CLI** for [Graphiti](https://github.com/getzep/graphiti) with **FalkorDB** persistence and **OpenAI-compatible** LLM, embedding, and reranking endpoints.

## 🚀 Quick Start

### Installation

```bash
uv sync
uv run graphiti-cli --help
```

### Usage Examples

```bash
# Set LLM
$ uv run graphiti-cli config set llm \
--base-url <URL> \
--model-name <NAME> \
--api-key <KEY> \
--extra-body '{"enable_thinking": false}'

# Set Reranker
$ uv run graphiti-cli config set reranker \
--base-url <URL> \
--model-name <NAME> \
--api-key <KEY>

# Set Embedder
$ uv run graphiti-cli config set embedder \
--base-url <URL> \
--model-name <NAME> \
--api-key <KEY>

# Set FalkorDB
$ uv run graphiti-cli config set falkordb \
--host localhost \
--port 6379 \
--database default_db

# Show current configuration
$ uv run graphiti-cli config show

# Add an episode
$ uv run graphiti-cli episode add \
--name "story" \
--content "Zhang san is Li si's husband ..." \
--source text

# Add a node
$ uv run graphiti-cli node add \
--name "Zhang san" \
--summary "A man ..." \
--attribute org=example
$ uv run graphiti-cli node add \
--name "Li si" \
--summary "A woman ..." \
--attribute org=example

# Add an edge
$ uv run graphiti-cli edge add \
--name "husband" \
--fact "Zhang san is Li si's husband ..." \
--source-uuid <UUID> \
--target-uuid <UUID>

# Append a triplet
$ uv run graphiti-cli triplet \
--source-name "Zhang san" \
--target-name "Li si" \
--edge-name "husband" \
--edge-fact "Zhang san is Li si's husband ..."

# Hybrid search
$ uv run graphiti-cli search --content "Who is Zhang san"
```

> Use `uv run graphiti-cli --help` to see more.

## 📄 License

Apache-2.0. See [LICENSE](LICENSE) for details.
