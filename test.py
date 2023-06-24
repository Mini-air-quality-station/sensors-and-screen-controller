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
from util import CONFIG, ConfigManager, FileLock
import sensors
from util import SensorType


PIN_TO_KEY = {
    5: pygame.K_UP,
    19: pygame.K_DOWN,
    6: pygame.K_LEFT,
    13: pygame.K_RIGHT
}

def get_reading(self, sensor_type: SensorType) -> int | float:
    wiggle = 1
    add_or_sub = True if random.random() < 0.5 else False
    temp_val = 21 + wiggle if add_or_sub else 21
    hum_val = 60 + wiggle if add_or_sub else 60
    press_val = 1015 + wiggle if add_or_sub else 1015
    pm1_val = 3 + wiggle if add_or_sub else 3
    pm25_val = 1 + wiggle if add_or_sub else 1
    pm10_val = 2 + wiggle if add_or_sub else 2
    match sensor_type:
        case SensorType.TEMPERATURE:
            return temp_val
        case SensorType.HUMIDITY:
            return hum_val
        case SensorType.PRESSURE:
            return press_val
        case SensorType.PM1:
            return pm1_val
        case SensorType.PM2_5:
            return pm25_val
        case SensorType.PM10:
            return pm10_val


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
    sensors.DHT.__init__ = init
    sensors.BMP280.__init__ = init
    sensors.PMSA003C.__init__ = init
    sensors.DHT.get_reading = get_reading
    sensors.BMP280.get_reading = get_reading
    sensors.PMSA003C.get_reading = get_reading

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
