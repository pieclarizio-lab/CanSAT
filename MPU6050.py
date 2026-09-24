from math import sqrt, atan2
from time import sleep_ms

error_msg = "\nError \n"
i2c_err_str = "Impossibile comunicare con il modulo all'indirizzo 0x{:02X}, controlla i cavi SDA e SCL"

# Global Variables
_GRAVITIY_MS2 = 9.80665

# Scale Modifiers
_ACC_SCLR_2G = 16384.0
_ACC_SCLR_4G = 8192.0
_ACC_SCLR_8G = 4096.0
_ACC_SCLR_16G = 2048.0

_GYR_SCLR_250DEG = 131.0
_GYR_SCLR_500DEG = 65.5
_GYR_SCLR_1000DEG = 32.8
_GYR_SCLR_2000DEG = 16.4

# Pre-defined ranges
_ACC_RNG_2G = 0x00
_ACC_RNG_4G = 0x08
_ACC_RNG_8G = 0x10
_ACC_RNG_16G = 0x18

_GYR_RNG_250DEG = 0x00
_GYR_RNG_500DEG = 0x08
_GYR_RNG_1000DEG = 0x10
_GYR_RNG_2000DEG = 0x18

# MPU-6050 Registers
_PWR_MGMT_1 = 0x6B
_ACCEL_XOUT0 = 0x3B
_TEMP_OUT0 = 0x41
_GYRO_XOUT0 = 0x43
_ACCEL_CONFIG = 0x1C
_GYRO_CONFIG = 0x1B

_maxFails = 3
_MPU6050_ADDRESS = 0x68

# CORREZIONE 1: Rimosso l'argomento dinamico 'endian'
def signedIntFromBytes(x):
    y = int.from_bytes(x, 'big')
    if (y >= 0x8000):
        return -((65535 - y) + 1)
    else:
        return y


