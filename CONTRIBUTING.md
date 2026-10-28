# 贡献说明

欢迎针对独立执行路径、宿主适配、文档及真实验证提出 issue 或 pull request。开发环境、合成示例和命令见 [README](README.md)。

## 开发流程

1. 创建独立分支，并使用独立 runtime 和合成测试数据。
2. 说明具体触发条件、修改后的行为和验证范围。
3. 修改契约时同步 `docs/protocol.md`，保留原文、真实全局词钟与完整帧数。
4. 运行与修改相关的测试；媒体/Canvas/工作流修改需运行实际集成测试。

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m pytest -m 'not integration'
python -m pytest -m integration
python -m build
```

集成测试依赖 FFmpeg、ffprobe 和 Chromium。请报告操作系统、Python、FFmpeg 和浏览器版本，不把 mock 通过等同于真实媒体通过。不要提交生成的 runtime、媒体、日志或虚拟环境。

## 必须保持的行为

- 宿主负责推理，最多四名同岗员工处理相邻完整段落；每个人完成本段完整画面工作。
- 不在执行工具中加入隐式模型、ASR、配音、生成素材或钱包请求。
- `synthetic` 与调用方提供的最终 `asr` 证据必须明确区分；摘要绑定不等于来源认证。
- 提交保持领取、CAS、不可变结果历史及跨进程锁；请求渲染后冻结，失败不自动重放。
- 技术执行、媒体事实和审美判断分开；保留 `host_review_required`。
- 新依赖需说明用途和许可；不要引入未知许可素材、字体或私有二进制。

## 数据与许可

贡献者应有权提交其代码和资源。贡献按本项目 [MIT 许可](LICENSE) 提供，依赖和第三方代码须保留各自通知；在 [THIRD_PARTY.md](THIRD_PARTY.md) 记录新增来源。

示例优先使用代码生成的合成内容。不要上传用户视频、人像、第三方学习帧、账户会话、Cookie、密钥、真实配置或私人路径。提交前检查 `git diff --cached` 和追踪文件清单。安全问题参照 [SECURITY.md](SECURITY.md)。
