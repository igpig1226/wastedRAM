<p align="center">
  <img src="assets/wastedram-hero.svg" alt="wastedRAM：别让内存闲着" width="100%">
</p>

<h1 align="center">wastedRAM</h1>
<p align="center">用 Mac 闲置内存处理小任务，把云端 token 留给真正复杂的问题。</p>
<p align="center">
  <img alt="Apple Silicon" src="https://img.shields.io/badge/Mac-Apple%20Silicon-18242a?style=flat-square">
  <img alt="MLX" src="https://img.shields.io/badge/local-MLX-a9f374?style=flat-square">
  <img alt="Cloud API" src="https://img.shields.io/badge/cloud-OpenAI%20compatible-837bed?style=flat-square">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-5c8f78?style=flat-square">
</p>

> 本仓库是**独立分发版 skill**。路由引擎在 [pigmodel 开发仓库](https://github.com/igpig1226/pigmodel) 继续开发；使用 wastedRAM 不需要了解该仓库。

wastedRAM 是一个通用 AI coding agent skill：把任务拆成「本地 MLX 推理」和「云端 API」两层，短题本地跑，复杂编码才走云端。Claude Code、Codex CLI、Cursor、Aider、Windsurf、Cline，或你自己的 agent 都能用。

## 为什么

- 短问答、概念题完全不出本机，云端 token 归零
- 大任务交给云端规划，子任务本地并行执行
- 云端 prompt 压缩 + 预算自适应 + 精确匹配缓存
- 本地失败自动回退云端，不把任务跑挂

## 结构

```
SKILL.md              技能入口，宿主读这个
scripts/run_task.py   免安装入口（CLI + Python）
scripts/engine/       内置路由引擎，checkout 即可运行
references/           模型档位与排障
assets/               头图
```

## 使用

不需要 pip install，clone 之后直接跑。

先启动本地模型（按物理内存选档位，见下）：

```bash
mlx_lm.server --model mlx-community/Qwen2.5-Coder-7B-Instruct-8bit --port 8080 --host 127.0.0.1
```

然后：

```bash
python scripts/run_task.py "实现一个 parse_port 函数并写测试" \
  --cloud-url https://api.deepseek.com/v1 \
  --cloud-model deepseek-chat \
  --local-model mlx-community/Qwen2.5-Coder-7B-Instruct-8bit
```

或者在 Python 里：

```python
import sys
sys.path.insert(0, "scripts")
from run_task import run

result = run(
    task="Implement a Python parse_port(value) function with tests",
    cloud_url="https://api.deepseek.com/v1",
    cloud_model="deepseek-chat",
    cloud_key="sk-...",          # 纯本地命中时不需要
    local_model="mlx-community/Qwen2.5-Coder-7B-Instruct-8bit",
)
print(result["content"], result["source"], result["cloud_tokens"])
```

## 配置

| 变量 | 用途 |
| --- | --- |
| `WASTEDRAM_CLOUD_URL` | OpenAI 兼容 `/v1` 地址，云端路径必填 |
| `WASTEDRAM_CLOUD_API_KEY` | 云端密钥 |
| `WASTEDRAM_LOCAL_URL` | 本地地址，默认 `http://127.0.0.1:8080` |

纯本地命中（`is_simple` / `is_medium`）不需要任何云端密钥。

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

## 接到宿主

把 `SKILL.md` 放进宿主的 skills 目录，或让宿主扫描本仓库：

- Claude Code：`~/.claude/skills/wastedram/SKILL.md`
- Codex CLI：项目 `.codex/skills/` 或全局 skills 目录
- Cursor / Windsurf / Cline：指向本仓库 `SKILL.md`
- 通用：把 `SKILL.md` 并进 system prompt

详细内容见 [SKILL.md](SKILL.md)、[references/models.md](references/models.md)、[references/troubleshooting.md](references/troubleshooting.md)。
