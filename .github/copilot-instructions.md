<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# PDF Reader MCP Server

This is an MCP (Model Context Protocol) server project that provides PDF reading and analysis functionality.

You can find more info and examples at:
- https://modelcontextprotocol.io/llms-full.txt
- https://github.com/modelcontextprotocol/python-sdk

## Project Structure

- `src/pdf_reader_mcp/server.py`: Main server implementation with PDF processing functionality
- `src/pdf_reader_mcp/__init__.py`: Entry point for the package
- `.vscode/mcp.json`: VS Code configuration for the MCP server
- `pyproject.toml`: Project configuration and dependencies

## PDF Functionality

This server uses PyPDF2 for:
1. Opening and reading PDF files
2. Extracting text from PDF pages
3. Reading PDF metadata
4. Counting pages in PDFs

## MCP Features Implemented

- Resources: PDF files with custom `pdf://` URI scheme
- Prompts: For summarizing PDFs and extracting text from pages
- Tools: For opening, closing, and inspecting PDFs
