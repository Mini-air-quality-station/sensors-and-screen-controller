from __future__ import annotations
from abc import ABC, abstractmethod
from random import randint
from threading import Lock
import board
import adafruit_bmp280
import logging
from adafruit_dht import DHT22

from util import SensorType

class WrongSensorType(Exception):
    pass
class SensorReadingError(Exception):
    pass

class Sensor(ABC):
    def __init__(self) -> None:
        super().__init__()
        self._lock = Lock()

    @abstractmethod
    def get_reading(self, sensor_type: SensorType) -> int | float:
        raise NotImplementedError

class DHT(Sensor):
    def __init__(self) -> None:
        super().__init__()
        self.dht = DHT22(board.D4)

    def get_reading(self, sensor_type: SensorType) -> int:
        with self._lock:
            try:
                if sensor_type == SensorType.TEMPERATURE:
                    return self.dht.temperature
                if sensor_type == SensorType.HUMIDITY:
                    return self.dht.humidity
            except:
                logging.exception("Couldn't get a reading")
                raise SensorReadingError
        raise WrongSensorType

class BMP280(Sensor):
    def __init__(self) -> None:
        super().__init__()
        self.i2c = board.I2C()
        
    def get_reading(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            try:
                if sensor_type == SensorType.PRESSURE:
                    bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=0x76)
                    return '{:.1f}'.format(bmp280.pressure)
            except:
                logging.exception("Couldn't get a reading")
                raise SensorReadingError
        raise WrongSensorType

class PMSA003C(Sensor):
    def get_reading(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            try:
                if sensor_type == SensorType.PM1:
                    return randint(0, 10)
                elif sensor_type == SensorType.PM2_5:
                    return randint(10, 20)
                elif sensor_type == SensorType.PM10:
                    return randint(20, 30)
            except:
                logging.exception("Couldn't get a reading")
                raise SensorReadingError
        raise WrongSensorType
