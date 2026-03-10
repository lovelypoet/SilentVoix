import httpx
import json
import time
import os

WORKER_URL = "http://localhost:8095"

def test_health():
    print("Checking worker health...")
    try:
        response = httpx.get(f"{WORKER_URL}/health")
        print(f"Health: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_process_video(video_path):
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        return

    print(f"Sending video for processing: {video_path}")
    files = {
        "video_file": open(video_path, "rb")
    }
    data = {
        "options_json": json.dumps({
            "generate_overlay": True,
            "calculate_metrics": False
        })
    }
    
    response = httpx.post(f"{WORKER_URL}/v1/jobs/process", files=files, data=data)
    job = response.json()
    job_id = job["job_id"]
    print(f"Job created: {job_id}")
    
    while True:
        status_res = httpx.get(f"{WORKER_URL}/v1/jobs/{job_id}")
        status_data = status_res.json()
        print(f"Status: {status_data['status']} | Progress: {status_data.get('progress', 0)}")
        
        if status_data["status"] in ["completed", "failed"]:
            print(f"Final Job Data: {json.dumps(status_data, indent=2)}")
            break
            
        time.sleep(2)

if __name__ == "__main__":
    test_health()
    # Note: Requires a real test video to run full process
    # test_process_video("test.mp4")
