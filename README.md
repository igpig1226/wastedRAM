<p align="center">
  <img src="assets/wastedram-hero.svg" alt="wastedRAM：别让内存闲着" width="100%">
</p>

<h1 align="center">wastedRAM</h1>
<p align="center">把机械性的小任务丢给 Mac 本地模型，省下主模型的 token 和上下文。</p>
<p align="center">
  <img alt="Apple Silicon" src="https://img.shields.io/badge/Mac-Apple%20Silicon-18242a?style=flat-square">
  <img alt="MLX" src="https://img.shields.io/badge/local-MLX-a9f374?style=flat-square">
  <img alt="No API key" src="https://img.shields.io/badge/API%20key-none-837bed?style=flat-square">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-5c8f78?style=flat-square">
</p>

> 本仓库是**独立分发版 skill**。开发在 [pigmodel 仓库](https://github.com/igpig1226/pigmodel) 进行；使用 wastedRAM 不需要了解那个仓库。

wastedRAM 是一个放进 IDE / AI 编码助手的 skill：教宿主模型把翻译、摘要、解释、小函数、测试样板这类**机械且可验证**的子任务交给本地 MLX 模型，自己只保留判断和最终验收。

**不需要 API key，不联网，不接云端。** 所有推理都在本机。

## 为什么

- 主模型的 token 和上下文只花在真正需要判断的地方
- 本地模型跑在 Apple Silicon 上，延迟低，离线可用
- 任务粒度由宿主控制，失败就自己做，不会把流程跑挂

## 结构

```
SKILL.md                   技能入口，宿主读这个
scripts/local_chat.py      调用本地模型（无 key）
scripts/start_server.sh    启动本地 MLX server
references/                模型档位与排障
assets/                    头图
```

## 快速开始

```bash
pip install mlx-lm
./scripts/start_server.sh
```

另开终端验证：

```bash
curl -s http://127.0.0.1:8080/v1/models
```

然后直接问本地模型：

```bash
python scripts/local_chat.py "Explain what a Python context manager is in 3 sentences"
```

写代码时给足契约：

```bash
python scripts/local_chat.py \
  "Write a Python parse_port(value) accepting int or base-10 string, 1..65535, \
ValueError for float/bool/None/'443.0'/0/65536. Include tests." \
  --max-tokens 1024
```

## 放进你的 IDE

把 `SKILL.md` 放到宿主的 skills 目录，或让宿主扫描本仓库：

| 宿主 | 放置方式 |
| --- | --- |
| Codex CLI | 项目 `.codex/skills/wastedram/SKILL.md`，或全局 skills 目录 |
| Claude Code | `~/.claude/skills/wastedram/SKILL.md` |
| Cursor | 指向本仓库 `SKILL.md` 作为 rule / skill |
| Windsurf / Cline | 同上，导入 `SKILL.md` |
| 其它 agent | 把 `SKILL.md` 内容并入 system prompt |

宿主会根据 frontmatter 的 `description` 在遇到机械子任务时自动加载。

## 模型档位

| 统一内存 | 模型 |
| --- | --- |
| ≤16GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` |
| 17–32GB | `mlx-community/Qwen2.5-Coder-7B-Instruct-8bit` |
| 33–48GB | `mlx-community/Qwen2.5-Coder-14B-Instruct-8bit` |
| 49–64GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` |
| 65–127GB | `mlx-community/Qwen2.5-72B-Instruct-4bit` |
| ≥128GB | `mlx-community/Qwen2.5-72B-Instruct-8bit` |

权重文件大小不是运行时内存；上下文和系统也要空间。变慢或 swap 就降档：

```bash
./scripts/start_server.sh mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
```

## 限制

- 只支持 Apple Silicon Mac
- 本地模型小，复杂推理和跨文件任务要宿主自己做
- 生成的代码必须自己验证，skill 不保证正确性

细节见 [SKILL.md](SKILL.md)、[references/models.md](references/models.md)、[references/troubleshooting.md](references/troubleshooting.md)。
