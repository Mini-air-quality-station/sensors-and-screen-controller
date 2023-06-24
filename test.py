from __future__ import annotations
import logging
import random
import signal
import time
from threading import Lock, Thread
from typing import Callable, Literal
import pygame
from luma.emulator.device import pygame as luma_pygame
from PIL import ImageFont
from display import ScreenDisplay, Terminal
from sensor_main import Device
from util import CONFIG, ConfigManager, FileLock, SensorType
import sensors


PIN_TO_KEY = {
    5: pygame.K_UP,
    19: pygame.K_DOWN,
    6: pygame.K_LEFT,
    13: pygame.K_RIGHT
}


def round_nearest(num: float, to: float) -> float:
    return round(round(num / to) * to, 1)


class RandomReading:
    def __init__(self, min_val, max_val, start, precision) -> None:
        self.min = min_val
        self.max = max_val
        self.current = start
        self.precision = precision
        self.change = 0.1

    def get_random_reading(self) -> float:
        if self.current <= self.min:
            self.current += self.change
        elif self.current >= self.max:
            self.current -= self.change
        else:
            self.current += self.change * random.choice([-1, 1])

        return round_nearest(self.current, self.precision)


class Reading:
    def __init__(self) -> None:
        self.temp_val = RandomReading(15, 25, 20, 0.2)
        self.hum_val = RandomReading(40, 80, 60, 1)
        self.press_val = RandomReading(1000, 1080, 1010, 1)
        self.pm1_val = RandomReading(2, 15, 3, 1)
        self.pm25_val = RandomReading(8, 25, 12, 1)
        self.pm10_val = RandomReading(10, 35, 15, 1)

    def get_reading(self, sensor_type: SensorType) -> float:
        if sensor_type is SensorType.TEMPERATURE:
            return self.temp_val.get_random_reading()
        if sensor_type is SensorType.HUMIDITY:
            return self.hum_val.get_random_reading()
        if sensor_type is SensorType.PRESSURE:
            return self.press_val.get_random_reading()
        if sensor_type is SensorType.PM1:
            return self.pm1_val.get_random_reading()
        if sensor_type is SensorType.PM2_5:
            return self.pm25_val.get_random_reading()
        if sensor_type is SensorType.PM10:
            return self.pm10_val.get_random_reading()


def init(self, *_args):
    super(type(self), self).__init__([])


def main():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename='sensor.log',
        encoding='utf-8',
    )

    random_reading = Reading()
    sensors.DHT.__init__ = init
    sensors.BMP280.__init__ = init
    sensors.PMSA003C.__init__ = init
    sensors.DHT.get_reading = random_reading.get_reading
    sensors.BMP280.get_reading = random_reading.get_reading
    sensors.PMSA003C.get_reading = random_reading.get_reading

    CONFIG["sensor_file"] = "sensor_specs/sensors_config.ini"
    CONFIG["sensor_lock"] = "sensor_specs/envs.lock"
    # pylint: disable=protected-access
    ConfigManager._config_cache["config_file"] = "sensor_specs/sensors_config.ini"
    ConfigManager._config_cache["file_lock"] = FileLock("sensor_specs/envs.lock")
    # pylint: enable=protected-access
    pygame.init()
    emulator = PygameEmulator(320, 240, rotate=0)
    keyboard = PigpioWrapper()
    device = Device(
        pi_gpio=keyboard,
        display=ScreenDisplay(
            terminal=Terminal(
                device=emulator,
                font=ImageFont.truetype("DejaVuSansMono.ttf", 21)
            )
        )
    )
    stop = False

    def sigint_handler(_1, _2):
        nonlocal stop
        stop = True
        device.stop()

    signal.signal(signal.SIGINT, sigint_handler)
    device_thread = Thread(target=device.run)
    device_thread.start()

    while not stop:
        time.sleep(0.02)
        pygame.event.pump()
        keystate = pygame.key.get_pressed()
        if keystate[pygame.K_ESCAPE] or pygame.event.peek(pygame.QUIT):
            break
        for callback in keyboard.callbacks:
            if keyboard.read(callback.pin) != callback.last_state:
                callback.change_state()

    device.stop()
    device_thread.join()
    emulator.abort()
    pygame.quit()


class Callback:
    def __init__(self, func: Callable[[int, int, int], None], remove_self, edge, pin, state) -> None:
        self.remove_self = remove_self
        self.func = func
        self.pin = pin
        self.edge = edge
        self.last_state = state

    def cancel(self) -> None:
        self.remove_self(self)

    def change_state(self) -> None:
        self.last_state = not self.last_state
        self.func(self.pin, self.last_state, 0)


class PigpioWrapper:
    def __init__(self) -> None:
        self.connected = True
        self.callbacks: list[Callback] = []

    def set_mode(self, _pin, _mode) -> None:
        pass

    def set_pull_up_down(self, _pin, _pull) -> None:
        pass

    def read(self, pin) -> bool:
        return pygame.key.get_pressed()[PIN_TO_KEY[pin]] if pin in PIN_TO_KEY else False

    def callback(self, pin, edge, func) -> Callback:
        if pin not in PIN_TO_KEY:
            raise NotImplementedError
        new_callback = Callback(func, self._remove_callback, edge, pin, self.read(pin))
        self.callbacks.append(new_callback)
        return new_callback

    def _remove_callback(self, _callback: Callback) -> None:
        try:
            self.callbacks.remove(_callback)
        except ValueError:
            # callback.cancel()(called in util.py Switch) calls _remove_callback.
            logging.error("Multiple calls to callback.cancel()")


class PygameEmulator(luma_pygame):
    def __init__(self, width=128, height=64, rotate=0, mode="RGB",
                 transform="scale2x", scale=2, frame_rate=60, **kwargs):
        super().__init__(width, height, rotate, mode, transform, scale, frame_rate, **kwargs)
        self.quit = False
        self._lock = Lock()

    # Called by turn_on()/turn_off() in display.py. Doesn't need to do anything
    def backlight(self, on_off) -> None:
        pass

    def abort(self) -> None:
        with self._lock:
            if not self.quit:
                self.quit = True

    def _abort(self) -> Literal[False]:
        return False

    def display(self, image) -> None:
        with self._lock:
            if not self.quit:
                super().display(image)


if __name__ == "__main__":
    main()
