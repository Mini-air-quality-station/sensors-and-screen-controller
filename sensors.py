from __future__ import annotations
from abc import ABC, abstractmethod
from random import randint
from threading import Lock

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
    def get_reading(self, sensor_type: SensorType) -> int:
        with self._lock:
            if sensor_type == SensorType.TEMPERATURE:
                return randint(10, 30)
            if sensor_type == SensorType.HUMIDITY:
                return randint(40, 100)
        raise WrongSensorType

class BMP280(Sensor):
    def get_reading(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            if sensor_type == SensorType.PRESSURE:
                return randint(990, 1100)
        raise WrongSensorType

class PMSA003C(Sensor):
    def get_reading(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            if sensor_type == SensorType.PM1:
                return randint(0, 10)
            elif sensor_type == SensorType.PM2_5:
                return randint(10, 20)
            elif sensor_type == SensorType.PM10:
                return randint(20, 30)
        raise WrongSensorType