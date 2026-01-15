// MongoDB initialization script for Sign Glove application
db = db.getSiblingDB('signglove');

// Create collections with proper indexes
db.createCollection('gestures');
db.createCollection('sensor_data');
db.createCollection('training_results');
db.createCollection('audio_files');
db.createCollection('models');

// Create indexes for better performance
db.gestures.createIndex({ "gesture_name": 1 }, { unique: true });
db.gestures.createIndex({ "created_at": -1 });
db.sensor_data.createIndex({ "gesture_id": 1 });
db.sensor_data.createIndex({ "timestamp": -1 });
db.training_results.createIndex({ "created_at": -1 });
db.audio_files.createIndex({ "filename": 1 }, { unique: true });

// Insert some sample gesture data if needed
db.gestures.insertMany([
  {
    gesture_name: "hello",
    description: "Greeting gesture",
    created_at: new Date(),
    updated_at: new Date(),
    sample_count: 0
  },
  {
    gesture_name: "goodbye",
    description: "Farewell gesture", 
    created_at: new Date(),
    updated_at: new Date(),
    sample_count: 0
  },
  {
    gesture_name: "thank_you",
    description: "Thank you gesture",
    created_at: new Date(),
    updated_at: new Date(),
    sample_count: 0
  }
]);

print("Sign Glove database initialized successfully!");
print("Collections created: gestures, sensor_data, training_results, audio_files, models");
print("Sample gestures inserted: hello, goodbye, thank_you"); 