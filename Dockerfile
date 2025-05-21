FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
COPY uv.lock ./
COPY src/ ./src/

# Install uv package manager and pdf-reader-mcp
RUN pip install uv && \
    uv pip install --no-cache-dir -e . && \
    pip uninstall -y uv

# Expose the default port (if needed in the future)
# EXPOSE 3000

# Set the entrypoint command to run the server
ENTRYPOINT ["pdf-reader-mcp"]
