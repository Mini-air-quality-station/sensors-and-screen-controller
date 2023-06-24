from __future__ import annotations
from configparser import ConfigParser
from contextlib import AbstractContextManager, nullcontext
from copy import deepcopy
from enum import Enum, auto
import fcntl
import functools
from io import TextIOWrapper
import logging
from pathlib import Path
from threading import Lock, RLock, Timer, Condition
from typing import Callable, TypedDict
import pigpio
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
from urllib3.exceptions import NewConnectionError


CONFIG = {
    "sensor_file": "/etc/mini-air-quality/sensors_config.ini",
    "sensor_section": "sensors_config",
    "sensor_lock": "/etc/mini-air-quality/envs.lock",
    "display_file": "./display_config.ini",
    "display_section": "display_config",
}


class SensorType(Enum):
    TEMPERATURE = "temperature_dht22_freq"
    HUMIDITY = "humidity_dht22_freq"
    PRESSURE = "pressure_bmp280_freq"
    PM1 = "particle_pm1_pmsa003-c_freq"
    PM2_5 = "particle_pm25_pmsa003-c_freq"
    PM10 = "particle_pm10_pmsa003-c_freq"

    @classmethod
    @functools.cache
    def index(cls, sensor_type: SensorType) -> int:
        """@brief Returns index of element"""
        return list(SensorType).index(sensor_type)


class Key(Enum):
    UP = auto()
    DOWN = auto()
    OK = auto()
    CANCEL = auto()


class InfluxDatabase:
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

    def close(self) -> None:
        self.write_api.close()
        self.client.close()

    def add(self, sensor_type: SensorType, value: int | float) -> None:
        with self._lock:
            point = influxdb_client.Point(sensor_type.name).field("value", value)
            try:
                self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            except NewConnectionError as exc:
                logging.error("InfluxDB Connection error, couldn't write: %s", exc)
            except ApiException as exc:
                logging.error("InfluxDB ApiException, couldn't write: %s", exc)


class SensorReadings:
    def __init__(self, database: InfluxDatabase) -> None:
        self.readings: dict[SensorType, int | float | None] = {
            SensorType.TEMPERATURE: None,
            SensorType.HUMIDITY: None,
            SensorType.PRESSURE: None,
            SensorType.PM1: None,
            SensorType.PM2_5: None,
            SensorType.PM10: None,
        }
        self.database = database

    def get(self, sensor_type: SensorType) -> int | float | None:
        return self.readings[sensor_type]

    def add(self, sensor_type: SensorType, value: int | float) -> None:
        self.readings[sensor_type] = value
        self.database.add(sensor_type, value)


class ResettableTimer(Timer):
    """call start to initialize, call reset to 'start' timer"""
    def __init__(self, interval: float, function: Callable[..., object], *args, **kwargs) -> None:
        super().__init__(interval, function, args, kwargs)
        self._function_wait = Condition()
        self._end = False

    def cancel(self) -> None:
        with self._function_wait:
            super().cancel()
            self._end = True
            self._function_wait.notify()

    def stop(self) -> None:
        """@brief stop timer and wait for cancel or reset"""
        with self._function_wait:
            self._function_wait.notify()

    def reset(self, interval: float | None = None) -> None:
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
        self.stop = False

    def cancel(self) -> None:
        self.stop = True
        super().cancel()

    def reset(self, new_interval: float | None = None) -> None:
        if new_interval is not None:
            self.interval = new_interval
        self.finished.set()

    def run(self) -> None:
        while not self.stop:
            if not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)
            self.finished.clear()


class Switch:
    def __init__(
            self,
            key: Key,
            pin: int,
            pi_gpio: pigpio.pi,
            callback: Callable[[Key, bool], None],
            debounce: float = 0.05,
            long_push_time: float = 0.5,
    ) -> None:
        """ Maintains current state of push button after debouncing.
            Calls callback(key, False) when button is pushed.
            Calls callback(key, True) again when button is pushed for more than long_push_time seconds
        """
        self.key = key
        self.pin = pin
        pi_gpio.set_mode(pin, pigpio.INPUT)
        pi_gpio.set_pull_up_down(pin, pigpio.PUD_DOWN)
        self.current_state = pi_gpio.read(pin)
        self._lock = Lock()
        self._debounce_timer = ResettableTimer(debounce, self.change_state)
        self._debounce_timer.start()
        self._long_timer = ResettableTimer(long_push_time, callback, self.key, True)
        self._long_timer.start()
        self._edge_callback = pi_gpio.callback(pin, pigpio.EITHER_EDGE, self.edge_change)
        self.callback = callback

    def edge_change(self, _1, level, _2) -> None:
        with self._lock:
            if level != 2:
                if level != self.current_state:
                    self._debounce_timer.reset()
                else:
                    self._debounce_timer.stop()

    def change_state(self) -> None:
        self.current_state = not self.current_state
        if self.current_state:
            self.callback(self.key, False)
            self._long_timer.reset()
        else:
            self._long_timer.stop()

    def clean(self) -> None:
        """@brief Call when done using switch."""
        self._edge_callback.cancel()
        self._debounce_timer.cancel()
        self._long_timer.cancel()
        self._debounce_timer.join(1)
        self._long_timer.join(1)


