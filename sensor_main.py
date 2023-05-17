#!/usr/bin/env python

from __future__ import annotations
from logging.handlers import RotatingFileHandler
import signal
import logging
from pathlib import Path
from threading import Event
import pigpio
from display import ST7789Display, ScreenDisplay
from sensor_menu import get_menu
from sensors import BMP280, DHT, PMSA003C, Sensor, SensorReadingError
from util import ConfigManager, Database, InfluxDatabase, SensorType, RepeatTimer, SensorReadings, Switch
from menu import Interface, Key

class Device:
    def __init__(
        self,
        *,
        display: ScreenDisplay | None = None,
        config_file: str = "/etc/mini-air-quality/sensors_config.ini",
        pi_gpio: pigpio.pi = pigpio.pi(),
        database: Database | None = None,
    ) -> None:
        self.database = database or InfluxDatabase()
        self.pi_gpio = pi_gpio
        self.config_file = config_file
        self.stop_event = Event()
        self.display = display or ST7789Display()
        self.switches: list[Switch] = []
        self.last_mtime = Path(self.config_file).stat().st_mtime
        self.sensor_timers: dict[SensorType, RepeatTimer] = {}
        self.config_timer: RepeatTimer = RepeatTimer(10, self._update_freq)
        self.interface: None | Interface = None

    def _initialize(self):
        readings = SensorReadings(database=self.database)
        self.interface = Interface(
            menu=get_menu(self.config_file),
            sensor_readings=readings,
            display=self.display
        )

        if not self.pi_gpio.connected:
            logging.error("Pigpio not connected!")
        else:
            self.switches = [
                Switch(Key.UP, 5, self.pi_gpio, self.interface.key_press),
                Switch(Key.DOWN, 19, self.pi_gpio, self.interface.key_press, long_push_time=0.5),
                Switch(Key.CANCEL, 6, self.pi_gpio, self.interface.key_press),
                Switch(Key.OK, 13, self.pi_gpio, self.interface.key_press)
            ]

        self.sensor_timers = self._get_sensor_timers(readings, self.interface)
        for timer in self.sensor_timers.values():
            timer.start()

        self.config_timer.start()

    def _update_freq(self):
        if not ConfigManager.is_cache_current(self.config_file):
            for sensor_type, new_freq in self._get_current_conf().items():
                self.sensor_timers[sensor_type].interval = new_freq

    def stop(self):
        self.stop_event.set()

    def run(self):
        self._initialize()
        self.stop_event.wait()
        self.close()

    def close(self):
        for switch in self.switches:
            switch.clean()
        self.config_timer.cancel()
        self.config_timer.join(1)
        for timer in self.sensor_timers.values():
            timer.cancel()
            timer.join(1)
        self.interface.close()
        self.database.close()

    def _get_current_conf(self) -> dict[SensorType, int]:
        config = ConfigManager.get_config(self.config_file)
        sensor_conf = {}
        for sensor_type in SensorType:
            type_conf = sensor_type.value
            if type_conf in config['sensors_config']:
                sensor_conf[sensor_type] = int(config['sensors_config'][type_conf])
        return sensor_conf

    def _get_sensor_timers(self, readings: SensorReadings, interface: Interface):
        dht = DHT()
        bmp = BMP280()
        pmsa = PMSA003C()
        start_conf = self._get_current_conf()

        def update_reading(sensor: Sensor, sensor_type: SensorType):
            try:
                value = sensor.get_reading(sensor_type)
                readings.add(sensor_type, value)
                interface.update_sensor(sensor_type)
            except SensorReadingError:
                logging.warning("SensorReadingError: %s, %s", sensor.__class__.__name__, sensor_type.name)

        def get_timer(sensor, sensor_type, default_value):
            return RepeatTimer(start_conf.get(sensor_type, default_value), update_reading, sensor, sensor_type)

        return {
            SensorType.HUMIDITY: get_timer(dht, SensorType.HUMIDITY, 10),
            SensorType.TEMPERATURE: get_timer(dht, SensorType.TEMPERATURE, 10),
            SensorType.PRESSURE: get_timer(bmp, SensorType.PRESSURE, 10),
            SensorType.PM1: get_timer(pmsa, SensorType.PM1, 10),
            SensorType.PM2_5: get_timer(pmsa, SensorType.PM2_5, 10),
            SensorType.PM10: get_timer(pmsa, SensorType.PM10, 10),
        }

def main():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.WARNING,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[RotatingFileHandler("sensor.log", encoding="utf-8", backupCount=2, maxBytes=1_000_000)]
    )
    device = Device()
    def sigint_handler(_1, _2):
        device.stop()
    signal.signal(signal.SIGINT, sigint_handler)
    try:
        device.run()
    except Exception: #pylint: disable=broad-except
        logging.exception("device.run()")
        device.stop()

if __name__ == "__main__":
    main()
