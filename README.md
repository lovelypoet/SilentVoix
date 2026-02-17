# SilentVoix

A sign language glove project that translates hand gestures into text and speech using machine learning.

## Overview

SilentVoix is an innovative assistive technology project that uses a smart glove equipped with sensors to recognize sign language gestures and convert them to speech. The system consists of a hardware component (ESP32-based glove with sensors), a backend API (FastAPI/Python), and a web-based frontend (Vue 3) for configuration, training, and monitoring.

## Features

- **Real-time Gesture Recognition**: Recognizes hand gestures using sensor data from the glove
- **Text-to-Speech (TTS)**: Converts recognized gestures to spoken words
- **Training Interface**: Web-based UI for collecting training data and improving gesture recognition
- **User Management**: Role-based authentication with admin, editor, and user roles
- **Audio Management**: Upload and manage custom audio files for different gestures
- **MongoDB Integration**: Stores gesture data, user information, and training datasets

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+**: For the backend
- **Node.js (LTS version)**: For the frontend
- **npm**: Node package manager, usually installed with Node.js
- **MongoDB**: A running MongoDB instance (local or remote)

## Quick Start

### 1. Backend Setup

Navigate to the backend directory and set up the Python environment:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Configure MongoDB Connection:**

Create or edit `backend/.env` file:

```env
# For local MongoDB (default: mongodb://localhost:27017)
# MONGO_URI=mongodb://localhost:27017
DB_NAME=signglove

# For MongoDB Atlas (uncomment and update with your credentials)
# MONGO_URI=mongodb+srv://your_user:your_password@your_cluster.mongodb.net/your_db?retryWrites=true&w=majority
```

> **⚠️ Security Note**: Never commit credentials to version control. Use environment variables and keep your `.env` file in `.gitignore`.

**Create Default Users:**

```bash
python3 create_users.py
```

Default credentials (for development only):
- Admin: `admin@signglove.com` / `admin123`
- Editor: `editor@signglove.com` / `editor123`
- User: `user@signglove.com` / `user123`

> **⚠️ Security Warning**: These are default development credentials. Change all passwords before deploying to production.

### 2. Frontend Setup

Navigate to the frontend directory and install dependencies:

```bash
cd vue-next
npm install
```

### 3. Running the Application

Use the convenience script to start both servers:

```bash
./run_dev.sh
```

This will start:
- Backend API server on `http://localhost:8000`
- Frontend dev server on `http://localhost:5173`

Access the application at `http://localhost:5173` and log in with the default credentials.

## Project Structure

```
SilentVoix/
├── backend/          # FastAPI backend
│   ├── core/         # Core settings and configuration
│   ├── models/       # Database models
│   ├── routes/       # API routes
│   ├── services/     # Business logic
│   └── main.py       # Application entry point
├── vue-next/         # Vue 3 frontend
│   ├── src/          # Source code
│   └── tests/        # Frontend tests
├── mongo-init/       # MongoDB initialization scripts
└── run_dev.sh        # Development server launcher
```

## Troubleshooting

**ModuleNotFoundError**: Ensure you have activated your Python virtual environment and installed all dependencies.

**MongoDB Connection Errors**: 
- Verify your `MONGO_URI` in `backend/.env` is correct
- Ensure MongoDB is running locally or your Atlas cluster is accessible

**Connection Refused Errors**:
- Ensure both backend and frontend servers are running
- Check the logs in `logs/backend.log` and `logs/frontend.log`

**Frontend not loading**: 
- Ensure `npm install` completed successfully
- Check that port 5173 is not already in use

## Development

For more detailed development instructions, see [instruction.md](instruction.md).

## License

This project is part of an assistive technology initiative for sign language communication.
