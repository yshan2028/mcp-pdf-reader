# PDF Reader MCP Server for VS Code

An MCP server that enables VS Code to view and analyze PDF documents using the Model Context Protocol (MCP).

## Features

- Open and read PDF documents
- Extract text from PDFs
- View PDF metadata
- Generate summaries of PDF content
- Extract text from specific pages or page ranges

## Installation

1. Ensure you have Python 3.13+ installed
2. Clone this repository
3. Create a virtual environment:
   ```
   uv venv .venv
   source .venv/bin/activate
   ```
4. Install dependencies:
   ```
   uv pip install -e .
   ```

## Usage

This MCP server integrates with VS Code's MCP client to provide PDF reading capabilities.

### Available Tools

- **open-pdf**: Open a PDF file by providing its file path
- **close-pdf**: Close an open PDF file
- **list-pdf-metadata**: View metadata of an open PDF
- **get-pdf-page-count**: Get the total number of pages in a PDF

### Available Prompts

- **summarize-pdf**: Generate a summary of a PDF document
- **extract-text-from-pdf**: Extract text from specific pages or page ranges

## VS Code Configuration

The server is configured to run in VS Code through the `.vscode/mcp.json` file.

## Development

To make changes to this project:

1. Modify the code in the `src/pdf_reader_mcp` directory
2. Install in development mode: `uv pip install -e .`
3. Test your changes in VS Code

## Requirements

- Python 3.13+
- PyPDF2 3.0.0+
- MCP SDK 1.9.0+
- VS Code with MCP extension

### Prompts

The server provides a single prompt:
- summarize-notes: Creates summaries of all stored notes
  - Optional "style" argument to control detail level (brief/detailed)
  - Generates prompt combining all current notes with style preference

### Tools

The server implements one tool:
- add-note: Adds a new note to the server
  - Takes "name" and "content" as required string arguments
  - Updates server state and notifies clients of resource changes

## Configuration

[TODO: Add configuration details specific to your implementation]

## Quickstart

### Install

#### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  ```
  "mcpServers": {
    "pdf-reader-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/pieterm@backbase.com/Documents/Code/ai/MCP/mcp-uv-pdf-reader",
        "run",
        "pdf-reader-mcp"
      ]
    }
  }
  ```
</details>

<details>
  <summary>Published Servers Configuration</summary>
  ```
  "mcpServers": {
    "pdf-reader-mcp": {
      "command": "uvx",
      "args": [
        "pdf-reader-mcp"
      ]
    }
  }
  ```
</details>

## Development

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/pieterm@backbase.com/Documents/Code/ai/MCP/mcp-uv-pdf-reader run pdf-reader-mcp
```


Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.