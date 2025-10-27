import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import base64

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl, Field
import mcp.server.stdio
import fitz  # pymupdf
from PIL import Image
import io

# Store opened PDF documents
pdfs: Dict[str, fitz.Document] = {}
pdf_paths: Dict[str, str] = {}  # Map of PDF IDs to their file paths
pdf_images: Dict[str, Dict[int, List[str]]] = {}  # Map of PDF ID to page number to image paths

server = Server("pdf-reader-mcp")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available PDF resources.
    Each PDF is exposed as a resource with a custom pdf:// URI scheme.
    """
    return [
        types.Resource(
            uri=AnyUrl(f"pdf://{pdf_id}"),
            name=f"PDF: {Path(path).name}",
            description=f"PDF document at {path}",
            mimeType="application/pdf",
        )
        for pdf_id, path in pdf_paths.items()
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific PDF's content by its URI.
    The PDF ID is extracted from the URI host component.
    Returns base64 encoded PDF content.
    """
    if uri.scheme != "pdf":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    pdf_id = uri.host
    if pdf_id in pdf_paths:
        # Read the PDF file and return it as base64 encoded
        with open(pdf_paths[pdf_id], "rb") as file:
            pdf_content = file.read()
            return base64.b64encode(pdf_content).decode("utf-8")

    raise ValueError(f"PDF not found: {pdf_id}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts.
    Each prompt can have optional arguments to customize its behavior.
    """
    return [
        types.Prompt(
            name="summarize-pdf",
            description="Creates a summary of a PDF document",
            arguments=[
                types.PromptArgument(
                    name="pdf_id",
                    description="The ID of the PDF to summarize",
                    required=True,
                ),
                types.PromptArgument(
                    name="style",
                    description="Style of the summary (brief/detailed)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="extract-text-from-pdf",
            description="Extract text from a specific page or range of a PDF",
            arguments=[
                types.PromptArgument(
                    name="pdf_id",
                    description="The ID of the PDF to extract text from",
                    required=True,
                ),
                types.PromptArgument(
                    name="page",
                    description="Page number to extract (starts at 0)",
                    required=False,
                ),
                types.PromptArgument(
                    name="start_page",
                    description="Start page for range extraction (inclusive)",
                    required=False,
                ),
                types.PromptArgument(
                    name="end_page",
                    description="End page for range extraction (inclusive)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="analyze-pdf",
            description="Analyze a PDF and answer questions about its content",
            arguments=[
                types.PromptArgument(
                    name="pdf_id",
                    description="The ID of the PDF to analyze",
                    required=True,
                ),
                types.PromptArgument(
                    name="question",
                    description="The specific question to answer about the PDF content",
                    required=True,
                ),
                types.PromptArgument(
                    name="page_range",
                    description="Optional specific page range to focus on (format: '0-5')",
                    required=False,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt by combining arguments with server state.
    The prompt extracts text from the PDF and can be customized via arguments.
    """
    if not arguments or "pdf_id" not in arguments:
        raise ValueError("Missing required PDF ID argument")

    pdf_id = arguments["pdf_id"]
    if pdf_id not in pdfs:
        raise ValueError(f"PDF not found: {pdf_id}")

    pdf_reader = pdfs[pdf_id]
    pdf_path = pdf_paths[pdf_id]
    pdf_name = Path(pdf_path).name

    if name == "summarize-pdf":
        style = arguments.get("style", "brief")
        detail_prompt = " Give extensive details." if style == "detailed" else ""

        # Extract text from all pages for summarization
        text_content = ""
        total_pages = len(pdf_reader.pages)

        # Get PDF metadata for better context
        metadata = pdf_reader.metadata
        metadata_text = ""
        if metadata:
            metadata_text = "\nDocument Metadata:\n" + "\n".join([f"- {k}: {v}" for k, v in metadata.items()])

        # Create a structured summary of the content with page numbers
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                # Format the text to be easier to read
                page_text = page_text.replace('\n\n', '\n').strip()
                text_content += f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}\n"

        # Instructions for the model are included in the user message since system role isn't available
        return types.GetPromptResult(
            description=f"Summarize PDF: {pdf_name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"# PDF Analysis Task\n\n"
                            f"You are an expert document analyst specializing in PDF analysis and summarization. "
                            f"Your task is to provide a clear, accurate, and well-structured {style} summary of this PDF document titled '{pdf_name}' ({total_pages} pages).{detail_prompt}"
                            f"{metadata_text}\n\n"
                            f"Document Content:\n{text_content}\n\n"
                            f"Based on the content above, please provide:\n"
                            f"1. A concise overview of what this document is about\n"
                            f"2. The main points or arguments presented\n"
                            f"3. Any key findings, conclusions, or recommendations\n"
                            f"4. The structure and organization of the document"
                        ),
                    ),
                )
            ],
        )

    elif name == "extract-text-from-pdf":
        # Handle specific page or page range extraction
        if "page" in arguments:
            page_num = int(arguments["page"])
            if page_num < 0 or page_num >= len(pdf_reader.pages):
                raise ValueError(f"Invalid page number: {page_num}")

            page = pdf_reader.pages[page_num]
            page_text = page.extract_text() or f"No text found on page {page_num}"

            # Format the text for better readability
            page_text = page_text.replace('\n\n', '\n').strip()

            # Add metadata about the document for context
            metadata = pdf_reader.metadata
            metadata_text = ""
            if metadata:
                metadata_text = "\nDocument Metadata:\n" + "\n".join([f"- {k}: {v}" for k, v in metadata.items() if v])

            return types.GetPromptResult(
                description=f"Text from page {page_num + 1} of {pdf_name}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=(
                                f"# PDF Text Extraction\n\n"
                                f"Below is the text extracted from page {page_num + 1} (of {len(pdf_reader.pages)}) of the PDF document titled '{pdf_name}'."
                                f"{metadata_text}\n\n"
                                f"```\n{page_text}\n```\n\n"
                                f"Please work with this text to answer any questions, summarize, or analyze as needed."
                            ),
                        ),
                    )
                ],
            )
        else:
            # Handle page range
            start_page = int(arguments.get("start_page", "0"))
            end_page = int(arguments.get("end_page", str(len(pdf_reader.pages) - 1)))

            if start_page < 0 or end_page >= len(pdf_reader.pages) or start_page > end_page:
                raise ValueError(f"Invalid page range: {start_page}-{end_page}")

            text_content = ""
            for page_num in range(start_page, end_page + 1):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    # Format the text for better readability
                    page_text = page_text.replace('\n\n', '\n').strip()
                    text_content += f"\n--- PAGE {page_num + 1}/{len(pdf_reader.pages)} ---\n{page_text}\n"

            # Add metadata about the document for context
            metadata = pdf_reader.metadata
            metadata_text = ""
            if metadata:
                metadata_text = "\nDocument Metadata:\n" + "\n".join([f"- {k}: {v}" for k, v in metadata.items() if v])

            return types.GetPromptResult(
                description=f"Text from pages {start_page + 1}-{end_page + 1} of {pdf_name}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=(
                                f"# PDF Text Extraction\n\n"
                                f"Below is the text extracted from pages {start_page + 1}-{end_page + 1} (of {len(pdf_reader.pages)}) of the PDF document titled '{pdf_name}'."
                                f"{metadata_text}\n\n"
                                f"```\n{text_content}\n```\n\n"
                                f"Please work with this text to answer any questions, summarize, or analyze as needed."
                            ),
                        ),
                    )
                ],
            )

    elif name == "analyze-pdf":
        question = arguments.get("question", "")
        if not question:
            raise ValueError("Missing question for PDF analysis")

        # Extract text based on specified page range or use all pages
        page_range = arguments.get("page_range", "")
        total_pages = len(pdf_reader.pages)

        start_page = 0
        end_page = total_pages - 1

        # Parse page range if specified
        if page_range:
            try:
                range_parts = page_range.split("-")
                if len(range_parts) == 2:
                    start_page = max(0, int(range_parts[0]))
                    end_page = min(total_pages - 1, int(range_parts[1]))
                else:
                    # Single page specified
                    page_num = int(page_range)
                    start_page = end_page = min(total_pages - 1, max(0, page_num))
            except ValueError:
                raise ValueError(f"Invalid page range format: {page_range}")

        # Extract text from the specified pages
        text_content = ""
        for page_num in range(start_page, end_page + 1):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                # Format the text for better readability
                page_text = page_text.replace('\n\n', '\n').strip()
                text_content += f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}\n"

        # Add metadata for context
        metadata = pdf_reader.metadata
        metadata_text = ""
        if metadata:
            metadata_text = "\nDocument Metadata:\n" + "\n".join([f"- {k}: {v}" for k, v in metadata.items() if v])

        # Create page range description
        pages_desc = f"pages {start_page + 1}-{end_page + 1}" if start_page != end_page else f"page {start_page + 1}"

        return types.GetPromptResult(
            description=f"Analysis of {pdf_name} ({question})",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"# PDF Analysis Request\n\n"
                            f"I need your help analyzing the following PDF document titled '{pdf_name}' ({total_pages} total pages).\n"
                            f"I'm specifically looking at {pages_desc}."
                            f"{metadata_text}\n\n"
                            f"## Question\n{question}\n\n"
                            f"## Document Content\n```\n{text_content}\n```\n\n"
                            f"Please analyze the document content carefully and provide a thorough and accurate answer to my question, "
                            f"citing specific parts of the text where relevant."
                        ),
                    ),
                )
            ],
        )

    else:
        raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
            name="open-pdf",
            description="Open a PDF file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the PDF file"},
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="close-pdf",
            description="Close an open PDF file",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF to close"},
                },
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="list-pdf-metadata",
            description="List metadata of an open PDF",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF to get metadata for"},
                },
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="get-pdf-page-count",
            description="Get the page count of a PDF",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF to get page count for"},
                },
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="get-pdf-page-text",
            description="Get the text content of a specific page in a PDF",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF to get page text from"},
                    "page_number": {"type": "integer", "description": "Page number (0-based index)"},
                },
                "required": ["pdf_id", "page_number"],
            },
        ),
        types.Tool(
            name="pdf-to-text",
            description="Extract all text from a PDF document",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF to extract text from"},
                    "include_page_numbers": {"type": "boolean", "description": "Whether to include page number markers in the output", "default": True},
                    "start_page": {"type": "integer", "description": "Start page number (0-based, inclusive)"},
                    "end_page": {"type": "integer", "description": "End page number (0-based, inclusive)"},
                },
                "required": ["pdf_id"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can modify server state and notify clients of changes.
    """
    if not arguments:
        raise ValueError("Missing arguments")

    if name == "open-pdf":
        path = arguments.get("path")
        if not path:
            raise ValueError("Missing path")

        # Normalize the path to handle spaces, special characters, and tilde expansion
        path = os.path.expanduser(path)
        path = os.path.abspath(path)
        
        # Validate that the file exists and is a PDF
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        
        # Check if it's a file and readable
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        
        if not os.access(path, os.R_OK):
            raise ValueError(f"File is not readable: {path}")

        try:
            # Try to open as PDF
            reader = fitz.open(path)

            # Generate a unique ID
            pdf_id = base64.urlsafe_b64encode(os.path.abspath(path).encode()).decode()[:12]

            # Store the reader and path
            pdfs[pdf_id] = reader
            pdf_paths[pdf_id] = path

            # Notify clients that resources have changed
            await server.request_context.session.send_resource_list_changed()

            return [
                types.TextContent(
                    type="text",
                    text=f"Opened PDF '{os.path.basename(path)}' with {reader.page_count} pages. PDF ID: {pdf_id}",
                )
            ]
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {str(e)}")

    elif name == "close-pdf":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        path = pdf_paths[pdf_id]

        # Remove from storage
        del pdfs[pdf_id]
        del pdf_paths[pdf_id]

        # Notify clients that resources have changed
        await server.request_context.session.send_resource_list_changed()

        return [
            types.TextContent(
                type="text",
                text=f"Closed PDF '{os.path.basename(path)}'",
            )
        ]

    elif name == "list-pdf-metadata":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        reader = pdfs[pdf_id]
        metadata = reader.metadata

        if metadata:
            metadata_text = "\n".join([f"{k}: {v}" for k, v in metadata.items()])
        else:
            metadata_text = "No metadata available"

        return [
            types.TextContent(
                type="text",
                text=f"Metadata for '{os.path.basename(pdf_paths[pdf_id])}':\n\n{metadata_text}",
            )
        ]

    elif name == "get-pdf-page-count":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        reader = pdfs[pdf_id]

        return [
            types.TextContent(
                type="text",
                text=f"'{os.path.basename(pdf_paths[pdf_id])}' has {len(reader.pages)} pages",
            )
        ]

    elif name == "get-pdf-page-text":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        page_number = arguments.get("page_number")
        if page_number is None:
            raise ValueError("Missing page number")

        reader = pdfs[pdf_id]

        # Check if page number is valid
        if page_number < 0 or page_number >= len(reader.pages):
            raise ValueError(f"Invalid page number. PDF has {len(reader.pages)} pages (0-{len(reader.pages)-1})")

        # Extract text from the specified page
        page = reader.pages[page_number]
        page_text = page.extract_text()

        if not page_text:
            page_text = f"No extractable text found on page {page_number}"

        return [
            types.TextContent(
                type="text",
                text=f"Text from page {page_number} of '{os.path.basename(pdf_paths[pdf_id])}':\n\n{page_text}",
            )
        ]

    elif name == "pdf-to-text":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        reader = pdfs[pdf_id]
        include_page_numbers = arguments.get("include_page_numbers", True)

        # Get page range or use all pages
        start_page = arguments.get("start_page", 0)
        end_page = arguments.get("end_page", len(reader.pages) - 1)

        # Validate page range
        if start_page < 0 or start_page >= len(reader.pages):
            start_page = 0
        if end_page < 0 or end_page >= len(reader.pages):
            end_page = len(reader.pages) - 1
        if start_page > end_page:
            start_page, end_page = end_page, start_page

        # Extract text from all pages
        all_text = []
        total_pages = len(reader.pages)

        for page_num in range(start_page, end_page + 1):
            page = reader.pages[page_num]
            page_text = page.extract_text()

            if page_text:
                # Format the text to be easier to read
                page_text = page_text.replace('\n\n', '\n').strip()

                if include_page_numbers:
                    all_text.append(f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}")
                else:
                    all_text.append(page_text)
            elif include_page_numbers:
                all_text.append(f"\n--- PAGE {page_num + 1}/{total_pages} ---\n[No extractable text on this page]")

        # Join all the text
        full_text = "\n".join(all_text)

        # Get PDF metadata for context
        metadata = reader.metadata
        metadata_text = ""
        if metadata:
            metadata_text = "\nDocument Metadata:\n" + "\n".join([f"- {k}: {v}" for k, v in metadata.items() if v])

        # Create page range description
        if start_page == 0 and end_page == total_pages - 1:
            page_range_desc = f"all pages (1-{total_pages})"
        elif start_page == end_page:
            page_range_desc = f"page {start_page + 1}"
        else:
            page_range_desc = f"pages {start_page + 1}-{end_page + 1}"

        return [
            types.TextContent(
                type="text",
                text=(
                    f"Text extracted from {page_range_desc} of '{os.path.basename(pdf_paths[pdf_id])}'"
                    f"{metadata_text}\n\n{full_text}"
                ),
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pdf-reader-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
