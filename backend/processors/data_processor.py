"""
Data processing functions for reading and writing CSV files
"""
import csv
import os
import logging
from core.config import FLEX_SENSORS
from utils import normalize_data, row_validation
from noise_reducer import NoiseReducer

def read_data(file_path, use_noise_reduction=True, noise_config=None):
    """
    @effect: Hàm đọc dữ liệu từ file raw_data.csv, gửi lại dữ liệu chuẩn bị ghi vào file clean_data.csv
    @Args: 
        file_path: Đường dẫn đến file CSV cần đọc
        use_noise_reduction: Có sử dụng noise reduction không
        noise_config: Cấu hình cho noise reduction
    @return: Tuple chứa dữ liệu đã chuẩn hóa và header của file CSV
    @raise ValueError, IndexError: Nếu dữ liệu không hợp lệ hoặc không đủ cột
    @raise FileNotFoundError: Nếu file chưa được tạo
    """
    skipped_rows = 0
    data = []
    header = [] 
    noise_reducer = None
    
    if use_noise_reduction:
        config = noise_config or {}
        window_size = config.get('window_size', 3)
        outlier_threshold = config.get('outlier_threshold', 2.0)
        noise_reducer = NoiseReducer(window_size=window_size, outlier_threshold=outlier_threshold)
        logging.info(f"NoiseReducer initialized with window_size={window_size} and outlier_threshold={outlier_threshold}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found!")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Loại bỏ dòng cuối rỗng
            lines = file.readlines()
            while lines and not lines[-1].strip():
                lines.pop()
            
            if not lines:
                raise ValueError(f"File {file_path} is empty.")
            
            reader = csv.reader(lines)
            
            try:
                header = next(reader)  # Đọc header
            except StopIteration:
                raise ValueError(f"File {file_path} is empty or has no header.")
            
            # Số cột mong đợi từ header
            expected_col = len(header)
            
            for row_num, row in enumerate(reader, start=2):
                # Bỏ qua dòng cuối rỗng hoặc chỉ chứa whitespace
                if not row or all(not cell.strip() for cell in row):
                    continue
                
                # Kiểm tra tính hợp lệ của dòng
                is_valid, error_message = row_validation(row, expected_col, row_num)
                
                # Nếu không hợp lệ -> cảnh báo và bỏ qua data
                if not is_valid:
                    logging.warning(f"{error_message}")
                    skipped_rows += 1  
                    continue  # Skip dòng
                
                try:
                    values = [float(val.strip()) for val in row[:-1]]  # Chuyển đổi dữ liệu sang float và tránh label
                    label = row[-1].strip()  # Lấy label riêng
                    
                    if noise_reducer:
                        # Có thể tùy chỉnh filter nào được áp dụng
                        apply_moving_avg = noise_config.get('apply_moving_avg', True) if noise_config else True
                        apply_outlier = noise_config.get('apply_outlier', True) if noise_config else True
                        apply_median = noise_config.get('apply_median', False) if noise_config else False
                        
                        values = noise_reducer.apply_filters(
                            values, 
                            apply_moving_avg=apply_moving_avg,
                            apply_outlier=apply_outlier,
                            apply_median=apply_median
                        )
                    
                    data.append(values + [label])  # Thêm data và label vào dòng
                    
                except (ValueError, IndexError) as e:
                    logging.warning(f"Warning: Row {row_num} has invalid data format: {e}")
                    skipped_rows += 1
                    continue  # Bỏ qua dòng nếu có lỗi
                    
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        raise
    
    print("==================== Result ====================")
    print(f"Successfully read {len(data)} rows, skipped {skipped_rows} invalid rows.")
    
    if use_noise_reduction:
        print("Noise reduction filters applied:")
        if noise_config:
            print(f"  - Moving Average: {noise_config.get('apply_moving_avg', True)}")
            print(f"  - Outlier Detection: {noise_config.get('apply_outlier', True)}")
            print(f"  - Median Filter: {noise_config.get('apply_median', False)}")
        else:
            print("  - Moving Average: True")
            print("  - Outlier Detection: True")
            print("  - Median Filter: False")
    
    # Trả về dữ liệu sau chuẩn hóa cùng header
    return data, header

def write_data(file_path, data, header):
    """
    @effect: Hàm ghi dữ liệu đã chuẩn hóa vào file clean_data.csv
    @Args:
        file_path: Đường dẫn file output (clean_data.csv)
        data: Dữ liệu đã được xử lý
        header: Header của file CSV
    @return: True nếu ghi thành công, False nếu không có dữ liệu
    """
    if not data:
        logging.warning("No valid data to write!")
        return False
    
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(header)  # Ghi header vào đầu file
            
            rows = 0
            for row in data:
                val = row[:-1]
                label = row[-1]
                normalized_data = normalize_data(val)  # Chuẩn hóa dữ liệu
                writer.writerow(normalized_data + [label])
                rows += 1
            
            # In ra số dòng ghi thành công
            logging.info(f"Total {rows} rows written to {file_path}.")
            return True
            
    except Exception as e:
        logging.error(f"Error writing to file {file_path}: {e}")
        return False

def initialize_csv(file_path):
    """
    @effect: Khởi tạo file CSV với header nếu file chưa tồn tại
    @Args: file_path: Đường dẫn file cần khởi tạo
    @return: True nếu thành công, False nếu có lỗi
    """
    if os.path.exists(file_path):
        logging.info(f"File {file_path} already exists.")
        return True
    
    try:
        # Check thư mục nếu chưa tồn tại thì tạo
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:        
            writer = csv.writer(csvfile)
            # Ghi header
            header = [f'flexSensor{i + 1}' for i in range(FLEX_SENSORS)] + ['label']
            writer.writerow(header)
        
        logging.info(f"File {file_path} created with header.")
        return True
        
    except Exception as e:
        logging.error(f"Error creating file {file_path}: {e}")
        return False