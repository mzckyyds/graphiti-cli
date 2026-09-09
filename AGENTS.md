# AGENTS.md

## 项目概览

`graphiti-cli` — 一个面向 [Graphiti](https://github.com/getzep/graphiti)（时序知识图谱框架）的 CLI 工具，用户侧用法与命令示例见 `README.md`。

代码结构：src 布局（`src/graphiti_cli/`），入口为 `__main__.py`（`uv run python -m graphiti_cli`）与 `pyproject.toml` 中 `[project.scripts]` 注册的 `graphiti-cli` 命令（指向 `graphiti_cli.__main__:app`）；`cli.py`（根命令 `app`, 组装各子命令）、`commands/`（各类子命令函数统一存放, 每类一个模块, 如 `commands/config.py`, `commands/_base.py` 存放共用工具）、`client.py`（Graphiti 实例构建）、`settings.py`（配置读写, 含 `CLI_HOME` 等常量）。

配置统一存放在 `~/.graphiti-cli/settings.json`（目录 700, 文件 600），所有命令从这里读取，不使用环境变量。

包/依赖管理基于 uv，以 `pyproject.toml` 为准。

CI 暂未配置，随项目成长逐步补充。

## 常用命令

* **环境安装**：`uv sync`
* **运行**：`uv run graphiti-cli ...`（或 `uv run python -m graphiti_cli ...`）
* **添加依赖**：`uv add <package>`（切勿手动编辑 `uv.lock`）
* **添加开发依赖**：`uv add --dev <package>`（pytest, pytest-asyncio, ruff, pyright 已配置）
* **测试**：`uv run pytest`（异步测试由 pytest-asyncio 支持, `asyncio_mode = "auto"`）
* **质量检查/格式化**：`uv run ruff format src/ && uv run ruff check src/`
* **类型检查**：`uv run pyright`

## CLI 行为语义

### 图分区(group\_id)

`--group-id` 用于多租户/多场景隔离. **FalkorDB 下每个 group\_id 对应一张同名图**:

* `episode add` 是唯一会创建新分区的路径: 写入时指定 `--group-id X` 后,
  数据落在图 `X`;
* 其余所有命令的 `--group-id X` 要求图 `X` 已存在, 不存在会直接报错
  (避免拼错分区名时静默创建一张空图, 见 `_base.driver_for`);
* 不传 `--group-id` 时使用默认分区(group\_id 为 `_`, 即配置里的
  `database`); `episode/node/edge` 的按 UUID 直读与改删、以及
  `node/edge add`, 都需要 `--group-id` 与写入时一致, 否则会在默认
  分区里找不到数据.

### 属性保留键

`--attribute` 的 KEY 不能与节点/边的内建字段冲突(保存时属性会被展平进
记录属性, 冲突的 KEY 会被静默丢弃), 冲突时 `parse_attributes` 直接报错:

* 节点(`EntityNode`): `uuid`/`name`/`name_embedding`/`group_id`/`summary`/`created_at`/`labels`
* 边(`EntityEdge`): `uuid`/`name`/`group_id`/`fact`/`fact_embedding`/`episodes`/`created_at`/`expired_at`/`valid_at`/`invalid_at`/`reference_time`/`source_uuid`/`target_uuid`

### --extra-body 注入机制

CLI 会包装 OpenAI 客户端的 `chat.completions.create`, 将配置的 extra\_body
合并进每次 LLM/Reranker 请求的 extra\_body 参数(用户传入的同名字段优先).
因此 extra\_body 可以覆盖 graphiti-core 自身设置的请求字段(例如
response\_format 的 json\_schema 结构化输出), 用于兼容对结构化输出支持
不佳的 OpenAI 兼容端点; 若无此类兼容需求, 不建议设置该字段.

### 输出格式

所有结果以 JSON 输出, 便于管道处理(`jq` 等). `search` 的输出统一为
JSON 对象: 默认为 `{"nodes": [...], "edges": [...]}`, `--only-node` 为
`{"nodes": [...]}`, `--only-edge` 为 `{"edges": [...]}`.

## 代码规范

### 开发依赖

* **pytest** - 同步测试

* **pytest-asyncio** - 异步测试

* **ruff** - 质量检查/格式化

```toml
[tool.ruff]
line-length = 88 # 与 Black 默认值一致
target-version = {{与 pyproject.toml 中 `[project].requires-python` 的值相匹配}}

[tool.ruff.lint]
# 采用全选项+单项逐一排除的模式
select = ["ALL"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
skip-magic-trailing-comma = false
```

* **pyright** - 类型检查

```toml
[tool.pyright]
typeCheckingMode = "strict"
```

### 数据规范

* **外部数据入口** - 使用 `pydantic`，保障流入数据安全

* **内部数据流通** - 使用 `dataclass`，以提高性能和节省内存

* **规范字典结构** - 使用 `TypedDict`，方便静态类型检查

### 模块规范

* **类型导入** - 非运行时类型导入统一放在 `TYPE_CHECKING` 中

* **成员导出** - 使用 `__all__` 导出，即使只有一个导出项也要用尾逗号换行

* **私有成员** - 仅在模块内使用的成员以下划线开头命名，如 `def _convert_xxx_to_xxx()`

### 注释规范

* **Docstring** - 使用 **Google Style Docstring** 格式；公共 API 应提供完整文档字符串，私有成员根据复杂度和实际需要添加；语言精炼

* **普通注释** - 语言精炼，不要在代码末尾注释，必要时通过 `NOTE`、`BUG` 等注明类型

* **层次注释** - 使用三级层次注释区分代码结构，分隔符结束位置与 pyproject.toml 中 `[tool.ruff].line-length` 的值相匹配，标题首字母大写

```python
# =====================================
# 一级标题
# =====================================
class BaseXXX:
    pass

    # +++++++++++++++++++++++++++++++++++++
    # 二级标题
    # +++++++++++++++++++++++++++++++++++++
    def _base_convert(
        self,
    ) -> None:
        pass

    # -------------------------------------
    # 三级标题
    # -------------------------------------
    def convert_a(
        self,
    ) -> None:
        pass

    def convert_b(
        self,
    ) -> None:
        pass

    # +++++++++++++++++++++++++++++++++++++
    # 二级标题
    # +++++++++++++++++++++++++++++++++++++
    def _base_log(
        self,
    ) -> None:
        pass

    # -------------------------------------
    # 三级标题
    # -------------------------------------
    def log_a(
        self,
    ) -> None:
        pass

    def log_b(
        self,
    ) -> None:
        pass
```

### 异常规范

使用 **f-string** + **!r** 格式：

```python
raise ValueError(f"Invalid value: {value!r}")
```

### 日志规范

使用 **module logger** + **lazy formatting** + **%r** + **key=value** 格式：

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Received no message: node=%r, turn=%r", name, turn)
```

### 函数和方法定义规范

除 `self`、`cls` 外参数默认必须定义为 **keyword-only**，且只要存在参数则必须使用多行参数列表并保留尾逗号：

```python
# 函数定义
def handle_1() -> int: ...


def handle_2(
    *,
    a: int,
) -> int: ...


def handle_3(
    *,
    a: int,
    b: int,
) -> int: ...


# 方法定义
class H1:
    def handle(
        self,
    ) -> int: ...


class H2:
    def handle(
        self,
        *,
        a: int,
    ) -> int: ...


class H6:
    def handle(
        self,
        *,
        a: int,
        b: int,
    ) -> int: ...
```

### 函数和方法调用规范

优先使用关键字参数。项目内部原则上不使用 **positional-only** 参数，但三方模块可能强制使用位置参数，此时遵循其 API 要求：

```python
# 函数调用
convert(value="1", encoding="utf-8")

# 方法调用
obj.convert(value="1", encoding="utf-8")
```

### 符号规范

注释、文档字符串与用户可见字符串中统一使用**半角符号**，分隔符后跟**一个空格**；行尾与字符串收尾不留尾随空格：

```python
# Bad
logger.info("登录成功！登录态已保存到 %r，下次可直接使用。")

# Good
logger.info("登录成功! 登录态已保存到 %r, 下次可直接使用.")
```

> NOTE: 运行时逻辑中需要匹配全角字符的正则（如页面文本 `IP属地：上海`）不受此规则约束，需保留全角字符并加 `NOTE` 注明。
