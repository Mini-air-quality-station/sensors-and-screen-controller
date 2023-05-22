#!/usr/bin/env python

from __future__ import annotations
from logging.handlers import RotatingFileHandler
import signal
import logging
from threading import Event
import pigpio
from display import ST7789Display, ScreenDisplay
from sensor_menu import get_menu
from sensors import BMP280, DHT, PMSA003C, Sensor, SensorReadingError
from util import ConfigManager, InfluxDatabase, SensorType, RepeatTimer, SensorReadings, Switch
from menu import Interface, Key


class Device:
    def __init__(
        self,
        *,
        display: ScreenDisplay | None = None,
        pi_gpio=pigpio.pi(),
    ) -> None:
        self.database = InfluxDatabase()
        self.pi_gpio = pi_gpio
        self.stop_event = Event()
        self.display = display or ST7789Display()
        self.switches: list[Switch] = []
        self.sensor_timers: dict[SensorType, RepeatTimer] = {}
        self.config_timer: RepeatTimer = RepeatTimer(10, self._update_freq)
        self.interface: None | Interface = None

    def _initialize(self):
        readings = SensorReadings(database=self.database)
        self.interface = Interface(
            menu=get_menu(),
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
        if not ConfigManager.is_cache_current(display_config=False):
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
        config = ConfigManager.get_config(display_config=False)
        sensor_conf = {}
        for sensor_type in SensorType:
            type_conf = sensor_type.value
            if type_conf in config['sensors_config']:
                sensor_conf[sensor_type] = int(config['sensors_config'][type_conf])
        return sensor_conf

    def _get_sensor_timers(self, readings: SensorReadings, interface: Interface):
        def make_sensor(sensor_class: type[Sensor], *args) -> Sensor | None:
            try:
                return sensor_class(*args)
            except Exception:  # pylint: disable=broad-exception-caught
                logging.exception("Couldn't init sensor: %s", sensor_class.__name__)
                return None

        dht = make_sensor(DHT)
        bmp = make_sensor(BMP280)
        pmsa = make_sensor(PMSA003C, self.pi_gpio)
        sensors: list[tuple[SensorType, Sensor | None]] = [
            (SensorType.HUMIDITY, dht), (SensorType.TEMPERATURE, dht), (SensorType.PRESSURE, bmp),
            (SensorType.PM1, pmsa), (SensorType.PM2_5, pmsa), (SensorType.PM10, pmsa)
        ]
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
            sensor_type: get_timer(sensor, sensor_type, 10)
            for sensor_type, sensor in sensors if sensor is not None
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
    except Exception:  # pylint: disable=broad-except
        logging.exception("device.run()")
        device.stop()


if __name__ == "__main__":
    main()
