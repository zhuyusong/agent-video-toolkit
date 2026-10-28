# Agent Video Toolkit

供 Codex 等宿主平台使用的本地视频执行工具，版本 **0.1.0**。[English](README.en.md)

宿主平台理解原文并安排最多 4 名同岗员工，各自处理不同的相邻完整段落。每名员工都负责本段文意、解释画面、字幕图形、镜头包装及可运行的 Canvas 代码。工具负责冻结输入、领取与提交、校验、合并、逐帧执行、样帧和无声成片导出。

程序独立运行，不依赖 Studio、Core、账户服务器或私有二进制。执行流程没有模型 API、ASR、配音、素材生成和钱包调用。宿主平台自身的模型与额度由宿主管理。

## 安装与完整演示

需要 Python 3.11+、可执行的 `ffmpeg` 与 `ffprobe`（支持 `libx264`），以及 Playwright 安装的 Chromium。依赖和浏览器的首次安装需要联网。

```powershell
git clone https://github.com/zhuyusong/agent-video-toolkit.git
cd agent-video-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m playwright install chromium
```

Linux/macOS 将解释器路径换成 `.venv/bin/python`；Linux 可使用虚拟环境中的 `python -m playwright install --with-deps chromium` 安装浏览器系统依赖。后文简写的 `python` 均指已安装本项目的虚拟环境解释器。把 FFmpeg 的 `bin` 放入 `PATH`，或设置两个可执行文件的绝对路径：

