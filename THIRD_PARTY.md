# Third-party components

本项目的新创作自有源码采用 MIT。仓库不复制或捆绑 Studio/Core 私有代码、用户数据、第三方视频学习帧、字体、FFmpeg 或 Chromium 二进制。正常安装会通过 pip 及 Playwright 获取外部依赖；这些组件继续适用其原许可，不受本项目 MIT 重新许可。

## Direct Python runtime dependencies

下表对应 `pyproject.toml` 固定版本；许可标识与这些已安装发行包的 metadata/license 文件核对。

| Component | Version | License | Upstream |
|---|---|---|---|
| MCP Python SDK (`mcp`) | 1.26.0 | MIT | [source and license](https://github.com/modelcontextprotocol/python-sdk) |
| Playwright Python | 1.58.0 | Apache-2.0 | [source and license](https://github.com/microsoft/playwright-python) |
| Pillow | 12.1.0 | MIT-CMU | [source and license](https://github.com/python-pillow/Pillow) |
| portalocker | 3.2.0 | BSD-3-Clause | [source and license](https://github.com/wolph/portalocker) |

传递依赖由 pip 安装并保留其发行包中的许可文件。开发工具 `pytest`、`build` 及构建后端 setuptools 仅用于测试和打包。重新分发安装环境时，应根据实际装入的完整依赖清单保留全部适用通知；本表不替代各组件原始许可。

## External executables and browser

- **FFmpeg / ffprobe**：由使用者提供，见 [FFmpeg legal page](https://ffmpeg.org/legal.html)。FFmpeg 构建的许可取决于配置和启用的组件；本工具使用 `libx264` 编码，应核对所用构建附带的许可与配置。这里不发布 FFmpeg 构建，也不承诺所有构建的重新分发条件相同。
- **Chromium**：由 `python -m playwright install chromium` 单独安装。Chromium 及其第三方组件的通知随相应浏览器发行，参阅 [Chromium source](https://www.chromium.org/chromium-projects/) 和所下载浏览器的许可文件。Playwright 的许可不替代浏览器组件许可。
- **系统字体**：Canvas 使用本机 `sans-serif`，仓库未附带字体。使用者添加字体或重新分发渲染环境时需保留对应权利与许可。

## Inputs and synthetic examples

程序内示例使用 FFmpeg 的测试图源和本项目创作的文字、Canvas 图形，运行时在本地生成；演示词钟明确标为 `synthetic`。项目源码和发布树不包含用户媒体。

外部导入的 PNG/JPEG 需要 `rights` 说明，但字段是使用者声明，并不授予或核验任何权利。请仅使用有权处理及分发的素材；本项目许可不覆盖使用者输入。
