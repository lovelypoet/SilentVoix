  # 🎯 ESP32 + SD Card TTS System for Sign Glove

This system is designed for **ESP32 + 32GB SD Card** architecture where TTS audio files are stored locally and played based on AI model predictions.

## 🏗️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Sign Glove    │    │     ESP32       │    │   Web Interface │
│   (Sensors)     │───▶│   + SD Card     │◄───│  (Language      │
│                 │    │   (32GB)        │    │   Selection)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Model      │
                       │  (TensorFlow    │
                       │   Lite)         │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   TTS Audio     │
                       │   (MP3/WAV)     │
                       │   from SD Card  │
                       └─────────────────┘
```

## 📁 **SD Card Structure**

```
/sd/
├── tts/
│   ├── en/                    # English TTS files
│   │   ├── hello.mp3
│   │   ├── yes.mp3
│   │   ├── no.mp3
│   │   └── ...
│   ├── vn/                    # Vietnamese TTS files
│   │   ├── xin_chao.mp3
│   │   ├── co.mp3
│   │   ├── khong.mp3
│   │   └── ...
│   └── fr/                    # French TTS files
│       ├── bonjour.mp3
│       ├── oui.mp3
│       ├── non.mp3
│       └── ...
└── ai_models/                 # AI model files
    ├── gesture_model.tflite
    └── gesture_model_dual.tflite
```

## 🌍 **Multi-Language Support**

### **English (en)**
- **Class 0**: Hello → `/sd/tts/en/hello.mp3`
- **Class 1**: Yes → `/sd/tts/en/yes.mp3`
- **Class 2**: No → `/sd/tts/en/no.mp3`
- **Class 3**: Thank you → `/sd/tts/en/thankyou.mp3`

### **Vietnamese (vn)**
- **Class 0**: Xin chào → `/sd/tts/vn/xin_chao.mp3`
- **Class 1**: Có → `/sd/tts/vn/co.mp3`
- **Class 2**: Không → `/sd/tts/vn/khong.mp3`
- **Class 3**: Cảm ơn → `/sd/tts/vn/cam_on.mp3`

### **French (fr)**
- **Class 0**: Bonjour → `/sd/tts/fr/bonjour.mp3`
- **Class 1**: Oui → `/sd/tts/fr/oui.mp3`
- **Class 2**: Non → `/sd/tts/fr/non.mp3`
- **Class 3**: Merci → `/sd/tts/fr/merci.mp3`

## 🔧 **How It Works**

### **1. Web Interface Language Selection**
- User selects language (EN/VN/FR) on web interface
- Language preference is sent to ESP32
- ESP32 loads corresponding TTS files from SD card

### **2. AI Model Training**
- AI model is trained with data in selected language
- Model learns gesture patterns for that language
- Training data is stored on SD card

### **3. Real-time Gesture Recognition**
- ESP32 receives sensor data from glove
- AI model predicts gesture class
- ESP32 plays corresponding TTS audio from SD card

### **4. TTS Audio Playback**
- Audio files are stored as MP3/WAV on SD card
- ESP32 plays audio through built-in speaker
- No internet required - completely offline

## 📡 **API Endpoints for ESP32 Integration**

### **Get TTS File Information**
```bash
GET /esp32/tts-info/{gesture_label}?language=en
```
Returns ESP32 file path and metadata for a specific gesture.

### **Get All TTS Files for Language**
```bash
GET /esp32/tts-files?language=vn
```
Returns all available TTS files for Vietnamese.

### **Get SD Card Structure**
```bash
GET /esp32/sd-structure
```
Returns recommended folder structure for SD card.

### **Generate TTS Files**
```bash
POST /esp32/generate-tts-files?language=fr
```
Generates TTS audio files for French language.

### **Get System Status**
```bash
GET /esp32/tts-status
```
Returns overall TTS system status and statistics.

## 🚀 **Setup Instructions**

### **1. Prepare SD Card**
```bash
# Format SD card as FAT32
# Create folder structure
mkdir -p /sd/tts/en
mkdir -p /sd/tts/vn
mkdir -p /sd/tts/fr
mkdir -p /sd/ai_models
```

### **2. Generate TTS Audio Files**
```bash
# Via API
curl -X POST "http://localhost:8080/esp32/generate-tts-files?language=en" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Download generated files and copy to SD card
```

### **3. Copy AI Models**
```bash
# Copy your trained models to SD card
cp gesture_model.tflite /sd/ai_models/
cp gesture_model_dual.tflite /sd/ai_models/
```

### **4. Configure ESP32**
```cpp
// ESP32 Arduino code
#include <SD.h>
#include <Audio.h>

// SD Card configuration
#define SD_CS 5
#define SD_MOSI 23
#define SD_MISO 19
#define SD_SCK 18

