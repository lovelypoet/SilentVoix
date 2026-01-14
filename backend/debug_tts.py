#!/usr/bin/env python3
"""
Debug script for TTS testing
This will help identify why TTS might not be working
"""

import asyncio
import websockets
import json
import time
import random

def generate_test_data():
    """Generate test sensor data"""
    flex_sensors = [random.randint(200, 800) for _ in range(5)]
    accel = [random.randint(-2000, 2000) for _ in range(3)]
    gyro = [random.randint(-500, 500) for _ in range(3)]
    
    # Normalize flex sensors
    processed = [f/1023.0 for f in flex_sensors]
    processed.extend(accel + gyro)
    
    return processed

async def debug_tts_flow():
    """Debug the TTS flow step by step"""
    print("🔍 TTS Debug Script")
    print("=" * 50)
    print("This script will help debug why TTS might not be working.")
    print()
    
    # Test 1: Check WebSocket connection
    print("1️⃣ Testing WebSocket connection...")
    uri = "ws://localhost:8000/ws/stream"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully!")
            
            # Test 2: Send a single message and check response
            print("\n2️⃣ Testing single prediction...")
            test_data = {
                "right": [0.4, 0.45, 0.38, 0.42, 0.41, 100, -50, 200, 10, -5, 15],
                "timestamp": time.time()
            }
            
            await websocket.send(json.dumps(test_data))
            print("📤 Sent test data")
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if "prediction" in data:
                print(f"✅ Prediction received: '{data['prediction']}'")
                print(f"📊 Confidence: {data.get('confidence', 'N/A')}")
                
                # Test 3: Send multiple predictions
                print("\n3️⃣ Testing multiple predictions...")
                print("   (This will send 5 predictions with different words)")
                
                for i in range(5):
                    test_data = {
                        "right": generate_test_data(),
                        "timestamp": time.time()
                    }
                    
                    await websocket.send(json.dumps(test_data))
                    
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(response)
                        
                        if "prediction" in data:
                            print(f"   [{i+1}] Prediction: '{data['prediction']}'")
                        else:
                            print(f"   [{i+1}] Unexpected response: {data}")
                            
                    except asyncio.TimeoutError:
                        print(f"   [{i+1}] No response received")
                    
                    await asyncio.sleep(0.5)
                
                print("\n✅ Backend is working correctly!")
                print("\n📋 Next steps for TTS debugging:")
                print("1. Open your frontend in the browser")
                print("2. Go to the 'TTS Test' page (new menu item)")
                print("3. Click 'Test Basic TTS' - you should hear audio")
                print("4. If no audio, check:")
                print("   - Browser audio permissions")
                print("   - System volume")
                print("   - Browser console for errors")
                print("5. Then go to 'Live Predict' page")
                print("6. Click 'Connect' and 'TTS Enabled'")
                print("7. Run this script again to send live data")
                
            else:
                print(f"❌ Unexpected response: {data}")
                
    except ConnectionRefusedError:
        print("❌ Cannot connect to WebSocket. Make sure backend is running:")
        print("   python run_server.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_tts_flow())
