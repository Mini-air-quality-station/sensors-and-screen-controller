from __future__ import annotations
from enum import Enum, auto
import functools
import logging
from threading import Event, Lock, Timer
from typing import Callable

import pigpio

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
from urllib3.exceptions import NewConnectionError

class SensorType(Enum):
    TEMPERATURE = auto(),
    HUMIDITY = auto(),
    PRESSURE = auto(),
    PM1 = auto(),
    PM2_5 = auto(),
    PM10 = auto()

    @classmethod
    @functools.cache
    def index(cls, sensor_type: SensorType):
        """@brief Returns index of element"""
        return list(SensorType).index(sensor_type)

    @functools.cache
    def to_conf(self):
        type_conf = {
            SensorType.TEMPERATURE: "temperature_dht22_freq",
            SensorType.HUMIDITY: "humidity_dht22_freq",
            SensorType.PRESSURE: "pressure_bmp280_freq",
            SensorType.PM1: "particle_pm1_pmsa003-c_freq",
            SensorType.PM2_5: "particle_pm25_pmsa003-c_freq",
            SensorType.PM10: "particle_pm10_pmsa003-c_freq",
        }
        return type_conf[self]


class Key(Enum):
    UP = auto()
    DOWN = auto()
    OK = auto()
    CANCEL = auto()


class Database:
    def close(self):
        pass

    #pylint: disable-next=unused-argument
    def get_last(self, sensor_type: SensorType) -> int | float:
        return 0

    def add(self, sensor_type: SensorType, value: int | float):
        pass

class InfluxDatabase(Database):
    def __init__(self) -> None:
        self._lock = Lock()

        url = "http://localhost:8086"
        self.org = "my-org"
        self.client = influxdb_client.InfluxDBClient(url=url, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def close(self):
        self.write_api.close()
        self.client.close()

    def get_last(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            query = f'from(bucket:"sensors")\
                |> range(start: 0)\
                |> filter(fn:(r) => r._measurement == "{sensor_type.name}")\
                |> last()'

            try:
                result = self.query_api.query(org=self.org, query=query)
                return result[0].records[0].get_value()
            except IndexError:
                logging.info("%s table is empty", sensor_type.name)
                return float('nan')
            except NewConnectionError:
                logging.exception("InfluxDB Connection error, couldn't write")
                return float('nan')
            except ApiException:
                logging.exception("InfluxDB ApiException, couldn't write")
                return float('nan')

    def add(self, sensor_type: SensorType, value: int | float):
        with self._lock:
            point = influxdb_client.Point(sensor_type.name).field("value", value)
            try:
                self.write_api.write(bucket="sensors", org=self.org, record=point)
            except NewConnectionError:
                logging.exception("InfluxDB Connection error, couldn't write")
            except ApiException:
                logging.exception("InfluxDB ApiException, couldn't write")


class SensorReadings:
    def __init__(self, database: Database) -> None:
        self.readings = {
            SensorType.TEMPERATURE: database.get_last(SensorType.TEMPERATURE),
            SensorType.HUMIDITY: database.get_last(SensorType.HUMIDITY),
            SensorType.PRESSURE: database.get_last(SensorType.PRESSURE),
            SensorType.PM1: database.get_last(SensorType.PM1),
            SensorType.PM2_5: database.get_last(SensorType.PM2_5),
            SensorType.PM10: database.get_last(SensorType.PM10),
        }
        self.database = database

    def get(self, sensor_type: SensorType):
        return self.readings[sensor_type]

    def add(self, sensor_type: SensorType, value: int | float):
        self.readings[sensor_type] = value
        self.database.add(sensor_type, value)

class ResettableTimer(Timer):
    """call start to initialize, call reset to 'start' timer"""
    def __init__(self, interval: float, function: Callable[..., object], *args, **kwargs) -> None:
        super().__init__(interval, function, args, kwargs)
        self._function_wait = Event()
        self._end = False
        self._lock = Lock()

    def cancel(self):
        with self._lock:
            super().cancel()
            self._end = True
            self._function_wait.set()

    def stop(self):
        """@brief stop timer and wait for cancel or reset"""
        self._function_wait.set()

    def reset(self, interval: float | None = None):
        """@brief restart timer with different interval if not None"""
        with self._lock:
            # in case _funtion_wait is waiting
            self._function_wait.set()
            self._function_wait.clear()
            if interval is not None:
                self.interval = interval
            self.finished.set()

    def run(self) -> None:
        while self.finished.wait():
            with self._lock:
                if self._end:
                    break
                self.finished.clear()
            finished_wait = not self._function_wait.wait(self.interval)
            if finished_wait:
                self.function(*self.args, **self.kwargs)

class RepeatTimer(Timer):
    def __init__(self, interval: float, function: Callable[..., object], *args, **kwargs) -> None:
        super().__init__(interval, function, args, kwargs)

    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

class Switch:
    def __init__(self, key: Key, pin: int, pi_gpio: pigpio.pi, callback: Callable[[Key], None], debounce: float = 0.05) -> None:
        """ Maintains current state of push button after debouncing.
            Calls callback when button is pushed.
        """
        self.key = key
        self.pin = pin
        pi_gpio.set_mode(pin, pigpio.INPUT)
        pi_gpio.set_pull_up_down(pin, pigpio.PUD_DOWN)
        self.current_state = pi_gpio.read(pin)
        self._lock = Lock()
        self._debounce_timer = ResettableTimer(debounce, self.change_state)
        self._debounce_timer.start()
        self._edge_callback = pi_gpio.callback(pin, pigpio.EITHER_EDGE, self.edge_change)
        self.callback = callback

    def edge_change(self, _1, level, _2):
        with self._lock:
            if level != 2:
                if level != self.current_state:
                    self._debounce_timer.reset()
                else:
                    self._debounce_timer.stop()

    def change_state(self):
        self.current_state = not self.current_state
        if self.current_state:
            self.callback(self.key)

    def clean(self):
        """@brief Call when done using switch."""
        self._edge_callback.cancel()
        self._debounce_timer.cancel()
        self._debounce_timer.join()