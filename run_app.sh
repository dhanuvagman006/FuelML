#!/bin/bash

# Start the Backend (FastAPI) in the background
echo "🚀 Starting Biofuel AI Backend (FastAPI)..."
source venv/bin/activate
uvicorn phase3_backend_api:app --reload --port 8000 &
BACKEND_PID=$!

# Wait a couple of seconds to ensure the backend starts before the frontend
sleep 2

# Start the Frontend (Vite/React) in the background
echo "🚀 Starting Biofuel React Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================================"
echo "✅ Both servers are now running successfully!"
echo "📡 Backend API available at:    http://localhost:8000"
echo "🖥️  Frontend UI available at:    http://localhost:5173"
echo "========================================================"
echo "Press Ctrl+C to stop both servers."

# Trap termination signals to kill both background processes cleanly
trap "echo -e '\n🛑 Shutting down both servers...'; kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM EXIT

# Wait infinitely so the script doesn't exit until interrupted
wait 
