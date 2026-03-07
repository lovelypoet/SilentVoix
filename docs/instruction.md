# Sign Glove Development Instructions

This document covers local setup for the current SilentVoix stack. The active product scope is model upload, runtime validation, live inference, and dataset management for external training workflows.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python 3.10+**: For the backend.
*   **Node.js (LTS version)**: For the frontend.
*   **npm**: Node package manager, usually installed with Node.js.
*   **MongoDB**: A running MongoDB instance (local or remote). For local development, ensure a local MongoDB server is running.

## 1. Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
    *   **Troubleshooting `externally-managed-environment` error:** If `pip install` fails with this error, it means your system Python is managed by the OS. Always use a virtual environment as shown above.

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements-api.txt
    ```
    Use `requirements.txt` only if you explicitly need the legacy all-in-one ML environment.

4.  **Configure MongoDB Connection:**
    The application uses a `.env` file for configuration.
    *   If you are using a **local MongoDB instance**, ensure your `backend/.env` file either does not contain a `MONGO_URI` line, or it is commented out (e.g., `# MONGO_URI=...`). The default `MONGO_URI` in `backend/core/settings.py` is `mongodb://localhost:27017`.
    *   If you are using a **remote MongoDB Atlas cluster**, update the `MONGO_URI` in `backend/.env` with your connection string.

    Example `backend/.env` for local MongoDB:
    ```
    # MONGO_URI=mongodb+srv://your_user:your_password@your_cluster.mongodb.net/your_db?retryWrites=true&w=majority
    DB_NAME=signglove
    ```

5.  **Create Default Users:**
    Run the user creation script to populate the database with default login credentials.
    ```bash
    python3 create_users.py
    ```
    *   **Expected Output:** You should see messages indicating that `admin@signglove.com`, `editor@signglove.com`, and `user@signglove.com` are created (or already exist).
    *   **Default Credentials:**
        *   Admin: `admin@signglove.com` / `admin123`
        *   Editor: `editor@signglove.com` / `editor123`
        *   User: `user@signglove.com` / `user123`

## 2. Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd vue-next
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

## 3. Running the Application

Use `run_dev.sh` for the lightweight local API + frontend flow. Use Docker profiles when you need the split runtime services.

1.  **Navigate back to the project root directory:**
    ```bash
    cd ..
    ```

2.  **Run the development script:**
    ```bash
    ./run_dev.sh
    ```
    This script will:
    *   Activate the Python virtual environment for the backend.
    *   Start the FastAPI backend server in the background.
    *   Start the Vue.js frontend development server in the background.

3.  **Access the Application:**
    Once both servers are running, open your web browser and navigate to:
    ```
    http://localhost:5173
    ```

4.  **Log In:**
    Use the default credentials created earlier, for example:
    *   **Email:** `admin@signglove.com`
    *   **Password:** `admin123`
 
### Docker dev stack with runtimes

`docker-compose.dev.yml` now starts the full development stack by default, including:
- `ml-tensorflow`
- `ml-pytorch`
- `worker-library`

Run:

```bash
docker compose -f docker-compose.dev.yml up -d
```

Service URLs:
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- TensorFlow runtime: `http://localhost:8091/health`
- PyTorch runtime: `http://localhost:8092/health`
- Worker library: `http://localhost:8093/health`

## 4. Troubleshooting

*   **`ModuleNotFoundError`**: If you encounter this, ensure you have activated your Python virtual environment (`source backend/venv/bin/activate`) and installed the API dependency set (`pip install -r backend/requirements-api.txt`).
*   **MongoDB Connection Errors (e.g., DNS errors)**:
    *   Verify your `MONGO_URI` in `backend/.env` is correct for your setup (local vs. Atlas).
    *   Ensure your local MongoDB instance is running if you're using it.
    *   If using MongoDB Atlas, check your network connectivity and Atlas cluster status.
*   **`net::ERR_CONNECTION_REFUSED` or `500 Internal Server Error` on login**:
    *   Ensure both the backend and frontend servers are running.
    *   Check the backend server's console for any error messages.
    *   Confirm that the `MONGO_URI` is correctly configured and the backend can connect to the database.
*   **Frontend not loading**: Ensure `npm install` was successful in the `vue-next` directory and that the `npm run dev` command is running without errors.
*   **Runtime-check or predict fails in Docker**:
    *   Confirm `USE_RUNTIME_SERVICES=true`.
    *   Confirm the `8091`, `8092`, and `8093` health endpoints respond.
    *   Confirm uploaded model metadata has the correct `export_format`.

If you encounter persistent issues, please provide detailed error messages and the steps you've taken.
