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

> 本仓库是独立分发版。路由引擎在 [pigmodel 开发仓库](https://github.com/igpig1226/pigmodel) 继续开发；使用 wastedRAM 不需要了解该仓库。

## Quick Start

当前尚未发布到 PyPI，先从 Git 安装。需要 Apple Silicon Mac 和 Python 3.10+。

```bash
pip install 'wastedram[mlx] @ git+https://github.com/igpig1226/wastedRAM.git'
export WASTEDRAM_CLOUD_URL='https://api.deepseek.com/v1'
export WASTEDRAM_CLOUD_API_KEY='你的密钥'
```

在两个终端分别运行这两行；首次启动会下载选中的模型：

```bash
mlx_lm.server --model "$(wastedram model)" --port 8080 --host 127.0.0.1
wastedram run "问题"
```

`wastedram model` 根据物理统一内存输出推荐模型。发布到 PyPI 后，安装命令可简化为 `pip install 'wastedram[mlx]'`。

## 内存档位

下列模型仓库已核对。权重文件大小仅供估算，**不是运行时内存**；上下文、系统和其他应用也需要空间。8GB 机器用 7B 4bit；若发生交换内存或明显变慢，请降档或缩短上下文。

| Mac 统一内存 | 推荐模型 | 权重文件约 |
| --- | --- | ---: |
| ≤16GB | [Qwen2.5-Coder-7B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-Coder-7B-Instruct-4bit) | 4.0 GiB |
| 17–32GB | [Qwen2.5-Coder-7B-Instruct-8bit](https://huggingface.co/mlx-community/Qwen2.5-Coder-7B-Instruct-8bit) | 7.5 GiB |
| 33–48GB | [Qwen2.5-Coder-14B-Instruct-8bit](https://huggingface.co/mlx-community/Qwen2.5-Coder-14B-Instruct-8bit) | 14.6 GiB |
| 49–64GB | [Qwen2.5-Coder-32B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-Coder-32B-Instruct-4bit) | 17.2 GiB |
| 65–127GB | [Qwen2.5-72B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen2.5-72B-Instruct-4bit) | 38.1 GiB |
| ≥128GB | [Qwen2.5-72B-Instruct-8bit](https://huggingface.co/mlx-community/Qwen2.5-72B-Instruct-8bit) | 71.9 GiB |

96GB 与 128GB 档使用通用 72B Instruct，并非 Coder 专版。大模型不保证每项任务更好；按实际质量和速度选。要手动覆盖模型，启动服务器时指定 `--model`，提问时指定相同的 `--local-model`。

## 配置

| 变量 | 用途 |
| --- | --- |
| `WASTEDRAM_CLOUD_URL` | 云服务 OpenAI 兼容 `/v1` 地址，必填。 |
| `WASTEDRAM_CLOUD_API_KEY` | 云服务密钥；DeepSeek 等服务需要。 |
| `WASTEDRAM_LOCAL_URL` | 本地服务地址，默认 `http://127.0.0.1:8080`。 |

旧的 `PIGMODEL_CLOUD_URL`、`PIGMODEL_CLOUD_API_KEY`、`PIGMODEL_LOCAL_URL` 仍可作为兼容别名；新变量优先。见 [.env.example](.env.example)。CLI 不会自动读取 `.env`，请在 shell 中导出变量，也不要提交密钥。`--local-url`、`--local-model` 和 `--cloud-model` 可按次覆盖。

## 它怎样节省云端 token

短且适合本地处理的任务走 MLX，复杂任务走云端。相同请求可从本机缓存读取，避免重复调用。部分请求会压缩上下文；本地失败时回退云端。实际节省量取决于任务、缓存命中率与云服务计费方式。

## 常见问题

<details>
<summary><strong>我用 Ollama，怎么切换？</strong></summary>

把本地地址设为 Ollama 的 OpenAI 兼容接口，并指定已安装模型：

```bash
WASTEDRAM_LOCAL_URL=http://127.0.0.1:11434 wastedram run "问题" --local-model qwen2.5-coder:7b
```
</details>

<details>
<summary><strong>怎样使用工作流模式？</strong></summary>

```bash
wastedram run "任务" --mode workflow
```

该模式让云端规划、局部任务在本地执行、云端整合。它只处理文本；内置代码检查覆盖有限，输出仍需审查。
</details>

<details>
<summary><strong>如何安装为 agent skill？</strong></summary>

将 [skills/wastedram/SKILL.md](skills/wastedram/SKILL.md) 复制到支持 `SKILL.md` 的 agent skills 目录。wheel 也把这份文件安装到 Python 前缀的 `share/wastedram/skills/wastedram/`。
</details>

仓库脚本 `scripts/start_local.sh` 可检查端口并等待服务就绪；传入模型 ID 可覆盖推荐值。大模型首次下载和载入可能超过默认 30 秒等待，可设置 `WASTEDRAM_READY_TIMEOUT=180`。

## English

wastedRAM routes small text tasks to a local MLX model and complex tasks to an OpenAI-compatible cloud endpoint on Apple Silicon Macs. Install from Git using the command above until a PyPI release exists. Set `WASTEDRAM_CLOUD_URL` and `WASTEDRAM_CLOUD_API_KEY`, then run the two Quick Start commands. `wastedram model` selects a model based on unified memory from 8GB through 128GB; pass `--local-model` to override it. The local URL defaults to `http://127.0.0.1:8080`. Ollama users can set `WASTEDRAM_LOCAL_URL=http://127.0.0.1:11434` and pass an installed model. Legacy `PIGMODEL_*` variables remain supported. Savings depend on the task mix and cache hits; review generated code before use.
