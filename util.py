from __future__ import annotations
from configparser import ConfigParser
from enum import Enum, auto
import functools
import logging
from pathlib import Path
import shutil
from threading import Lock, Timer, Condition
from typing import Callable

import pigpio

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
from urllib3.exceptions import NewConnectionError

class SensorType(Enum):
    TEMPERATURE = "temperature_dht22_freq"
    HUMIDITY = "humidity_dht22_freq"
    PRESSURE = "pressure_bmp280_freq"
    PM1 = "particle_pm1_pmsa003-c_freq"
    PM2_5 = "particle_pm25_pmsa003-c_freq"
    PM10 = "particle_pm10_pmsa003-c_freq"

    @classmethod
    @functools.cache
    def index(cls, sensor_type: SensorType):
        """@brief Returns index of element"""
        return list(SensorType).index(sensor_type)


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
        self.org = "mini_air_quality"
        self.bucket = "sensor_data"
        self.username = "mini_air_quality"
        self.password = "mini_air_quality"
        self.token = "6y-fM0HpRAwx1P-fbH_3DaXklPqyFlAzUd58STICzqAlIcOks55jpjhyf6udF-nCykZTLzRMor48r279jfFWWw=="
        self.client = influxdb_client.InfluxDBClient(
            url=url, org=self.org, username=self.username, password=self.password, token=self.token
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def close(self):
        self.write_api.close()
        self.client.close()

    def get_last(self, sensor_type: SensorType) -> int | float:
        with self._lock:
            query = f'from(bucket:"{self.bucket}")\
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
                self.write_api.write(bucket=self.bucket, org=self.org, record=point)
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
        self._function_wait = Condition()
        self._end = False

    def cancel(self):
        with self._function_wait:
            super().cancel()
            self._end = True
            self._function_wait.notify()

    def stop(self):
        """@brief stop timer and wait for cancel or reset"""
        with self._function_wait:
            self._function_wait.notify()

    def reset(self, interval: float | None = None):
        """@brief restart timer with different interval if not None"""
        with self._function_wait:
            if interval is not None:
                self.interval = interval
            self._function_wait.notify()
            self.finished.set()

    def run(self) -> None:
        while self.finished.wait():
            with self._function_wait:
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

class ConfigManager:
    _lock = Lock()

    @classmethod
    def get_config(cls, config_file: str) -> ConfigParser:
        config = ConfigParser()
        with cls._lock:
            config.read(config_file)
        return config

    @classmethod
    def get_config_value(cls, config_file: str, config_section: str, key: str):
        """@brief Return value of config with key=key. If key doesn't exist return None"""
        config = cls.get_config(config_file)
        try:
            return str(config[config_section][key])
        except KeyError:
            print(f"{config_file}: Key {key} or section {config_section} doesn't exist!")
            logging.error("%s: Key %s doesn't exist!\n", config_file, key)
            return None

    @classmethod
    def update_config_values(cls, config_file: str, config_section: str, key_value: dict[str, str]):
        config = cls.get_config(config_file)
        for key, value in key_value.items():
            config[config_section][key] = value
        tmp_file = Path(Path(config_file).parent / f"{config_file}.replace")
        with tmp_file.open(mode="w", encoding="utf8") as new_config_file:
            config.write(new_config_file)

        shutil.move(tmp_file, config_file)