```powershell
$env:AVT_FFMPEG = 'C:\tools\ffmpeg\bin\ffmpeg.exe'
$env:AVT_FFPROBE = 'C:\tools\ffmpeg\bin\ffprobe.exe'
```

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m agent_video --root runtime demo demo-output
```

演示目录必须尚不存在。该命令生成 4 秒、12 fps 的合成底片和明确标为 `synthetic` 的测试词钟，再完成四员工提交、320 像素宽派生预览、48 帧真实执行、编码、全解码及实际成片样帧提取。结束的 JSON 给出 `video`、`receipt` 和 `samples` 路径。示例没有用户数据或真实 ASR；`synthetic_not_asr` 会保留在任务和证明中。

只生成并准备输入可加 `--prepare-only`，随后由宿主完成任务。演示画面用于验证管线，不代表视频设计质量。

## Codex 接入

按照 [Codex 官方 MCP 文档](https://developers.openai.com/codex/mcp)，在 Codex 配置中注册 stdio 服务。解释器必须指向已安装本项目的虚拟环境，`--root` 使用专用的绝对目录。以下路径只是示例，需替换为本机位置：

```toml
[mcp_servers.agent_video]
command = 'C:\work\agent-video-toolkit\.venv\Scripts\python.exe'
args = ["-m", "agent_video.mcp_server", "--root", 'C:\work\agent-video-runtime']
env = { PYTHONIOENCODING = "utf-8", AVT_FFMPEG = 'C:\tools\ffmpeg\bin\ffmpeg.exe', AVT_FFPROBE = 'C:\tools\ffmpeg\bin\ffprobe.exe' }
```

也可用 CLI 注册：

```powershell
codex mcp add agent_video -- C:\work\agent-video-toolkit\.venv\Scripts\python.exe -m agent_video.mcp_server --root C:\work\agent-video-runtime
```

服务进程需要继承可用的 FFmpeg 环境。其他支持本地 stdio MCP 的平台使用相同启动命令。

可以这样给宿主下任务：

> 读取已准备的项目，安排最多四名同岗员工分别处理相邻完整段落。每个人完成文意、解释状态、字幕图形、镜头包装和 Canvas 代码。遵守冻结的 visual_brief、真实 ASR 全局词钟和全部帧数。收齐后合并渲染，查看实际样帧和成片，再报告画面结论。

| MCP 工具 | CLI 子命令 | 作用 |
|---|---|---|
| `avt_projects` | `projects` | 列出本 runtime 的冻结运行 |
| `avt_prepare` | `prepare` | 从本地清单冻结输入、视觉要求、素材和员工范围 |
| `avt_task` | `task` | 领取或读取某员工完整任务，取得 claim token |
| `avt_submit` | `submit` | 提交完整设计和代码，按摘要保护修订 |
| `avt_assemble` | `assemble` | 收齐结果并绑定完整、连续的段落帧覆盖 |
| `avt_render` | `render` | 请求一次本地渲染，随后查询原请求 |
| `avt_status` | `status` | 查询进度及校验后的成片、证明和样帧 |

## 使用自己的输入

创建 `project.json`、真实最终 ASR 转录和对应文件。路径相对于清单所在目录，详见 [输入和员工协议](docs/protocol.md)。

```json
{
  "schema": "avt-project/v1",
  "source": "base.mp4",
  "audio": "recognition.wav",
  "transcript": "transcript.json",
  "assets": []
}
```

转录必须保存精确原文、毫秒词钟、段落的零基半开词范围，以及视频与识别音频的 SHA-256。词文本按顺序拼接必须与原文完全相同，包括标点与空格。ASR 在本工具外完成；不要把估时填成 `kind: "asr"`。`caller_supplied_final_asr` 只记录调用方的声明及文件摘要绑定，不证明识别来源真实性、识别准确性或口型同步。

等价 CLI 流程如下；将尖括号占位符替换成实际返回值：

```powershell
python -m agent_video --root runtime projects
python -m agent_video --root runtime prepare project.json --visual-brief "按原文解释因果，保留人物，文字清晰克制" --workers 4
python -m agent_video --root runtime task <run_id> worker-1 --claimant worker-1
python -m agent_video --root runtime submit <run_id> worker-1 result.json --claim-token <claim_token>
# 每名员工分别 task / submit；全部完成后：
python -m agent_video --root runtime assemble <run_id>
python -m agent_video --root runtime render <run_id> --wait
python -m agent_video --root runtime status <run_id>
```

首次提交不传 `--expected-sha256`；修订时重新读取 task，并传 `--expected-sha256 <previous_result_sha256>`。同一个 claimant 可读取已领取的任务，其他 claimant 不能覆盖。请求渲染后结果冻结。重复调用 render 返回同一请求，包括失败状态；修改代码或从失败、中断重做需创建新运行。

`prepare --preview-width 540` 可实际生成更小的底片，宽度须是偶数且不超过源宽度。程序核验派生片帧率、完整帧数、时长与源一致，保留双源摘要及 `clock_mapping: "identity"`，不会把派生片标成原分辨率或新 ASR。

## 证明和当前边界

每次运行保存在独立的 runtime 子目录。输入和素材复制后绑定摘要；结果按内容摘要保留历史；跨进程锁和 CAS 保护提交；渲染独占锁防止同一运行重复执行。成功状态会核对证明和产物摘要。

渲染器读取实际源帧，每帧创建新的 Canvas Worker，按原全局帧序合并各员工程序，输出无声 H.264 MP4。证明记录输入、词钟、员工结果、派生源、执行帧序摘要、实测媒体及成片抽样。`technical_execution_verified` 和 `full_decode_verified` 是技术事实；`quality_status` 始终为 `host_review_required`。宿主仍需查看画面、文字、人物和视觉解释，不能从哈希或可解码性推断审美通过。

0.1.0 支持恒定帧率（1–120 fps）、从零开始的规则时间戳、方形像素、2–4096 的偶数宽高，以及最多 432,000 帧；非零旋转元数据会被拒绝。先在外部规范化不合格源，再把真实 ASR 绑定到最终源文件。所有输入 JSON 上限为 16 MiB。现有素材仅支持最多 16 张 PNG/JPEG 图片，每张不超过 20 MiB、1600 万像素。暂不提供额外视频 B-roll、透明人物抠像、配音或音频混合。

Canvas 执行的是宿主提交的 JavaScript。Worker、无网络页面和帧截止时间用于执行隔离及故障限制，**不构成操作系统安全沙箱**。只执行可信、审查过的代码；运行用户应有权读取输入文件并写入专用 runtime。字体取本机可用的 `sans-serif`，不同机器的排版可能不同；仓库不附带字体。

## 开发与许可

```powershell
python -m pytest -m "not integration"
python -m pytest -m integration
python -m build
```

集成测试需要上述 FFmpeg 和 Chromium，实际执行渲染、样帧检查、失败防重放及 MCP stdio。详见 [贡献说明](CONTRIBUTING.md) 和 [安全边界](SECURITY.md)。

本项目新创作的自有代码采用 [MIT](LICENSE)：便于不同宿主集成、修改和分发，同时要求保留版权与许可文本。第三方依赖保留各自许可，见 [THIRD_PARTY.md](THIRD_PARTY.md)。仓库不发布用户视频、人像、会话、密钥、私有配置、第三方学习帧或未知许可字体。
