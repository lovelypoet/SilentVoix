import math
import numpy as np
import logging

class IMUNormalizer:
    """
    Enhanced IMU preprocessing with gyroscope normalization
    """

    def __init__(self, alpha: float = 0.3, dt: float = 0.01):
        self.alpha = alpha
        self.dt = dt
        self.smoothed_roll = None
        self.smoothed_pitch = None
        self.smoothed_yaw = None
        self.yaw_prev = 0.0
        
        # Gyroscope normalization parameters
        self.gyro_stats = {
            'gx': {'mean': 0, 'std': 1, 'min': -500, 'max': 500},
            'gy': {'mean': 0, 'std': 1, 'min': -500, 'max': 500},
            'gz': {'mean': 0, 'std': 1, 'min': -500, 'max': 500}
        }
        self.gyro_calibration_samples = []
        self.gyro_calibrated = False
        self.calibration_samples_needed = 100

    def calibrate_gyro(self, gx: float, gy: float, gz: float):
        """Collect samples for gyroscope calibration"""
        self.gyro_calibration_samples.append((gx, gy, gz))
        
        if len(self.gyro_calibration_samples) >= self.calibration_samples_needed:
            # Calculate statistics
            samples = np.array(self.gyro_calibration_samples)
            
            self.gyro_stats['gx']['mean'] = np.mean(samples[:, 0])
            self.gyro_stats['gy']['mean'] = np.mean(samples[:, 1])
            self.gyro_stats['gz']['mean'] = np.mean(samples[:, 2])
            
            self.gyro_stats['gx']['std'] = np.std(samples[:, 0]) or 1.0
            self.gyro_stats['gy']['std'] = np.std(samples[:, 1]) or 1.0
            self.gyro_stats['gz']['std'] = np.std(samples[:, 2]) or 1.0
            
            # For min-max scaling (alternative approach)
            self.gyro_stats['gx']['min'] = np.min(samples[:, 0])
            self.gyro_stats['gx']['max'] = np.max(samples[:, 0])
            self.gyro_stats['gy']['min'] = np.min(samples[:, 1])
            self.gyro_stats['gy']['max'] = np.max(samples[:, 1])
            self.gyro_stats['gz']['min'] = np.min(samples[:, 2])
            self.gyro_stats['gz']['max'] = np.max(samples[:, 2])
            
            self.gyro_calibrated = True
            logging.info(f"Gyroscope calibration completed with {len(self.gyro_calibration_samples)} samples")

    def normalize_gyro(self, gx: float, gy: float, gz: float):
        """Normalize gyroscope data using z-score normalization"""
        if not self.gyro_calibrated:
            return gx, gy, gz
            
        gx_norm = (gx - self.gyro_stats['gx']['mean']) / self.gyro_stats['gx']['std']
        gy_norm = (gy - self.gyro_stats['gy']['mean']) / self.gyro_stats['gy']['std']
        gz_norm = (gz - self.gyro_stats['gz']['mean']) / self.gyro_stats['gz']['std']
        
        return gx_norm, gy_norm, gz_norm

    def normalize_gyro_minmax(self, gx: float, gy: float, gz: float):
        """Alternative: Min-max scaling to [-1, 1]"""
        if not self.gyro_calibrated:
            return gx, gy, gz
            
        gx_range = self.gyro_stats['gx']['max'] - self.gyro_stats['gx']['min']
        gy_range = self.gyro_stats['gy']['max'] - self.gyro_stats['gy']['min']
        gz_range = self.gyro_stats['gz']['max'] - self.gyro_stats['gz']['min']
        
        gx_norm = 2 * (gx - self.gyro_stats['gx']['min']) / gx_range - 1 if gx_range > 0 else 0
        gy_norm = 2 * (gy - self.gyro_stats['gy']['min']) / gy_range - 1 if gy_range > 0 else 0
        gz_norm = 2 * (gz - self.gyro_stats['gz']['min']) / gz_range - 1 if gz_range > 0 else 0
        
        return gx_norm, gy_norm, gz_norm

    def compute_roll_pitch(self, ax: float, ay: float, az: float):
        """Compute roll & pitch in degrees from accelerometer"""
        roll  = math.atan2(ay, az) * 180.0 / math.pi
        pitch = math.atan2(-ax, math.sqrt(ay*ay + az*az)) * 180.0 / math.pi
        return roll, pitch

    def compute_yaw(self, gz: float):
        """Integrate gyro z-axis to get yaw (degrees)"""
        self.yaw_prev += gz * self.dt
        return self.yaw_prev

    def smooth(self, roll: float, pitch: float, yaw: float):
        """Exponential smoothing"""
        if self.smoothed_roll is None:
            self.smoothed_roll = roll
            self.smoothed_pitch = pitch
            self.smoothed_yaw = yaw
        else:
            self.smoothed_roll  = self.alpha*roll + (1-self.alpha)*self.smoothed_roll
            self.smoothed_pitch = self.alpha*pitch + (1-self.alpha)*self.smoothed_pitch
            self.smoothed_yaw   = self.alpha*yaw + (1-self.alpha)*self.smoothed_yaw
        return self.smoothed_roll, self.smoothed_pitch, self.smoothed_yaw

    def normalize(self, roll: float, pitch: float, yaw: float):
        """Normalize all angles to [-1,1]"""
        roll_n  = max(-180, min(180, roll)) / 180.0
        pitch_n = max(-180, min(180, pitch)) / 180.0
        yaw_n   = max(-180, min(180, yaw)) / 180.0
        return roll_n, pitch_n, yaw_n

    def process(self, ax: float, ay: float, az: float, gz: float):
        """Full pipeline: compute → smooth → normalize"""
        roll, pitch = self.compute_roll_pitch(ax, ay, az)
        yaw = self.compute_yaw(gz)
        roll, pitch, yaw = self.smooth(roll, pitch, yaw)
        return self.normalize(roll, pitch, yaw)
