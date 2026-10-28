# 输入、任务和执行协议 v1

本文对应 Agent Video Toolkit 0.1.0。JSON 拒绝未声明字段及非有限数，每份 JSON 上限 16 MiB；索引和范围使用零基半开区间 `[start, end)`。所有员工保留全局词索引、帧索引和原文，不建立局部估算时钟。

## 项目清单

```json
{
  "schema": "avt-project/v1",
  "source": "base.mp4",
  "audio": "recognition.wav",
  "transcript": "transcript.json",
  "assets": [
    {"id": "chart", "path": "chart.png", "kind": "image", "rights": "Created by the project author"}
  ]
}
```

`schema`、`source`、`transcript` 必填；`audio`、`assets` 可选，但 `kind: "asr"` 转录必须提供识别所用的精确音频文件。路径解析相对于清单目录，可使用绝对本地路径。程序复制输入到本次运行，不修改原文件。`rights` 是调用方的权利说明，工具不验证所有权；应只导入有权使用的素材。

视频要求恒定帧率 1–120 fps、从零开始的规则时间戳、方形像素、偶数宽高 2–4096、1–432,000 帧。非零旋转元数据会被拒绝。应先在外部完成转码和旋转规范化，再把最终 ASR 绑定到该确定源文件。

图片 ID 由英文字母或数字开头，后接英文字母、数字、`_` 或 `-`，总长 1–64 字符。素材仅接受 PNG/JPEG，最多 16 张，每张 20 MiB、1600 万像素以内。

## 真实最终 ASR 转录

以下是结构示意。示例哈希占位符必须换成实际文件的 SHA-256；词钟必须来自最终识别结果。

```json
{
  "kind": "asr",
  "final": true,
  "engine": "Name and version of the actual recognition engine",
  "source_sha256": "<64 lowercase hex characters for base.mp4>",
  "audio_sha256": "<64 lowercase hex characters for recognition.wav>",
  "text": "先准备，再执行。",
  "words": [
    {"id": 0, "text": "先准备，", "start_ms": 0, "end_ms": 900},
    {"id": 1, "text": "再执行。", "start_ms": 1000, "end_ms": 1900}
  ],
  "paragraphs": [{"start_word": 0, "end_word": 2}]
}
```

`words` 为 1–20,000 项，`id` 必须连续等于其数组索引。每个文本非空；按序拼接必须精确等于 `text`，包含全部标点、空格和换行。时间为整数毫秒，单词起点不早于前词终点，`start_ms < end_ms`，均位于视频完整时长内。段落范围按顺序完整覆盖全部词，不能有空段、重叠或遗漏。

ASR 是调用方提供的证据。工具验证原文、时钟结构和视频/音频字节摘要，不鉴别 `engine` 声明、不实际运行识别，也不证明音频与画面同步。请在外部完成这些核对。对估算或演示时间使用 `kind: "synthetic"`、`audio_sha256: null` 并显式传 `allow_synthetic=true`（CLI 为 `--allow-synthetic`）。其输出始终标记 `synthetic_not_asr`，不得冒充最终 ASR。

## 冻结与分工

`prepare(manifest_path, visual_brief, workers=4, preview_width=null, allow_synthetic=false)` 产生新 `run_id`。视觉要求是 6000 字符以内非空文字，按原样冻结到所有任务，不授权改变原文或词钟。

`workers` 为 1–4，实际人数不超过段落数。员工按相邻完整段落均分；首段从第 0 帧开始，下一段从其首词时刻的向上取整帧开始，末段覆盖到视频全部帧数。若两个段落边界落到同一帧，准备失败。所有帧区间连续且恰好覆盖整个视频。

可选预览宽度必须为不小于 2、不超过源宽度的偶数。派生底片按比例缩小；实际探测并全解码校验帧率、全部帧数、时长。冻结上下文同时保留 `source_sha256`、`render_source_sha256`、原/派生媒体信息、原全局词钟摘要和恒等映射 `clock_mapping: "identity"`。

`task(run_id, worker_id, claimant)` 领取并返回 `claim_token`、`previous_result_sha256`、该员工的 `worker.segments` 和完整冻结 `context`。同一 claimant 读取返回同一领取，其他 claimant 被拒绝。claim token 是本地并发协调凭证，runtime 应仅允许受信任用户访问。

## 员工提交

每名员工职责相同，必须对所有分配段落提交完整设计和一份程序：