class FileLock:
    def __init__(self, lock_filepath: str) -> None:
        self.depth = 0
        self.lock_filepath = lock_filepath
        self.lock_file: TextIOWrapper | None = None

    def __enter__(self) -> None:
        if self.depth == 0:
            self.lock_file = open(self.lock_filepath, "w", encoding="utf-8")
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX)
            except Exception:
                self.lock_file.close()
                self.lock_file = None
                raise
        self.depth += 1

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.depth -= 1
        if self.depth == 0:
            assert isinstance(self.lock_file, TextIOWrapper)
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            finally:
                self.lock_file.close()
                self.lock_file = None


class ConfigManager:
    class ConfigCache(TypedDict):
        config_file: str
        file_lock: AbstractContextManager
        st_mtime: float
        config: ConfigParser | None

    _lock = RLock()
    _config_cache: ConfigCache = {
        "config_file": CONFIG["sensor_file"],
        "file_lock": FileLock(CONFIG["sensor_lock"]),
        "st_mtime": float('-inf'),
        "config": None
    }
    _display_cache: ConfigCache = {
        "config_file": CONFIG["display_file"],
        "file_lock": nullcontext(),
        "st_mtime": float('-inf'),
        "config": None
    }

    @classmethod
    def is_cache_current(cls, *, display_config: bool) -> bool:
        """Return False if config isn't cached or file was modified since last cached"""
        with cls._lock:
            cache = cls._display_cache if display_config else cls._config_cache
            return cache["config"] is not None and cache["st_mtime"] == Path(cache["config_file"]).stat().st_mtime

    @classmethod
    def _get_config(cls, *, display_config: bool) -> ConfigParser:
        with cls._lock:
            if display_config and cls._display_cache["config"]:
                logging.debug("%s: cached display config", cls._display_cache["config_file"])
                return cls._display_cache["config"]
            cache = cls._display_cache if display_config else cls._config_cache
            config_file = cache["config_file"]
            configpath = Path(config_file)
            config = cache["config"]
            if config is None:
                config = ConfigParser()
                with cache["file_lock"]:
                    config.read(config_file)
                logging.debug("%s: loaded config: not cached", config_file)
                cache["st_mtime"] = configpath.stat().st_mtime
                cache["config"] = config
            else:
                st_mtime = configpath.stat().st_mtime
                if st_mtime != cache["st_mtime"]:
                    logging.debug("%s: loaded config: file changed", config_file)
                    cache["st_mtime"] = st_mtime
                    config = ConfigParser()
                    with cache["file_lock"]:
                        config.read(config_file)
                    cache["config"] = config
                else:
                    logging.debug("%s: cached config", config_file)
            return config

    @classmethod
    def get_config(cls, *, display_config: bool) -> ConfigParser:
        """
        If config not in cache then load from file.
        If config is in cache and is current or internal_config == True then return cache copy
        If config file was modified after caching then reload from file
        """
        logging.debug("deepcopy(display_config=%s)", display_config)
        try:
            config = cls._get_config(display_config=display_config)
        except OSError:
            logging.exception("_get_config exception")
            config = ConfigParser()
        return deepcopy(config)

    @classmethod
    def get_config_value(cls, key: str, *, display_config: bool) -> str | None:
        """@brief Return value of config with key=key. If key doesn't exist return None"""
        config_section = CONFIG["display_section"] if display_config else CONFIG["sensor_section"]
        with cls._lock:
            try:
                config = cls._get_config(display_config=display_config)
                return str(config[config_section][key])
            except KeyError:
                logging.error("Key %s or section %s doesn't exist!(display_config=%s)\n", key, config_section, display_config)
                return None
            except OSError:
                logging.exception("_get_config exception")
                return None

    @classmethod
    def update_config_values(cls, key_value: dict[str, str], *, display_config: bool) -> None:
        cache = cls._display_cache if display_config else cls._config_cache
        config_section = CONFIG["display_section"] if display_config else CONFIG["sensor_section"]
        with cls._lock, cache["file_lock"]:
            config = cls._get_config(display_config=display_config)
            if not config.has_section(config_section):
                config.add_section(config_section)
            for key, value in key_value.items():
                config[config_section][key] = value
            config_path = Path(cache["config_file"])
            with config_path.open("w", encoding="utf-8") as file:
                config.write(file)
            cache["st_mtime"] = config_path.stat().st_mtime
