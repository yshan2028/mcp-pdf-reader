# PDF Reader MCP 服务器 - VS Code 版

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/downloads/)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Q5Q81N7WMO)

**[English](README.md)** | **[中文文档](README_ZH.md)** (当前页面)

一个 MCP 服务器，使 VS Code 能够使用模型上下文协议 (MCP) 查看和分析 PDF 文档。

本项目基于 [模型上下文协议 Python SDK](https://github.com/modelcontextprotocol/python-sdk) 和 FastMCP 创建。

## ✨ 功能特性

- 📖 打开并读取 PDF 文档
- 📝 提取 PDF 文本（整个文档或特定页面）
- 📊 查看 PDF 元数据
- 📄 生成 PDF 内容摘要
- 🔍 提取特定页面或页面范围的文本
- 💭 分析 PDF 内容并回答相关问题

## 📦 安装

1. 确保已安装 Python 3.13+
2. 克隆此仓库
3. 创建虚拟环境：

```bash
uv venv .venv
source .venv/bin/activate
```

4. 安装依赖：

```bash
uv pip install -e .
```

## 🐳 Docker

也可以使用 Docker 运行此 MCP 服务器：

### 构建 Docker 镜像

```bash
docker build -t pdf-reader-mcp .
```

### 运行容器

```bash
docker run --name pdf-reader-mcp -it pdf-reader-mcp
```

### 与 VS Code 或 Claude Desktop 配合使用

使用 Docker 时，更新你的 MCP 配置以使用 Docker 容器：

#### VS Code 配置 (Docker)

```json
{
  "servers": {
    "pdf-reader": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run",
        "--rm", 
        "-i",
        "pdf-reader-mcp"
      ]
    }
  }
}
```

#### Claude Desktop 配置 (Docker)

```json
{
  "mcpServers": {
    "pdf-reader-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm", 
        "-i",
        "pdf-reader-mcp"
      ]
    }
  }
}
```

## 🚀 使用方法

此 MCP 服务器与 VS Code 的 MCP 客户端集成，提供 PDF 阅读功能。有关可用功能的详细信息，请参见下面的工具和提示部分。

## 📸 示例

### VS Code Copilot 中的 MCP 工具

该图显示了通过 MCP 协议在 VS Code 中可用的 PDF Reader 工具：

![VS Code Copilot 中的 PDF Reader MCP 工具](./images/CoPilot_MCP_Tools.png)

### 使用示例

以下是使用 PDF Reader 分析文档的示例：

![PDF Reader 使用示例](./images/Example_Usage.png)

## ⚙️ VS Code 配置

该服务器通过 `.vscode/mcp.json` 文件配置为在 VS Code 中运行。VS Code 必须安装 MCP 扩展才能使用此服务器。

安装 VS Code MCP 扩展：
1. 打开 VS Code
2. 转到扩展 (Ctrl+Shift+X 或 Cmd+Shift+X)
3. 搜索 "Model Context Protocol"
4. 安装 Microsoft 提供的扩展

安装扩展后，VS Code 将能够根据 `.vscode/mcp.json` 文件中的配置与此 MCP 服务器通信。你可以通过 VS Code 的 Copilot 或 VS Code 中内置的任何其他 MCP 客户端使用 MCP 服务器。

## 🔧 开发

对此项目进行更改：

1. 修改 `src/pdf_reader_mcp` 目录中的代码
2. 以开发模式安装：`uv pip install -e .`
3. 在 VS Code 中测试更改

## 📋 需求

- Python 3.13+
- PyPDF2 3.0.0+
- MCP SDK 1.9.0+ (来自 [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk))
- VS Code 与 MCP 扩展

## 🛠️ 工具和提示

### 工具

服务器实现以下工具：

- **open-pdf**: 打开 PDF 文件
  - 接受 `path` 作为必需的字符串参数
  - 返回用于在其他操作中引用的唯一 PDF ID

- **close-pdf**: 关闭打开的 PDF 文件
  - 接受 `pdf_id` 作为必需的字符串参数
  
- **list-pdf-metadata**: 查看打开的 PDF 的元数据
  - 接受 `pdf_id` 作为必需的字符串参数
  
- **get-pdf-page-count**: 获取 PDF 中的总页数
  - 接受 `pdf_id` 作为必需的字符串参数

- **get-pdf-page-text**: 获取 PDF 中特定页面的文本内容
  - 接受 `pdf_id` 作为必需的字符串参数
  - 接受 `page_number` 作为必需的整数参数 (0-based 索引)

- **pdf-to-text**: 从 PDF 文档中提取所有文本
  - 接受 `pdf_id` 作为必需的字符串参数
  - 可选 `include_page_numbers` 作为布尔值 (默认: true)
  - 可选 `start_page` 和 `end_page` 作为整数以提取特定范围

### 提示

服务器提供以下提示：

- **summarize-pdf**: 生成 PDF 文档摘要
  - 需要 `pdf_id` 参数来标识 PDF
  - 可选 `style` 参数来控制详细程度 (brief/detailed)

- **extract-text-from-pdf**: 从特定页面或页面范围提取文本
  - 需要 `pdf_id` 参数
  - 可选页面或页面范围参数 (`page`, `start_page`, `end_page`)

- **analyze-pdf**: 分析 PDF 并回答关于其内容的问题
  - 需要 `pdf_id` 参数
  - 需要 `question` 参数指定要分析的内容
  - 可选 `page_range` 参数以关注特定页面

## 🎯 快速开始

### 安装

#### VS Code

通过编辑项目中的 `.vscode/mcp.json` 来配置 VS Code 使用 MCP 服务器：

<details>
  <summary>开发配置</summary>

```json
{
  "servers": {
    "pdf-reader": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "${workspaceFolder}",
        "run",
        "python",
        "-c",
        "from pdf_reader_mcp import main; main()"
      ]
    }
  }
}
```
</details>

<details>
  <summary>发布包配置</summary>

```json
{
  "servers": {
    "pdf-reader": {
      "type": "stdio",
      "command": "pdf-reader-mcp"
    }
  }
}
```
</details>

#### Claude Desktop

在 MacOS 上：`~/Library/Application\ Support/Claude/claude_desktop_config.json`
在 Windows 上：`%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>开发/未发布服务器配置</summary>

```json
{
  "mcpServers": {
    "pdf-reader-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "${workspaceFolder}",
        "run",
        "pdf-reader-mcp"
      ]
    }
  }
}
```
</details>

<details>
  <summary>已发布服务器配置</summary>

```json
{
  "mcpServers": {
    "pdf-reader-mcp": {
      "command": "uvx",
      "args": [
        "pdf-reader-mcp"
      ]
    }
  }
}
```
</details>

## 🔨 开发

### 构建和发布

准备用于发布的包：

1. 同步依赖项并更新锁定文件：

```bash
uv sync
```

2. 构建包分发：

```bash
uv build
```

这将在 `dist/` 目录中创建源和 wheel 分发。

3. 发布到 PyPI：

```bash
uv publish
```

注意：你需要通过环境变量或命令标志设置 PyPI 凭证：

- Token：`--token` 或 `UV_PUBLISH_TOKEN`
- 或用户名/密码：`--username`/`UV_PUBLISH_USERNAME` 和 `--password`/`UV_PUBLISH_PASSWORD`

### 调试

由于 MCP 服务器通过 stdio 运行，调试可能具有挑战性。为了获得最佳调试体验，我们强烈建议使用 [MCP Inspector](https://github.com/modelcontextprotocol/inspector)。

你可以通过 [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) 使用此命令启动 MCP Inspector：

```bash
npx @modelcontextprotocol/inspector uv --directory "${workspaceFolder}" run pdf-reader-mcp
```

启动后，Inspector 将显示一个 URL，你可以在浏览器中访问该 URL 开始调试。

## 🤝 贡献

1. Fork 该仓库
2. 创建新分支 (`feature-branch`)
3. 提交你的更改
4. Push 到你的分支并提交 PR！

## 📄 许可证

此项目采用 **MIT License** 许可。

## 💬 联系方式

如有问题或需要支持，请通过 [GitHub Issues](https://github.com/yshan2028/mcp-pdf-reader/issues) 联系我们。