class MPU6050(object):
    # CORREZIONE 2: Ora accetta direttamente il tuo oggetto I2C
    def __init__(self, i2c, addr=_MPU6050_ADDRESS):
        self._failCount = 0
        self._terminatingFailCount = 0

        # --- OFFSET PERSONALI CALIBRATI ---
        self.offset_x = -0.0
        self.offset_y = -0.0
        self.offset_z = -0.0
        # -----------------------------------------

        self.i2c = i2c
        self.addr = addr
        try:
            # Sveglia il sensore
            self.i2c.writeto_mem(self.addr, _PWR_MGMT_1, bytes([0x00]))
            sleep_ms(5)
        except Exception as e:
            print(i2c_err_str.format(self.addr))
            print(error_msg)
            raise e

        self._accel_range = self.get_accel_range(True)
        self._gyro_range = self.get_gyro_range(True)

    def _readData(self, register):
        failCount = 0
        while failCount < _maxFails:
            try:
                sleep_ms(10)
                data = self.i2c.readfrom_mem(self.addr, register, 6)
                break
            except Exception:
                failCount = failCount + 1
                self._failCount = self._failCount + 1
                if failCount >= _maxFails:
                    self._terminatingFailCount = self._terminatingFailCount + 1
                    print(i2c_err_str.format(self.addr))
                    return {"x": float("NaN"), "y": float("NaN"), "z": float("NaN")}

        x = signedIntFromBytes(data[0:2])
        y = signedIntFromBytes(data[2:4])
        z = signedIntFromBytes(data[4:6])
        return {"x": x, "y": y, "z": z}

    def read_temperature(self):
        try:
            rawData = self.i2c.readfrom_mem(self.addr, _TEMP_OUT0, 2)
            raw_temp = signedIntFromBytes(rawData)
        except Exception:
            print(i2c_err_str.format(self.addr))
            return float("NaN")
        actual_temp = (raw_temp / 340) + 36.53
        return actual_temp

    def set_accel_range(self, accel_range):
        self.i2c.writeto_mem(self.addr, _ACCEL_CONFIG, bytes([accel_range]))
        self._accel_range = accel_range

    def get_accel_range(self, raw = False):
        raw_data = self.i2c.readfrom_mem(self.addr, _ACCEL_CONFIG, 2)
        if raw is True:
            return raw_data[0]
        else:
            if raw_data[0] == _ACC_RNG_2G: return 2
            elif raw_data[0] == _ACC_RNG_4G: return 4
            elif raw_data[0] == _ACC_RNG_8G: return 8
            elif raw_data[0] == _ACC_RNG_16G: return 16
            else: return -1

    def read_accel_data(self, g = False):
        accel_data = self._readData(_ACCEL_XOUT0)
        accel_range = self._accel_range
        scaler = None

        if accel_range == _ACC_RNG_2G: scaler = _ACC_SCLR_2G
        elif accel_range == _ACC_RNG_4G: scaler = _ACC_SCLR_4G
        elif accel_range == _ACC_RNG_8G: scaler = _ACC_SCLR_8G
        elif accel_range == _ACC_RNG_16G: scaler = _ACC_SCLR_16G
        else:
            print("Unkown range - scaler set to _ACC_SCLR_2G")
            scaler = _ACC_SCLR_2G

        x = accel_data["x"] / scaler
        y = accel_data["y"] / scaler
        z = accel_data["z"] / scaler

        # CORREZIONE 3: Sostituito elif con else per garantire sempre un ritorno
        if g is True:
            return {
                "x": x - (self.offset_x / _GRAVITIY_MS2),
                "y": y - (self.offset_y / _GRAVITIY_MS2),
                "z": z - (self.offset_z / _GRAVITIY_MS2)
            }
        else:
            # Qui la libreria sottrae i tuoi difetti di fabbrica!
            x = (x * _GRAVITIY_MS2) - self.offset_x
            y = (y * _GRAVITIY_MS2) - self.offset_y
            z = (z * _GRAVITIY_MS2) - self.offset_z
            return {"x": x, "y": y, "z": z}

    def read_accel_abs(self, g=False):
        d=self.read_accel_data(g)
        return sqrt(d["x"]**2 + d["y"]**2 + d["z"]**2)

    def set_gyro_range(self, gyro_range):
        self.i2c.writeto_mem(self.addr, _GYRO_CONFIG, bytes([gyro_range]))
        self._gyro_range = gyro_range

    def get_gyro_range(self, raw = False):
        raw_data = self.i2c.readfrom_mem(self.addr, _GYRO_CONFIG, 2)
        if raw is True:
            return raw_data[0]
        else:
            if raw_data[0] == _GYR_RNG_250DEG: return 250
            elif raw_data[0] == _GYR_RNG_500DEG: return 500
            elif raw_data[0] == _GYR_RNG_1000DEG: return 1000
            elif raw_data[0] == _GYR_RNG_2000DEG: return 2000
            else: return -1

    def read_gyro_data(self):
        gyro_data = self._readData(_GYRO_XOUT0)
        gyro_range = self._gyro_range
        scaler = None

        if gyro_range == _GYR_RNG_250DEG: scaler = _GYR_SCLR_250DEG
        elif gyro_range == _GYR_RNG_500DEG: scaler = _GYR_SCLR_500DEG
        elif gyro_range == _GYR_RNG_1000DEG: scaler = _GYR_SCLR_1000DEG
        elif gyro_range == _GYR_RNG_2000DEG: scaler = _GYR_SCLR_2000DEG
        else:
            print("Unkown range - scaler set to _GYR_SCLR_250DEG")
            scaler = _GYR_SCLR_250DEG

        x = gyro_data["x"] / scaler
        y = gyro_data["y"] / scaler
        z = gyro_data["z"] / scaler
        return {"x": x, "y": y, "z": z}

    def read_angle(self):
        a = self.read_accel_data()
        x = atan2(a["y"], a["z"])
        y = atan2(-a["x"], a["z"])
        return {"x": x, "y": y}