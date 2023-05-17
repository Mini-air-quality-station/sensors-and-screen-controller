from __future__ import annotations
from abc import ABC, abstractmethod
from threading import Lock
import logging
import board
import adafruit_bmp280
from adafruit_dht import DHT22
import pigpio
from util import SensorType


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
        try:
            self.dht = DHT22(board.D4)
        except AttributeError:
            logging.exception("DHT error")

    def get_reading(self, sensor_type: SensorType) -> int:
        with self._lock:
            try:
                if sensor_type is SensorType.TEMPERATURE:
                    temp = self.dht.temperature
                    if temp is not None:
                        return int(temp)
                elif sensor_type is SensorType.HUMIDITY:
                    humidity = self.dht.humidity
                    if humidity is not None:
                        return int(humidity)
            except Exception as exc:
                raise SensorReadingError from exc
        raise SensorReadingError


class BMP280(Sensor):
    def __init__(self) -> None:
        super().__init__()
        try:
            self.bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(board.I2C(), address=0x76)
        except AttributeError:
            logging.exception("BMP280 error")

    def get_reading(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            try:
                if sensor_type is SensorType.PRESSURE:
                    pressure = self.bmp280.pressure
                    if pressure is not None:
                        return int(self.bmp280.pressure)
            except Exception as exc:
                raise SensorReadingError from exc
        raise SensorReadingError


class PMSA003C(Sensor):
    def __init__(self) -> None:
        super().__init__()
        self.RX = 24
        self.pi: pigpio.pi = pigpio.pi()
        self.start1 = 0x42
        self.start2 = 0x4d
        self.working = True
        self.pm: dict[SensorType, None | int] = {
            SensorType.PM1: None,
            SensorType.PM2_5: None,
            SensorType.PM10: None
        }

        if not self.pi.connected:
            logging.error("pigpio not connected!")
            self.working = False
            return

        pigpio.exceptions = False
        self.pi.bb_serial_read_close(self.RX)
        pigpio.exceptions = True
        self.pi.bb_serial_read_open(self.RX, 9600)

        self.data: bytearray = bytearray()

    def check_sum(self, data) -> bool:
        return len(data) == 32 and sum(data[:30]) == int.from_bytes(data[-2:], byteorder='big')

    def get_data(self, data: bytearray) -> bytearray:
        indices = [i for i, x in enumerate(data[:-1]) if x == self.start1 and data[i+1] == self.start2]
        for i in reversed(indices):
            if self.check_sum(data[i:i+32]):
                return data[i:i+32]
        return bytearray()

    def update(self) -> None:
        _, data = self.pi.bb_serial_read(self.RX)
        if isinstance(data, bytearray):
            self.data += data
        frame = self.get_data(self.data)
        if frame:
            self.pm[SensorType.PM1] = int.from_bytes(data[4:6], byteorder='big')
            self.pm[SensorType.PM2_5] = int.from_bytes(data[6:8], byteorder='big')
            self.pm[SensorType.PM10] = int.from_bytes(data[8:10], byteorder='big')
            self.data = bytearray()

    def get_reading(self, sensor_type: SensorType) -> int | float:
        if not self.working:
            raise SensorReadingError
        with self._lock:
            try:
                self.update()
            except Exception as exc:
                raise SensorReadingError from exc

            tmp = self.pm[sensor_type]
            if tmp is None:
                raise SensorReadingError

            self.pm[sensor_type] = None
            return tmp
