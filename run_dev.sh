#!/bin/bash

# Trap to kill all background processes on script exit
trap "kill 0" EXIT

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Starting backend..."
cd backend
# Activate virtual environment
if [ -d "venv" ]; then
  source venv/bin/activate
elif [ -d ".venv" ]; then
  source .venv/bin/activate
fi
# Run backend with uvicorn, reloading on changes
# Redirect stdout/stderr to log files to keep terminal clean
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd vue-next
# Install npm dependencies if not already installed
if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi
# Run frontend dev server
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Both servers are running. Check logs/backend.log and logs/frontend.log for output."
echo "Press Ctrl+C to stop both servers."

wait
