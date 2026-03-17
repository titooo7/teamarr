# Teamarr: Dynamic Sports EPG Generator

Teamarr is a provider-agnostic sports data layer and dynamic EPG (Electronic Program Guide) generator. It is designed to monitor sports events across various providers and automatically generate XMLTV data, often integrating with tools like Dispatcharr for IPTV channel management.

## Project Overview

-   **Backend:** Python 3.11+ using **FastAPI**, **Uvicorn**, and **Pydantic**.
-   **Frontend:** **React 19** SPA built with **Vite**, **TypeScript**, and **Tailwind CSS**.
-   **Database:** **SQLite** with a schema designed for provider-agnostic sports data.
-   **Core Functionality:**
    -   **Provider Integration:** Supports multiple sports data providers including ESPN, TheSportsDB (TSDB), Cricbuzz, and Euroleague.
    -   **EPG Generation:** Generates XMLTV files based on customizable templates for teams and event groups.
    -   **Linear EPG Discovery:** Automatically discovers sports events from external XMLTV sources and maps them to virtual channels.
    -   **Dispatcharr Integration:** Seamlessly integrates with Dispatcharr for automated channel creation and management.
    -   **Scheduling:** Includes a background scheduler for periodic cache refreshes and EPG generation.

## Technical Architecture

-   **`teamarr/api/`**: FastAPI routes and application factory.
-   **`teamarr/consumers/`**: Logic for processing events, matching streams, and generating EPG data.
-   **`teamarr/core/`**: Shared interfaces, types, and sport-specific definitions.
-   **`teamarr/database/`**: Database connection management, schema definitions, and repository layers.
-   **`teamarr/providers/`**: Implementations for various sports data APIs.
-   **`teamarr/services/`**: High-level business logic services (EPG, Cache, Scheduler, etc.).
-   **`teamarr/templates/`**: EPG template resolution and context building.
-   **`frontend/`**: Modern React application for managing settings, channels, and groups.

## Building and Running

### Docker (Recommended)
The project is designed to run in a single container combining both frontend and backend.
```bash
docker compose up -d
```

### Manual Development Setup

#### Backend
1.  **Install Dependencies:**
    ```bash
    pip install -e .[dev]
    ```
2.  **Run Application:**
    ```bash
    python app.py
    ```
3.  **Run Tests:**
    ```bash
    pytest
    ```

#### Frontend
1.  **Navigate to frontend directory:**
    ```bash
    cd frontend
    ```
2.  **Install Dependencies:**
    ```bash
    npm install
    ```
3.  **Run Development Server:**
    ```bash
    npm run dev
    ```
4.  **Build for Production:**
    ```bash
    npm run build
    ```

## Development Conventions

-   **Linting:** Uses `ruff` for Python linting and `eslint` for TypeScript.
-   **Type Safety:** Heavy use of Pydantic models in the backend and TypeScript in the frontend.
-   **Database Migrations:** Schema changes are often handled via idempotent SQL scripts in `teamarr/database/schema.sql` and manual migration functions in `teamarr/api/app.py`.
-   **Logging:** Centralized logging configured in `teamarr/utilities/logging.py`.
-   **Testing:** New features or bug fixes should include corresponding tests in the `tests/` directory.

## Key Files

-   `app.py`: Main entry point for the Python application.
-   `pyproject.toml`: Python project configuration and dependencies.
-   `Dockerfile`: Multi-stage build for frontend and backend.
-   `teamarr/database/schema.sql`: Full SQLite database schema.
-   `frontend/package.json`: Frontend dependencies and scripts.