// Audio configuration
#define I2S_BCLK 26
#define I2S_LRC 25
#define I2S_DOUT 22

void setup() {
  // Initialize SD card
  if (!SD.begin(SD_CS, SD_MOSI, SD_MISO, SD_SCK)) {
    Serial.println("SD Card initialization failed!");
    return;
  }
  
  // Initialize audio
  audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
  audio.setVolume(21); // 0-21
}
```

## 💾 **ESP32 Code Examples**

### **Play TTS Audio from SD Card**
```cpp
void playTTS(const char* language, const char* gesture) {
  char filepath[64];
  snprintf(filepath, sizeof(filepath), "/sd/tts/%s/%s.mp3", language, gesture);
  
  if (SD.exists(filepath)) {
    audio.connecttoFS(SD, filepath);
    Serial.printf("Playing: %s\n", filepath);
  } else {
    Serial.printf("File not found: %s\n", filepath);
  }
}

// Usage examples
playTTS("en", "hello");      // Play English "Hello"
playTTS("vn", "xin_chao");   // Play Vietnamese "Xin chào"
playTTS("fr", "bonjour");    // Play French "Bonjour"
```

### **Language Selection via Web Interface**
```cpp
void handleLanguageSelection() {
  if (server.hasArg("language")) {
    String language = server.arg("language");
    if (language == "en" || language == "vn" || language == "fr") {
      currentLanguage = language;
      saveLanguagePreference();
      server.send(200, "text/plain", "Language set to " + language);
    }
  }
}
```

### **AI Model Loading from SD Card**
```cpp
void loadAIModel() {
  const char* modelPath = "/sd/ai_models/gesture_model.tflite";
  
  if (SD.exists(modelPath)) {
    // Load TensorFlow Lite model from SD card
    File modelFile = SD.open(modelPath);
    // ... model loading code ...
    Serial.println("AI Model loaded successfully");
  } else {
    Serial.println("AI Model not found on SD card");
  }
}
```

## ⚙️ **Configuration**

### **ESP32 Settings**
```json
{
  "esp32_config": {
    "sd_card": {
      "mount_point": "/sd",
      "tts_base_path": "/sd/tts",
      "max_file_size_mb": 5,
      "supported_formats": ["mp3", "wav"],
      "default_format": "mp3"
    },
    "audio_playback": {
      "volume": 100,
      "sample_rate": 16000,
      "bit_depth": 16,
      "channels": 1
    }
  }
}
```

### **Environment Variables**
```bash
# ESP32 Configuration
ESP32_IP=192.168.1.123
ESP32_SD_MOUNT=/sd
ESP32_TTS_BASE_PATH=/sd/tts

# TTS Configuration
TTS_ENABLED=true
TTS_FILTER_IDLE_GESTURES=true
TTS_CACHE_ENABLED=true
```

## 🧪 **Testing**

### **Test TTS File Generation**
```bash
cd backend
python test_selective_tts.py
```

### **Test ESP32 Integration**
```bash
# Test TTS file info
curl "http://localhost:8080/esp32/tts-info/Class%200?language=vn"

# Test SD structure
curl "http://localhost:8080/esp32/sd-structure"

# Test file generation
curl -X POST "http://localhost:8080/esp32/generate-tts-files?language=en" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🔍 **Troubleshooting**

### **SD Card Issues**
- Ensure SD card is formatted as FAT32
- Check SD card connections (CS, MOSI, MISO, SCK)
- Verify SD card is properly inserted

### **Audio Playback Issues**
- Check audio connections (BCLK, LRC, DOUT)
- Verify audio file format (MP3/WAV)
- Check audio volume settings

### **File Not Found Errors**
- Verify file paths match SD card structure
- Check file naming conventions
- Ensure files were copied correctly

### **Language Selection Issues**
- Verify language codes (en, vn, fr)
- Check web interface configuration
- Ensure TTS files exist for selected language

## 📊 **Performance Considerations**

### **SD Card Performance**
- Use Class 10 or higher SD card
- Keep file sizes under 5MB per audio file
- Use MP3 format for smaller file sizes

### **ESP32 Memory**
- Audio files are streamed from SD card
- Minimal RAM usage for audio playback
- Efficient file system access

### **Battery Life**
- SD card access is power-efficient
- Audio playback optimized for low power
- Sleep mode when not in use

## 🎯 **Benefits of This Architecture**

1. **Completely Offline** - No internet required
2. **Fast Response** - Local audio playback
3. **Multi-Language** - Easy language switching
4. **Scalable** - Add more languages easily
5. **Cost-Effective** - No cloud TTS costs
6. **Reliable** - No network dependency
7. **Customizable** - Easy to modify audio files

---

**🎉 Your ESP32 + SD Card TTS system is ready!** The glove will now play audio directly from the SD card based on AI model predictions, with full multi-language support and offline operation. 