# wastedRAM

用 Mac 闲置内存跑本地推理，把云端 token 留给真正难的部分。

本仓库是一个标准 AI coding agent skill，同时附带可安装的 Python 包。任何能执行 shell 或 Python 的宿主都能用：Claude Code、Codex CLI、Cursor、Aider、Windsurf、Cline，或你自己的 agent 框架。

## 仓库结构

```
wastedram/                 # skill 本体
├── SKILL.md               # 入口，宿主读这个
├── scripts/run_task.py    # 免安装脚本入口
└── references/            # 模型档位与排障
src/wastedram/             # pip 包（Router / workflow / codecheck）
scripts/start_local.sh     # 启动本地 MLX server
pyproject.toml
```

## 安装

```bash
pip install 'wastedram[mlx] @ git+https://github.com/igpig1226/wastedRAM.git'
```

需要 Apple Silicon Mac 与 Python 3.10+。没有 PyPI 发布前用上面的 Git 地址。

## 启动本地模型

```bash
mlx_lm.server --model "$(wastedram model)" --port 8080 --host 127.0.0.1
```

`wastedram model` 按物理统一内存选一个保守的量化模型。首次启动会下载权重。

## 配置

```bash
export WASTEDRAM_CLOUD_URL=https://api.deepseek.com/v1
export WASTEDRAM_CLOUD_API_KEY=sk-...
export WASTEDRAM_LOCAL_URL=http://127.0.0.1:8080
```

`PIGMODEL_*` 仍作为兼容别名。纯本地命中（`is_simple` / `is_medium`）不需要云密钥。

## 三种调用方式

```bash
# 1. CLI：任何能跑 shell 的 agent
wastedram run "实现一个 parse_port 函数并写测试"
```

```python
# 2. Python：任何能执行 Python 的 agent
from wastedram.skill_entry import run

result = run(
    task="Implement a Python parse_port(value) function with tests",
    cloud_url="https://api.deepseek.com/v1",
    cloud_model="deepseek-chat",
    cloud_key="sk-...",
    local_model="mlx-community/Qwen2.5-Coder-7B-Instruct-8bit",
)
print(result["content"], result["source"], result["cloud_tokens"])
```

```bash
# 3. 免安装脚本：只有仓库 checkout
python wastedram/scripts/run_task.py "your task" --cloud-url https://api.deepseek.com/v1
```

## 宿主如何自动触发

把 `wastedram/SKILL.md` 放进宿主的 skill 目录（或让宿主扫描本仓库），宿主会根据 frontmatter 的 `description` / 触发词在遇到「省 token、本地跑、大型任务分解」时自动加载。

- Claude Code：`~/.claude/skills/wastedram/SKILL.md`
- Codex CLI：项目 `.codex/skills/` 或全局 skills 目录
- Cursor / Windsurf / Cline：各自的 rules / skills 入口，指向本文件即可
- 通用：把 `wastedram/SKILL.md` 内容并入你的 system prompt

## 它怎样省 token

短事实题和概念题走本地 MLX；复杂编码走云端 PLAN → 本地并发叶子 → 云端 synthesis。云端 prompt 压缩、预算自适应、精确匹配缓存、失败回退。实际节省取决于任务组合与缓存命中率。

## 模型档位

| 统一内存 | 模型 |
| --- | --- |
| ≤16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` |
| ≥128GB | `mlx-community/Qwen2.5-72B-Instruct-8bit` |

权重文件大小不是运行时内存；上下文和系统也要空间。变慢或 swap 就降档。

## 限制

- 需要 Apple Silicon 与本地 OpenAI 兼容服务
- 代码验收是 AST + 执行沙箱的有界检查，不等于证明正确
- 缓存键包含端点、模型和任务，任一变化都会 miss
- 云端 token 数字以结果里的 `cloud_tokens` 为准，不要凭感觉宣称节省

详细模型与排障见 [wastedram/references/](wastedram/references/)。
