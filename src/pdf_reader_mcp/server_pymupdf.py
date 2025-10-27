import asyncio
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import base64
import json

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
import fitz  # pymupdf
from PIL import Image
import io

# Store opened PDF documents
pdfs: Dict[str, fitz.Document] = {}
pdf_paths: Dict[str, str] = {}
pdf_images: Dict[str, Dict[int, List[str]]] = {}  # PDF ID -> page number -> image paths

server = Server("pdf-reader-mcp")

def extract_images_from_page(doc: fitz.Document, page_num: int, pdf_id: str) -> List[str]:
    """Extract images from a page and save them as PNG files."""
    image_paths = []
    page = doc[page_num]
    
    # Get image list from page
    image_list = page.get_images()
    
    if not image_list:
        return image_paths
    
    # Create temp directory for images
    temp_dir = Path(tempfile.gettempdir()) / f"pdf_reader_{pdf_id}"
    temp_dir.mkdir(exist_ok=True)
    
    for img_index, img in enumerate(image_list):
        try:
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            
            if pix.n - pix.alpha < 4:  # GRAY or RGB
                pix_rgb = pix
            else:  # CMYK -> convert to RGB
                pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
            
            img_path = temp_dir / f"page_{page_num}_img_{img_index}.png"
            pix_rgb.save(str(img_path))
            image_paths.append(str(img_path))
            
            if pix != pix_rgb:
                pix_rgb = None
            pix = None
        except Exception as e:
            print(f"Warning: Could not extract image {img_index} from page {page_num}: {e}")
    
    return image_paths

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available PDF resources."""
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
    """Read a specific PDF's content by its URI."""
    if uri.scheme != "pdf":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    pdf_id = uri.host
    if pdf_id in pdf_paths:
        with open(pdf_paths[pdf_id], "rb") as file:
            pdf_content = file.read()
            return base64.b64encode(pdf_content).decode("utf-8")

    raise ValueError(f"PDF not found: {pdf_id}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """List available prompts."""
    return [
        types.Prompt(
            name="summarize-pdf",
            description="Creates a summary of a PDF document",
            arguments=[
                types.PromptArgument(name="pdf_id", description="The ID of the PDF to summarize", required=True),
                types.PromptArgument(name="style", description="Style of the summary (brief/detailed)", required=False)
            ],
        ),
        types.Prompt(
            name="extract-text-from-pdf",
            description="Extract text and images from a specific page or range",
            arguments=[
                types.PromptArgument(name="pdf_id", description="The ID of the PDF", required=True),
                types.PromptArgument(name="page", description="Page number (0-based)", required=False),
                types.PromptArgument(name="start_page", description="Start page", required=False),
                types.PromptArgument(name="end_page", description="End page", required=False),
            ],
        ),
        types.Prompt(
            name="analyze-pdf",
            description="Analyze a PDF and answer questions about its content",
            arguments=[
                types.PromptArgument(name="pdf_id", description="The ID of the PDF", required=True),
                types.PromptArgument(name="question", description="Question to answer", required=True),
                types.PromptArgument(name="page_range", description="Optional page range", required=False),
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    """Generate a prompt with PDF content."""
    if not arguments or "pdf_id" not in arguments:
        raise ValueError("Missing required PDF ID argument")

    pdf_id = arguments["pdf_id"]
    if pdf_id not in pdfs:
        raise ValueError(f"PDF not found: {pdf_id}")

    doc = pdfs[pdf_id]
    pdf_path = pdf_paths[pdf_id]
    pdf_name = Path(pdf_path).name

    if name == "summarize-pdf":
        style = arguments.get("style", "brief")
        text_content = ""
        total_pages = doc.page_count

        # Extract text from all pages
        for page_num in range(total_pages):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                page_text = page_text.replace('\n\n', '\n').strip()
                text_content += f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}\n"

        return types.GetPromptResult(
            description=f"Summarize PDF: {pdf_name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"# PDF Analysis Task\n\n"
                            f"Provide a {style} summary of this PDF document titled '{pdf_name}' ({total_pages} pages).\n\n"
                            f"Document Content:\n{text_content}\n\n"
                            f"Please provide a clear summary with key points and conclusions."
                        ),
                    ),
                )
            ],
        )

    elif name == "extract-text-from-pdf":
        if "page" in arguments:
            page_num = int(arguments["page"])
            if page_num < 0 or page_num >= doc.page_count:
                raise ValueError(f"Invalid page number: {page_num}")

            page = doc[page_num]
            page_text = page.get_text() or f"No text found on page {page_num}"
            page_text = page_text.replace('\n\n', '\n').strip()

            # Extract images from this page
            images = extract_images_from_page(doc, page_num, pdf_id)
            
            image_info = ""
            if images:
                image_info = f"\n\nImages found on this page:\n" + "\n".join([f"- {Path(img).name}" for img in images])

            return types.GetPromptResult(
                description=f"Text from page {page_num + 1} of {pdf_name}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=(
                                f"# PDF Text Extraction\n\n"
                                f"Text from page {page_num + 1} of '{pdf_name}':\n\n"
                                f"```\n{page_text}\n```"
                                f"{image_info}"
                            ),
                        ),
                    )
                ],
            )
        else:
            start_page = int(arguments.get("start_page", "0"))
            end_page = int(arguments.get("end_page", str(doc.page_count - 1)))

            if start_page < 0 or end_page >= doc.page_count or start_page > end_page:
                raise ValueError(f"Invalid page range: {start_page}-{end_page}")

            text_content = ""
            all_images = []
            for page_num in range(start_page, end_page + 1):
                page = doc[page_num]
                page_text = page.get_text()
                if page_text:
                    page_text = page_text.replace('\n\n', '\n').strip()
                    text_content += f"\n--- PAGE {page_num + 1}/{doc.page_count} ---\n{page_text}\n"
                
                # Extract images
                images = extract_images_from_page(doc, page_num, pdf_id)
                all_images.extend(images)

            image_info = ""
            if all_images:
                image_info = f"\n\nImages found in this range:\n" + "\n".join([f"- {Path(img).name}" for img in all_images])

            return types.GetPromptResult(
                description=f"Text from pages {start_page + 1}-{end_page + 1} of {pdf_name}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=(
                                f"# PDF Text Extraction\n\n"
                                f"Text from pages {start_page + 1}-{end_page + 1} of '{pdf_name}':\n\n"
                                f"```\n{text_content}\n```"
                                f"{image_info}"
                            ),
                        ),
                    )
                ],
            )

    elif name == "analyze-pdf":
        question = arguments.get("question", "")
        if not question:
            raise ValueError("Missing question")

        text_content = ""
        total_pages = doc.page_count

        for page_num in range(total_pages):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                page_text = page_text.replace('\n\n', '\n').strip()
                text_content += f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}\n"

        return types.GetPromptResult(
            description=f"Analysis of {pdf_name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"# PDF Analysis Request\n\n"
                            f"Document: {pdf_name} ({total_pages} pages)\n"
                            f"Question: {question}\n\n"
                            f"Content:\n```\n{text_content}\n```\n\n"
                            f"Please analyze and answer the question."
                        ),
                    ),
                )
            ],
        )

    else:
        raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="open-pdf",
            description="Open a PDF file for reading",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Path to the PDF file"}},
                "required": ["path"],
            },
        ),
        types.Tool(
            name="close-pdf",
            description="Close an open PDF file",
            inputSchema={
                "type": "object",
                "properties": {"pdf_id": {"type": "string", "description": "ID of the PDF to close"}},
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="get-pdf-page-count",
            description="Get the page count of a PDF",
            inputSchema={
                "type": "object",
                "properties": {"pdf_id": {"type": "string", "description": "ID of the PDF"}},
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="get-pdf-page-text",
            description="Get text from a specific page with image information",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF"},
                    "page_number": {"type": "integer", "description": "Page number (0-based)"},
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
                    "pdf_id": {"type": "string", "description": "ID of the PDF"},
                    "include_page_numbers": {"type": "boolean", "description": "Include page markers", "default": True},
                    "start_page": {"type": "integer", "description": "Start page (0-based)"},
                    "end_page": {"type": "integer", "description": "End page (0-based)"},
                },
                "required": ["pdf_id"],
            },
        ),
        types.Tool(
            name="extract-images",
            description="Extract images from a PDF page",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_id": {"type": "string", "description": "ID of the PDF"},
                    "page_number": {"type": "integer", "description": "Page number (0-based)"},
                },
                "required": ["pdf_id", "page_number"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent]:
    """Handle tool execution requests."""
    if not arguments:
        raise ValueError("Missing arguments")

    if name == "open-pdf":
        path = arguments.get("path")
        if not path:
            raise ValueError("Missing path")

        path = os.path.expanduser(path)
        path = os.path.abspath(path)
        
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise ValueError(f"File is not readable: {path}")

        try:
            doc = fitz.open(path)
            pdf_id = base64.urlsafe_b64encode(os.path.abspath(path).encode()).decode()[:12]

            pdfs[pdf_id] = doc
            pdf_paths[pdf_id] = path
            pdf_images[pdf_id] = {}

            await server.request_context.session.send_resource_list_changed()

            return [
                types.TextContent(
                    type="text",
                    text=f"Opened PDF '{os.path.basename(path)}' with {doc.page_count} pages. PDF ID: {pdf_id}",
                )
            ]
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {str(e)}")

    elif name == "close-pdf":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        path = pdf_paths[pdf_id]
        pdfs[pdf_id].close()
        del pdfs[pdf_id]
        del pdf_paths[pdf_id]
        if pdf_id in pdf_images:
            del pdf_images[pdf_id]

        await server.request_context.session.send_resource_list_changed()

        return [
            types.TextContent(
                type="text",
                text=f"Closed PDF '{os.path.basename(path)}'",
            )
        ]

    elif name == "get-pdf-page-count":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        doc = pdfs[pdf_id]
        return [
            types.TextContent(
                type="text",
                text=f"'{os.path.basename(pdf_paths[pdf_id])}' has {doc.page_count} pages",
            )
        ]

    elif name == "get-pdf-page-text":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        page_number = arguments.get("page_number")
        if page_number is None:
            raise ValueError("Missing page number")

        doc = pdfs[pdf_id]
        if page_number < 0 or page_number >= doc.page_count:
            raise ValueError(f"Invalid page number (0-{doc.page_count-1})")

        page = doc[page_number]
        page_text = page.get_text() or f"No extractable text found on page {page_number}"
        
        # Get images
        images = extract_images_from_page(doc, page_number, pdf_id)
        image_info = f"\n\nImages on page: {len(images)}"

        return [
            types.TextContent(
                type="text",
                text=f"Text from page {page_number} of '{os.path.basename(pdf_paths[pdf_id])}':\n\n{page_text}{image_info}",
            )
        ]

    elif name == "pdf-to-text":
        pdf_id = arguments.get("pdf_id")
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")

        doc = pdfs[pdf_id]
        include_page_numbers = arguments.get("include_page_numbers", True)
        start_page = arguments.get("start_page", 0)
        end_page = arguments.get("end_page", doc.page_count - 1)

        if start_page < 0 or start_page >= doc.page_count:
            start_page = 0
        if end_page < 0 or end_page >= doc.page_count:
            end_page = doc.page_count - 1
        if start_page > end_page:
            start_page, end_page = end_page, start_page

        all_text = []
        total_pages = doc.page_count

        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            page_text = page.get_text()

            if page_text:
                page_text = page_text.replace('\n\n', '\n').strip()
                if include_page_numbers:
                    all_text.append(f"\n--- PAGE {page_num + 1}/{total_pages} ---\n{page_text}")
                else:
                    all_text.append(page_text)
            elif include_page_numbers:
                all_text.append(f"\n--- PAGE {page_num + 1}/{total_pages} ---\n[No extractable text]")

        full_text = "\n".join(all_text)
        
        if start_page == 0 and end_page == total_pages - 1:
            page_range_desc = f"all pages (1-{total_pages})"
        elif start_page == end_page:
            page_range_desc = f"page {start_page + 1}"
        else:
            page_range_desc = f"pages {start_page + 1}-{end_page + 1}"

        return [
            types.TextContent(
                type="text",
                text=f"Text extracted from {page_range_desc} of '{os.path.basename(pdf_paths[pdf_id])}'\n\n{full_text}",
            )
        ]

    elif name == "extract-images":
        pdf_id = arguments.get("pdf_id")
        page_number = arguments.get("page_number")
        
        if not pdf_id or pdf_id not in pdfs:
            raise ValueError("Invalid PDF ID")
        if page_number is None:
            raise ValueError("Missing page number")

        doc = pdfs[pdf_id]
        if page_number < 0 or page_number >= doc.page_count:
            raise ValueError(f"Invalid page number")

        images = extract_images_from_page(doc, page_number, pdf_id)
        
        if not images:
            return [
                types.TextContent(
                    type="text",
                    text=f"No images found on page {page_number}",
                )
            ]

        image_list = "\n".join([f"- {Path(img).name}" for img in images])
        return [
            types.TextContent(
                type="text",
                text=f"Extracted {len(images)} image(s) from page {page_number}:\n{image_list}",
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pdf-reader-mcp",
                server_version="0.1.1",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
