"""
Regularization for Sign Glove 11-Feature Pipeline
- 5 flex sensors + 3 IMU angles (roll/pitch/yaw) + 3 gyroscope axes (gx, gy, gz)
- Includes: Kalman, Weighted Moving Average, Exponential Smoothing, Adaptive
- Uses enhanced IMUNormalizer with gyroscope normalization
"""

import logging
import csv
import os
from collections import deque
from typing import List, Dict, Optional
import math
import numpy as np
from processors.imu_normalizer import IMUNormalizer

# Initialize global IMU normalizer (using your enhanced class)
imu_norm = IMUNormalizer()

class RegularizationAlgorithms:
    """Regularization algorithms for flex sensors and IMU"""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.sensor_states = {}
        self.buffers = {}
        self.imu_norm = IMUNormalizer() 

    def reset_states(self):
        self.sensor_states.clear()
        self.buffers.clear()
        logging.info("All regularization states reset")

    def simple_kalman_filter(self, measurement: float, sensor_id: str) -> float:
        if sensor_id not in self.sensor_states:
            self.sensor_states[sensor_id] = {
                'estimate': measurement,
                'error': 1.0,
                'process_noise': 0.01,
                'measurement_noise': 0.1
            }
            return measurement
        state = self.sensor_states[sensor_id]
        predicted_error = state['error'] + state['process_noise']
        kalman_gain = predicted_error / (predicted_error + state['measurement_noise'])
        state['estimate'] += kalman_gain * (measurement - state['estimate'])
        state['error'] = (1 - kalman_gain) * predicted_error
        return state['estimate']

    def weighted_moving_average(self, measurement: float, sensor_id: str) -> float:
        buffer_key = f"wma_{sensor_id}"
        if buffer_key not in self.buffers:
            self.buffers[buffer_key] = deque(maxlen=self.window_size)
        buffer = self.buffers[buffer_key]
        buffer.append(measurement)
        if len(buffer) == 1:
            return measurement
        weights = [i + 1 for i in range(len(buffer))]
        return sum(buffer[i]*weights[i] for i in range(len(buffer))) / sum(weights)

    def exponential_smoothing(self, measurement: float, sensor_id: str, alpha: float = 0.3) -> float:
        if sensor_id not in self.sensor_states:
            self.sensor_states[sensor_id] = {'smoothed_value': measurement}
            return measurement
        state = self.sensor_states[sensor_id]
        state['smoothed_value'] = alpha*measurement + (1-alpha)*state['smoothed_value']
        return state['smoothed_value']

    def apply_single_algorithm(self, data: List[float], algorithm: str = "kalman") -> List[float]:
        regularized_data = []
        for i, value in enumerate(data):
            sensor_id = f"sensor_{i}"
            if algorithm == "kalman":
                result = self.simple_kalman_filter(value, sensor_id)
            elif algorithm == "weighted":
                result = self.weighted_moving_average(value, sensor_id)
            elif algorithm == "exponential":
                result = self.exponential_smoothing(value, sensor_id)
            else:
                result = self.simple_kalman_filter(value, sensor_id)
            regularized_data.append(result)
        return regularized_data

    def apply_combined_regularization(self, data: List[float],
                                      algorithm_weights: Optional[Dict[str, float]] = None) -> List[float]:
        if algorithm_weights is None:
            algorithm_weights = {'kalman':0.5, 'weighted':0.3, 'exponential':0.2}
        total_weight = sum(algorithm_weights.values())
        for key in algorithm_weights:
            algorithm_weights[key] /= total_weight
        regularized_data = []
        for i, value in enumerate(data):
            sensor_id = f"sensor_{i}"
            kalman_result = self.simple_kalman_filter(value, f"kalman_{sensor_id}")
            weighted_result = self.weighted_moving_average(value, f"weighted_{sensor_id}")
            exp_result = self.exponential_smoothing(value, f"exp_{sensor_id}")
            combined = (algorithm_weights['kalman']*kalman_result +
                        algorithm_weights['weighted']*weighted_result +
                        algorithm_weights['exponential']*exp_result)
            regularized_data.append(combined)
        return regularized_data

    def apply_adaptive_regularization(self, data: List[float]) -> List[float]:
        if len(data) < 3:
            return data
        variance = sum((x - sum(data)/len(data))**2 for x in data)/len(data)
        if variance > 1.0:
            weights = {'kalman':0.7, 'weighted':0.2, 'exponential':0.1}
        elif variance > 0.1:
            weights = {'kalman':0.3, 'weighted':0.5, 'exponential':0.2}
        else:
            weights = {'kalman':0.2, 'weighted':0.3, 'exponential':0.5}
        return self.apply_combined_regularization(data, weights)

    def process_csv_file(self, input_path: str, output_path: str, method: str = "adaptive") -> int:
        if not os.path.exists(input_path):
            logging.error(f"Input file not found: {input_path}")
            return 0
        self.reset_states()
        row_count = 0
        
        # Reset IMU normalizer for new file processing
        imu_norm.gyro_calibrated = False
        imu_norm.gyro_calibration_samples = []
        
        with open(input_path,'r',newline='',encoding='utf-8') as infile, \
             open(output_path,'w',newline='',encoding='utf-8') as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            header = next(reader)
            writer.writerow(header[:2]+['f1','f2','f3','f4','f5',
                                        'roll','pitch','yaw','gx','gy','gz'])
            
            calibration_mode = True
            
            for row in reader:
                if len(row) < 11:
                    continue
                session_id,label,*sensor_values = row
                try:
                    flex_values = list(map(float, sensor_values[:5]))
                    ax, ay, az = map(float, sensor_values[5:8])
                    gx, gy, gz = map(float, sensor_values[8:11])
                except ValueError:
                    continue
                    
                # CALIBRATION PHASE - Collect gyro samples without processing
                if calibration_mode:
                    imu_norm.calibrate_gyro(gx, gy, gz)
                    if not imu_norm.gyro_calibrated:
                        # Still calibrating, skip processing
                        continue
                    else:
                        # Calibration complete, switch to processing mode
                        calibration_mode = False
                        logging.info("Gyroscope calibration complete, starting data processing")
                        continue  # Process this sample in next iteration
                        
                # REGULAR PROCESSING - Only reached after calibration
                # Regularize flex sensors
                if method == "adaptive":
                    flex_reg = self.apply_adaptive_regularization(flex_values)
                elif method == "combined":
                    flex_reg = self.apply_combined_regularization(flex_values)
                else:
                    flex_reg = self.apply_single_algorithm(flex_values, method)
                    
                # Process IMU data (roll, pitch, yaw)
                roll, pitch, yaw = imu_norm.process(ax, ay, az, gz)
                
                # Apply additional smoothing to IMU angles
                roll = self.exponential_smoothing(roll, 'roll')
                pitch = self.exponential_smoothing(pitch, 'pitch')
                yaw = self.exponential_smoothing(yaw, 'yaw')
                
                # NORMALIZE GYROSCOPE DATA (the key addition)
                gx_norm, gy_norm, gz_norm = imu_norm.normalize_gyro(gx, gy, gz)
                
                writer.writerow([session_id,label]+[round(f,3) for f in flex_reg]+
                                [round(roll,3), round(pitch,3), round(yaw,3),
                                 round(gx_norm,3), round(gy_norm,3), round(gz_norm,3)])
                row_count += 1
                
        logging.info(f"Processed {row_count} rows from {input_path} -> {output_path}")
        return row_count

# ------------------- HELPER -------------------
def create_regularizer(window_size: int = 5) -> RegularizationAlgorithms:
    return RegularizationAlgorithms(window_size)

# ------------------- MAIN -------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    regularizer = create_regularizer()
    input_file = r'D:\study\output\sign-glove\backend\data\raw_data.csv'
    output_file = r'D:\study\output\sign-glove\backend\data\clean_data.csv'
    print(f"Processing {input_file} ...")
    rows = regularizer.process_csv_file(input_file, output_file, method='adaptive')
    print(f"Done! Processed {rows} rows. Output saved to {output_file}")