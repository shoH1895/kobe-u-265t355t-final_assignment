@echo off
uv sync --dev
uv run playwright install chromium
pause
