# Repository Guidelines

## Project Structure & Module Organization
- `app/` is the Flask application package (factory in `app/__init__.py`).
- `app/routes/` contains Blueprints and HTTP endpoints.
- `app/services/` holds business logic and integrations (market data, OCR, caching).
- `app/models/` contains SQLAlchemy models; SQLite files live in `data/`.
- `app/templates/` and `app/static/` contain Jinja2 templates and frontend assets.
- `config.py` defines runtime configuration and default paths (SQLite, uploads, logs).

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs Python dependencies.
- `python run.py` starts the Flask dev server (debug mode).
- `start.bat` is a Windows convenience wrapper for local startup.

The app runs locally at `http://127.0.0.1:5000`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, keep functions and variables `snake_case`.
- Classes and SQLAlchemy models follow `CamelCase` (see `app/models/`).
- JavaScript and CSS live in `app/static/`; keep filenames descriptive (e.g., `trade_stats.js`).
- Match existing patterns in nearby files rather than introducing new styles.

## Testing Guidelines
- A `tests/` layout exists (`api/`, `services/`, `e2e/`, `fixtures/`) but contains no committed tests yet.
- If you add tests, place them under the relevant subfolder and name files `test_*.py`.
- Document the runner you introduce (e.g., add `pytest` to `requirements.txt` and update this file).

## Commit & Pull Request Guidelines
- Recent commits use short, plain summaries (often Chinese) without prefixes. Keep messages concise and descriptive.

PRs should include:
- A brief summary of changes and affected areas (routes, services, templates).
- Testing steps you ran (or note “not run” with a reason).
- Screenshots for UI/template changes (`app/templates/`, `app/static/`).
- Notes for data/schema changes (SQLite files in `data/` and migration logic in `app/services/migration.py`).

## Security & Configuration Tips
- Set `SECRET_KEY` and database URLs via environment variables for non-dev use.
- Default SQLite files: `data/stock.db` and `data/private.db`.
- Uploaded OCR images are stored in `uploads/`; avoid committing generated data.
