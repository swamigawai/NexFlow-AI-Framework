# Quick Start Guide

## Prerequisites
- Python 3.9+
- pip

## 1. Setup Environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configuration
```bash
cp config/.env.example .env
```

## 3. Run Your First Scrape
```bash
python -m execution.scrape_single_site --url "https://example.com" --selectors "{\"title\": \"h1\"}" --output data/output/example.json
```

## 4. Run Tests
```bash
pytest
```

## Troubleshooting
- **ModuleNotFoundError**: Always run scripts using `python -m execution.script_name` from the project root.
- **Permission Denied**: Ensure you have write permissions for `logs/` and `data/` directories.
