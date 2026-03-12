import serial
import csv
import time
import os

# --- CẤU HÌNH ---
PORT = '/dev/ttyACM0'  # Nhớ đổi lại đúng cổng trên máy Linux của cậu nhé
BAUD = 115200
NUM_SAMPLES = 100      # Thu 100 mẫu mỗi lần (100 * 20ms = 2 giây dữ liệu cho 1 cử chỉ)
FILE_NAME = 'glove_dataset.csv'

# 1. Nhập nhãn (Label)
label = input("👉 Nhập tên cử chỉ bạn chuẩn bị làm (VD: A, B, C): ").strip().upper()

print(f"\n⏳ Chuẩn bị tư thế tay cho chữ '{label}'. Bắt đầu thu thập sau 3 giây...")
for i in range(3, 0, -1):
    print(f"{i}...")
    time.sleep(1)

# 2. Mở kết nối Serial
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    ser.reset_input_buffer() # Xóa rác đọng trong buffer
except Exception as e:
    print(f"❌ Không mở được cổng {PORT}. Lỗi: {e}")
    exit()

# Kiểm tra file đã tồn tại chưa
file_exists = os.path.isfile(FILE_NAME)

# 3. Mở file CSV để nối dữ liệu (Append mode)
with open(FILE_NAME, 'a', newline='') as f:
    writer = csv.writer(f)
    
    # Ghi Header nếu là file mới (Thêm timestamp_ms lên đầu)
    if not file_exists:
        header = ['timestamp_ms', 'ax', 'ay', 'az', 'gx', 'gy', 'gz', 'f1', 'f2', 'f3', 'f4', 'f5', 'label']
        writer.writerow(header)

    print("\n🔴 ĐANG GHI DỮ LIỆU... GIỮ NGUYÊN TƯ THẾ NHÉ!")
    
    count = 0
    while count < NUM_SAMPLES:
        try:
            line = ser.readline().decode('utf-8').strip()
            
            # BỎ QUA CÁC DÒNG RÁC: Dòng rỗng, chữ Calibrating, hoặc dòng Header in từ Arduino
            if not line or any(word in line for word in ["Calibrating", "READY", "timestamp"]):
                continue
                
            row = line.split(',')
            
            # CHỈ NHẬN KHI ĐỦ 12 CỘT TỪ ARDUINO
            if len(row) == 12:
                row.append(label) # Thêm Label vào làm cột thứ 13
                writer.writerow(row)
                count += 1
                
                # In log tiến độ cho đỡ chán
                if count % 20 == 0:
                    print(f"   Đã thu được {count}/{NUM_SAMPLES} mẫu...")
            else:
                pass # Dòng nào bị vấp, đứt đoạn (ít hơn 12 cột) thì bỏ qua luôn

        except UnicodeDecodeError:
            pass # Lâu lâu Serial nó bắn ra ký tự lạ thì bỏ qua cho khỏi crash code
            
print(f"\n✅ XONG! Đã lưu thành công {NUM_SAMPLES} mẫu của chữ '{label}' vào file {FILE_NAME}.")
ser.close()