```json
{
  "schema": "avt-worker/v1",
  "input_sha256": "<from task>",
  "worker_id": "worker-1",
  "designs": [{
    "segment_id": "paragraph-1",
    "meaning": "说明本段的具体含义",
    "visual_explanation": "用具体对象和状态变化解释因果",
    "caption_graphics": "说明字幕分组、位置和图形关系",
    "camera": "说明镜头与人物安排",
    "states": [{
      "start_word": 0,
      "end_word": 2,
      "action": "对象从准备态转为执行态",
      "explanation": "状态转换如何解释原文"
    }],
    "assets": []
  }],
  "code": "helpers.source(); helpers.caption(input.segment.start_word, input.segment.end_word);"
}
```

`designs` 按任务段落顺序逐项覆盖，`states` 按词范围完整覆盖对应段落。每段须有具体文意、解释、字幕图形和镜头说明；`assets` 只能引用冻结素材 ID。程序正文最多 60,000 字符。结构校验不会判断这些说明是否真实体现在画面中，宿主必须查看实际输出。

首次 `submit` 传 claim token 和结果，`expected_sha256=null`。修改现有结果时先重新读取 task，传返回的旧 `previous_result_sha256` 为 `expected_sha256`。不匹配即 CAS 冲突；同一结果重复提交会复用。旧结果按摘要保留。新提交使已有 assembly 失效，需要重新 assemble。请求渲染后禁止修改结果。

## Canvas 函数体

`code` 是同步 JavaScript 函数体，参数为 `ctx`、`input`、`helpers`。不使用 `import`、异步代码、网络或本地文件读取。逐帧从干净 Worker 和 Canvas 执行；不得依赖前一帧变量、随机数、日期或异步状态。需要状态时用全局 `input.frame`、词钟和当前段落计算。

| 值 | 含义 |
|---|---|
| `ctx` | 原生 Canvas2D 上下文 |
| `input.frame` | 零基全局帧索引 |
| `input.time_ms` | 原帧率下该帧的全局毫秒时刻 |
| `input.width`, `input.height` | 当前实际输出尺寸 |
| `input.fps` | 有理数帧率字符串，例如 `30000/1001` |
| `input.frames` | 全部帧数 |
| `input.segment` | 当前原文段，含全局词及帧范围 |
| `input.words` | 冻结的全部原始词与毫秒钟 |
| `helpers.source(x=0,y=0,w=width,h=height)` | 绘制当前真实源帧，可调整目标矩形 |
| `helpers.image(id,x,y,w,h)` | 绘制冻结图片 |
| `helpers.caption(start,end,x=width/2,y=height*.9,size=width/28)` | 显示指定连续短语中已到时间的原词前缀 |

每帧默认先绘制真实源帧。绘图坐标以实际输出像素为单位；按 `input.width/height` 计算布局以兼容预览。helper 字幕只能在当前段落词界内；它不自动换行、分页、避脸或验证阅读时长。员工应选择合适的短语范围、时刻与布局，避免把长段落挤成一行。直接调用 Canvas 文本 API 的内容、显示顺序和原文一致性由宿主审查。

程序每帧完成后必须同步返回；Promise 会被拒绝，超出帧截止时间会终止 Worker 并标记失败。Worker 与页面网络限制不是 OS 安全沙箱，只适用于可信代码。

## 合并、渲染和状态

`assemble` 读取全部结果、重新校验冻结文件和摘要，按原段落范围生成绑定清单。渲染时按每一全局帧选择当前段落所属员工的代码，不改词钟或通过剪短视频规避尾帧。

`render` 在后台启动一次本地进程，使用单独的渲染锁；重复请求返回同一 request ID，成功运行的产物会再次校验，失败也不自动重试。CLI `render --wait` 只等待该请求；等待超时不代表进程已取消，应继续 status。失败或进程中断保留本次数据，需要重做时创建新运行。

`status` 状态包含 `prepared`、`assembled`、`rendering`、`succeeded`、`failed`；检测到丢失执行锁的旧渲染时报告 `interrupted`。成功会返回 `video`、`receipt`、`samples` 的本机路径，并校验产物摘要。

`receipt.json` 记录输入、assembly、各员工结果、原/派生源、词钟、完整执行帧数和逐帧摘要序列摘要。成片必须匹配冻结的帧率、全部帧数、时长、尺寸，且无音轨并通过全解码。样帧从编码后的实际成片提取，覆盖首尾、四分位和段落边界。

这些是技术凭证：`technical_execution_verified: true`、`full_decode_verified: true` 不证明语义、审美或口型。`quality_status: "host_review_required"` 要求宿主另行查看、判断并说明观察范围。证明和设计文本保持独立，不把声明写成视觉验收事实。
