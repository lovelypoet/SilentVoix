#include <Wire.h>

#define MPU_ADDR 0x68
#define SDA_PIN 11 // Nhớ cắm đúng SDA vào 11, SCL vào 10 nhé
#define SCL_PIN 10

// ===== MPU RAW =====
int16_t ax_raw, ay_raw, az_raw;
int16_t gx_raw, gy_raw, gz_raw;

// ===== Converted =====
float ax, ay, az;
float gx, gy, gz;

// ===== Offset =====
float ax_offset=0, ay_offset=0, az_offset=0;
float gx_offset=0, gy_offset=0, gz_offset=0;

// ===== Filtered =====
float ax_f, ay_f, az_f;
float gx_f, gy_f, gz_f;
float alpha = 0.8;   // Low-pass filter strength

// ===== FLEX =====
const int flexPins[5] = {4, 5, 6, 2, 8};
int flexRaw[5];
float flexNorm[5];

// Đặt giới hạn ngược để dễ tìm Min/Max thực tế
int flexMin[5] = {4095, 4095, 4095, 4095, 4095};
int flexMax[5] = {0, 0, 0, 0, 0};

unsigned long lastTime = 0;
const int sampleRate = 50;
const int interval = 1000 / sampleRate;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  // Wake MPU
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission(true);

  analogReadResolution(12);

  // 1. Calibrate MPU (YÊU CẦU: ĐẶT TAY PHẲNG XUỐNG BÀN, KHÔNG NHÚC NHÍCH)
  Serial.println("Calibrating MPU... PLEASE KEEP HAND FLAT AND STILL!");
  calibrateMPU();
  
  // 2. Calibrate Flex (YÊU CẦU: NẮM VÀ MỞ BÀN TAY LIÊN TỤC TRONG 5 GIÂY)
  Serial.println("Calibrating Flex... OPEN AND CLOSE HAND FULLY FOR 5 SECONDS!");
  calibrateFlex();

  // 3. Mồi giá trị ban đầu cho bộ lọc Low-pass để tránh bị giật lag
  readMPU();
  ax_f = (ax_raw - ax_offset) / 16384.0;
  ay_f = (ay_raw - ay_offset) / 16384.0;
  az_f = (az_raw - az_offset) / 16384.0;
  gx_f = (gx_raw - gx_offset) / 131.0;
  gy_f = (gy_raw - gy_offset) / 131.0;
  gz_f = (gz_raw - gz_offset) / 131.0;

  Serial.println("READY! timestamp,ax,ay,az,gx,gy,gz,f1,f2,f3,f4,f5");
  lastTime = millis();
}

void calibrateMPU() {
  int samples = 500;
  for(int i = 0; i < samples; i++){
    readMPU();
    ax_offset += ax_raw;
    ay_offset += ay_raw;
    az_offset += az_raw - 16384; // Giả sử tay để phẳng, Z chịu 1g = 16384
    gx_offset += gx_raw;
    gy_offset += gy_raw;
    gz_offset += gz_raw;
    delay(5);
  }
  ax_offset /= samples; ay_offset /= samples; az_offset /= samples;
  gx_offset /= samples; gy_offset /= samples; gz_offset /= samples;
}

void calibrateFlex() {
  unsigned long startCalib = millis();
  // Cho người dùng 5 giây để đóng mở tay liên tục
  while(millis() - startCalib < 5000) {
    for(int i = 0; i < 5; i++){
      int val = analogRead(flexPins[i]);
      if(val < flexMin[i]) flexMin[i] = val;
      if(val > flexMax[i]) flexMax[i] = val;
    }
    delay(10);
  }
  Serial.println("Flex Calibration Done!");
}

void readMPU() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14, true);

  ax_raw = Wire.read()<<8 | Wire.read();
  ay_raw = Wire.read()<<8 | Wire.read();
  az_raw = Wire.read()<<8 | Wire.read();
  Wire.read(); Wire.read(); // Skip temp
  gx_raw = Wire.read()<<8 | Wire.read();
  gy_raw = Wire.read()<<8 | Wire.read();
  gz_raw = Wire.read()<<8 | Wire.read();
}

void loop() {
  // Sửa lỗi trôi thời gian (drift): Cộng dồn interval thay vì gán bằng millis()
  if (millis() - lastTime >= interval) {
    lastTime += interval; 

    readMPU();

    // ===== REMOVE OFFSET =====
    ax = (ax_raw - ax_offset) / 16384.0;
    ay = (ay_raw - ay_offset) / 16384.0;
    az = (az_raw - az_offset) / 16384.0;

    gx = (gx_raw - gx_offset) / 131.0;
    gy = (gy_raw - gy_offset) / 131.0;
    gz = (gz_raw - gz_offset) / 131.0;

    // ===== LOW PASS FILTER =====
    ax_f = alpha * ax_f + (1.0 - alpha) * ax;
    ay_f = alpha * ay_f + (1.0 - alpha) * ay;
    az_f = alpha * az_f + (1.0 - alpha) * az;

    gx_f = alpha * gx_f + (1.0 - alpha) * gx;
    gy_f = alpha * gy_f + (1.0 - alpha) * gy;
    gz_f = alpha * gz_f + (1.0 - alpha) * gz;

    // ===== FLEX NORMALIZE (Fixed Min/Max) =====
    for(int i = 0; i < 5; i++){
      flexRaw[i] = analogRead(flexPins[i]);
      // Ràng buộc giá trị không vượt quá giới hạn đã calibrate
      int constrainedVal = constrain(flexRaw[i], flexMin[i], flexMax[i]);
      
      if(flexMax[i] - flexMin[i] != 0) {
        flexNorm[i] = (float)(constrainedVal - flexMin[i]) / (flexMax[i] - flexMin[i]);
      } else {
        flexNorm[i] = 0;
      }
    }

    // ===== PRINT CLEAN DATA =====
    Serial.print(millis()); Serial.print(",");
    Serial.print(ax_f); Serial.print(",");
    Serial.print(ay_f); Serial.print(",");
    Serial.print(az_f); Serial.print(",");
    Serial.print(gx_f); Serial.print(",");
    Serial.print(gy_f); Serial.print(",");
    Serial.print(gz_f); Serial.print(",");
    
    for(int i=0; i<5; i++){
      Serial.print(flexNorm[i], 3); // Giới hạn in ra 3 số thập phân cho gọn
      if(i<4) Serial.print(",");
    }
    Serial.println();
  }
}
