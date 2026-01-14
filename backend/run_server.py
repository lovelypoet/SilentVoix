import uvicorn
import time

if __name__ == "__main__":
    print("Starting server... (Press Ctrl+C to stop)")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer stopped")