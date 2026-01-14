# 🎯 Selective TTS System for Sign Glove (Multi-Language)

This system provides **selective Text-to-Speech** that only speaks for meaningful gestures and avoids speaking for basic actions like hand resting or idle movements. **Your AI model remains fully active and intelligent!**

## ✨ What's New

### Before (Old System)
- TTS spoke for **every** recognized gesture
- No distinction between meaningful and idle gestures
- Constant audio feedback for all movements
- Single language support

### After (New System)
- TTS **only speaks for meaningful gestures**
- **Silent for idle movements** (hand resting, basic movements)
- **Multi-language support** (English, Vietnamese, French)
- **Configurable gesture mapping** for different sign languages
- **Smart filtering** to avoid unnecessary speech

## 🧠 **Your AI Model is NOT Replaced - It's Enhanced!**

### **What Your AI Model Still Does:**
- ✅ **Recognizes and classifies gestures** from sensor data
- ✅ **Learns from training data** (English, Vietnamese, French)
- ✅ **Adapts to different users** and hand sizes
- ✅ **Improves accuracy** over time with more data
- ✅ **Handles complex gestures** and expressions

### **What My TTS Filter Adds:**
- 🎯 **Only decides WHEN to speak** (not WHAT to recognize)
- 🎯 **Acts as a "smart speaker controller"** for your model's output
- 🎯 **Doesn't interfere with gesture recognition** at all

## 🔄 **How It Actually Works:**

```
Sensor Data → Your AI Model → Gesture Classification → TTS Filter → Speaker
     ↓              ↓              ↓              ↓         ↓
  Flex/IMU    TensorFlow Lite   "Class 0"    Should speak?   "Hello"
  Sensors      Neural Network    "Hello"      YES/NO          (or silent)
```

### **Example Flow:**
1. **Your model** recognizes "Class 0" from sensor data
2. **TTS filter** checks: "Is this meaningful enough to speak?"
3. **If YES** → Speaker says "Hello" (or "Xin chào" in Vietnamese)
4. **If NO** → Silent (for idle movements)

## 🌍 **Multi-Language Support**

### **Supported Languages:**
- **English (en)**: Hello, Yes, No, Thank you, Please, Sorry, Goodbye, Help, Water, Food, Emergency
- **Vietnamese (vn)**: Xin chào, Có, Không, Cảm ơn, Làm ơn, Xin lỗi, Tạm biệt, Giúp đỡ, Nước, Thức ăn, Khẩn cấp
- **French (fr)**: Bonjour, Oui, Non, Merci, S'il vous plaît, Désolé, Au revoir, Aide, Eau, Nourriture, Urgence

### **Language Switching:**
```python
# Set language dynamically
tts_service.set_language("vn")  # Switch to Vietnamese
tts_service.set_language("fr")  # Switch to French
tts_service.set_language("en")  # Switch to English
```

## 🚀 **How It Works**

### 1. Gesture Classification
The system now classifies gestures into two categories:

**✅ Meaningful Gestures (Trigger TTS):**
- Hello, Yes, No, Thank you
- Please, Sorry, Goodbye
- Help, Water, Food, Emergency

**⏭️ Idle Gestures (No TTS):**
- Hand resting/idle positions
- Basic hand movements
- Undefined or unknown gestures

### 2. Smart Filtering
```python
# Only meaningful gestures trigger speech
if tts_service.should_speak_gesture(gesture_label):
    await tts_service.speak_gesture(gesture_label, language="vn")
else:
    # Silent - no TTS for idle gestures
    pass
```

## ⚙️ Configuration

### Environment Variables
```bash
# Enable/disable TTS filtering
TTS_FILTER_IDLE_GESTURES=true

# Other TTS settings
TTS_ENABLED=true
TTS_PROVIDER=edge
TTS_VOICE=ur-IN-SalmanNeural
TTS_RATE=150
TTS_VOLUME=2.0
```

### Gesture Mapping
Edit `tts_config.json` to customize which gestures trigger speech in different languages:

```json
{
  "gesture_mapping": {
    "Class 0": "Hello",
    "Class 1": "Yes",
    "Class 2": "No",
    "Class 3": "Thank you"
  }
}
```

## 🧪 Testing

### Run the Test Script
```bash
cd backend
python test_selective_tts.py
```

