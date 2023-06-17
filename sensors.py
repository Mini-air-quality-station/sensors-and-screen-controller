from __future__ import annotations
from abc import ABC, abstractmethod
from threading import Lock
from typing import DefaultDict, Literal
from collections import deque, defaultdict
from statistics import median_low
import board
import adafruit_bmp280
from adafruit_dht import DHT22
import pigpio
from util import SensorType


class SensorReadingError(Exception):
    pass


class MutableBool:
    def __init__(self, initial_value: bool) -> None:
        self.bool_value = initial_value

    def __bool__(self) -> bool:
        return self.bool_value

    def __eq__(self, __value: object) -> bool:
        return self.bool_value == __value

class Sensor(ABC):
    def __init__(self) -> None:
        super().__init__()
        self._lock = Lock()
        # MutableBool is true if values are new(weren't read since last addition)
        bool_deque_type = tuple[MutableBool, deque[int | float]]
        self._readings: DefaultDict[SensorType, bool_deque_type] = defaultdict(lambda: (MutableBool(False), deque(list(), 6)))

    @abstractmethod
    def get_reading(self, sensor_type: SensorType) -> int | float:
        raise NotImplementedError

    def _add_reading(self, sensor_type: SensorType, value: int | float) -> None:
        is_new, readings_deque = self._readings[sensor_type]
        readings_deque.append(value)
        is_new.bool_value = True

    def _get_median(self, sensor_type: SensorType) -> int | float:
        is_new, readings_deque = self._readings[sensor_type]
        if not is_new or len(readings_deque) != readings_deque.maxlen:
            raise SensorReadingError
        is_new.bool_value = False
        return median_low(readings_deque)


class DHT(Sensor):
    def __init__(self) -> None:
        super().__init__()
        self.dht = DHT22(board.D4)

    def get_reading(self, sensor_type: SensorType) -> int | float:
        assert sensor_type in [SensorType.TEMPERATURE, SensorType.HUMIDITY], f"Wrong DHT sensor type({sensor_type})"
        with self._lock:
            try:
                if sensor_type is SensorType.TEMPERATURE:
                    temp = self.dht.temperature
                    if temp is not None:
                        self._add_reading(sensor_type, round(temp, 1))
                else:
                    humidity = self.dht.humidity
                    if humidity is not None:
                        self._add_reading(sensor_type, round(humidity, 1))
            except RuntimeError as exc:
                raise SensorReadingError from exc

            return self._get_median(sensor_type)


class BMP280(Sensor):
    def __init__(self) -> None:
        super().__init__()
        self.bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(board.I2C(), address=0x76)

    def get_reading(self, sensor_type: SensorType) -> int | float:
        assert sensor_type is SensorType.PRESSURE, f"Wrong BMP280 sensor type({sensor_type})"
        with self._lock:
            try:
                pressure = self.bmp280.pressure
                if pressure is not None:
                    self._add_reading(sensor_type, int(pressure))
            except (ValueError, ArithmeticError) as exc:
                raise SensorReadingError from exc

            return self._get_median(sensor_type)


class PMSA003C(Sensor):
    BYTEORDER: Literal['big'] = 'big'

    def __init__(self, pi: pigpio.pi) -> None:
        if not pi.connected:
            raise AttributeError
        super().__init__()
        self.RX = 24
        self.pi = pi
        self.start1 = 0x42
        self.start2 = 0x4d
        pigpio.exceptions = False
        self.pi.bb_serial_read_close(self.RX)
        pigpio.exceptions = True
        self.pi.bb_serial_read_open(self.RX, 9600)

        self.data: bytearray = bytearray()

    def check_sum(self, data) -> bool:
        # check if sum of first 30 bytes is same as last 2 bytes
        return len(data) == 32 and sum(data[:30]) == int.from_bytes(data[-2:], byteorder=self.BYTEORDER)

    def get_data(self, data: bytearray) -> bytearray:
        # find all occurences of self.start1 and self.start2 bytes
        indexes = [i for i, x in enumerate(data[:-1]) if x == self.start1 and data[i+1] == self.start2]
        # find last(newest) data frame
        for i in reversed(indexes):
            if self.check_sum(data[i:i+32]):
                return data[i:i+32]
        return bytearray()

    def update(self) -> None:
        _, data = self.pi.bb_serial_read(self.RX)
        if isinstance(data, bytearray):
            self.data += data
        frame = self.get_data(self.data)
        if frame:
            self._add_reading(SensorType.PM1, int.from_bytes(data[4:6], byteorder=self.BYTEORDER))
            self._add_reading(SensorType.PM2_5, int.from_bytes(data[6:8], byteorder=self.BYTEORDER))
            self._add_reading(SensorType.PM10, int.from_bytes(data[8:10], byteorder=self.BYTEORDER))
            self.data = bytearray()

    def get_reading(self, sensor_type: SensorType) -> int | float:
        assert sensor_type in [SensorType.PM1, SensorType.PM2_5, SensorType.PM10], (
            f"Wrong PMSA003C sensor type({sensor_type})"
        )
        with self._lock:
            try:
                self.update()
            except pigpio.error as exc:
                raise SensorReadingError from exc

            return self._get_median(sensor_type)
