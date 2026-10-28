# 无用户数据的合成示例

安装后，在仓库根运行：

```shell
avt --root runtime demo demo-output
```

这个命令通过 FFmpeg 的 `testsrc2` 生成 4 秒、12 fps、48 帧的测试源片。
它写入明确标记 `kind=synthetic` 的词钟，分配四个相邻段落，提交确定性示例代码，
生成 320×180 派生底片并执行每一帧，最后导出无声 MP4 和实际编码样帧。

`demo-output` 必须不存在，避免覆盖既有文件。完整可读示例实现位于
`src/agent_video/demo.py`；生成的数据和运行记录由 `.gitignore` 排除。
这份示例只证明工程执行路径，不证明真实语音识别、文字口型对齐或视觉质量。

只准备输入、交给宿主模型创作时：

```shell
avt --root runtime demo demo-output --prepare-only
```

随后使用返回的 `run_id`，按 README 的 `task → submit → assemble → render → status` 流程操作。
