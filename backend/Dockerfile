# --- Build Stage: Install uv and project dependencies ---
FROM python:3.14-slim

# Copy the uv binary directly from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


COPY . /app
# Set working directory and environment variables
WORKDIR /app

RUN uv sync --frozen --no-cache


# Run the FastAPI app using production configurations
CMD ["/app/.venv/bin/fastapi", "run", "main.py", "--port", "80", "--host", "0.0.0.0"]