### Test via API
```bash
# Get TTS configuration
curl -X GET "http://localhost:8080/utils/tts/config" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test TTS for a specific gesture in Vietnamese
curl -X POST "http://localhost:8080/utils/tts/test-gesture" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"gesture_label": "Class 0", "language": "vn"}'

# Test TTS in all languages
curl -X POST "http://localhost:8080/utils/tts/test-multilingual" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"gesture_label": "Class 0"}'

# Set language
curl -X POST "http://localhost:8080/utils/tts/language" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '"vn"'
```

## 🔧 Customization

### Add New Languages
1. Update `LANGUAGE_MAPPINGS` in `tts_service.py`
2. Add gesture translations for the new language
3. Restart the backend service

### Add New Meaningful Gestures
1. Update `tts_config.json`
2. Add to `LANGUAGE_MAPPINGS` in `tts_service.py`
3. Restart the backend service

### Modify Idle Gesture Detection
Edit the `IDLE_GESTURES` dictionary in `tts_service.py`:

```python
IDLE_GESTURES = {
    "hand_resting": ["rest", "idle", "neutral", "relaxed"],
    "basic_movement": ["movement", "wave", "point"],
    "no_meaning": ["", "none", "unknown"]
}
```

### Disable Filtering (Legacy Mode)
Set `TTS_FILTER_IDLE_GESTURES=false` to restore the old behavior where all gestures trigger TTS.

## 📊 Monitoring

### Log Messages
The system now logs TTS decisions with language information:

```
INFO: TTS spoke 'Xin chào' for gesture 'Class 0' in vn
INFO: TTS skipped for gesture 'hand_resting' in en: Gesture is idle/basic - no TTS needed
WARNING: TTS error for gesture 'Class 99' in fr: No meaningful text for gesture
```

### API Endpoints
- `GET /utils/tts/config` - View current TTS configuration
- `GET /utils/tts/languages` - Get available languages
- `POST /utils/tts/language` - Set current language
- `POST /utils/tts/test-gesture` - Test TTS for specific gestures
- `POST /utils/tts/test-multilingual` - Test TTS in all languages
- `POST /utils/tts/gesture-mapping` - Update gesture mapping

## 🎯 Benefits

1. **Reduced Audio Noise** - No more constant speech for idle movements
2. **Better User Experience** - TTS only when meaningful information is conveyed
3. **Multi-Language Support** - Works with English, Vietnamese, French
4. **Configurable** - Easy to adapt for different sign languages
5. **Battery Efficient** - Less unnecessary audio processing
6. **Professional Feel** - More polished and intentional communication
7. **AI Model Preserved** - Your neural network remains fully functional

## 🔄 Migration

### From Old System
1. The new system is **backward compatible**
2. Set `TTS_FILTER_IDLE_GESTURES=false` to restore old behavior
3. Gradually customize gesture mapping for your needs

### To New System
1. Update your `.env` file with new TTS settings
2. Customize `tts_config.json` for your gesture set
3. Test with `test_selective_tts.py`
4. Monitor logs to ensure proper filtering

## 🆘 Troubleshooting

### TTS Not Speaking
- Check `TTS_ENABLED=true`
- Verify gesture is in `LANGUAGE_MAPPINGS`
- Check logs for "TTS skipped" messages
- Verify language is set correctly

### Too Much TTS
- Set `TTS_FILTER_IDLE_GESTURES=true`
- Review `IDLE_GESTURES` configuration
- Add more gestures to idle categories

### Custom Gestures Not Working
- Update both `tts_config.json` and `LANGUAGE_MAPPINGS`
- Restart the backend service
- Check API responses for errors

### Language Issues
- Verify language code is supported (`en`, `vn`, `fr`)
- Check if gesture has translation in that language
- Use `GET /utils/tts/languages` to see available options

## 🤖 **AI Model Integration Summary**

**Your AI Model:**
- ✅ **Still does ALL gesture recognition**
- ✅ **Still learns and improves**
- ✅ **Still handles complex patterns**
- ✅ **Still adapts to users**

**TTS System:**
- 🎯 **Only decides WHEN to speak**
- 🎯 **Adds multi-language support**
- 🎯 **Filters out idle movements**
- 🎯 **Makes communication more professional**

---

**🎉 Enjoy your enhanced sign glove system!** The glove will now only speak when it has something meaningful to say, in multiple languages, while preserving all the intelligence of your AI model. 