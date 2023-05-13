import logging
import signal
from functools import partial
from threading import Lock, Thread
import time
from typing import Callable

import pigpio
from luma.emulator.device import asciiblock, pygame as luma_pygame
from PIL import ImageFont
import pygame

from display import ScreenDisplay, Terminal
from sensor_main import Device

def main():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename='sensor.log',
        encoding='utf-8',
    )
    print(f"{pygame.init()=}")
    emulator = PygameEmulator(320, 240, rotate=0)
    keyboard = KeyboardMock()
    device = Device(
        config_file="sensor_specs/sensors_config.ini",
        pi_gpio=PigpioWrapper(keyboard),
        #database=Database(),
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

PIN_TO_KEY = {
    5: pygame.K_UP,
    19: pygame.K_DOWN,
    6: pygame.K_LEFT,
    13: pygame.K_RIGHT
}

class Callback:
    def __init__(self, func: Callable[[int, int, int], None], remove_self, edge, pin, state) -> None:
        self.remove_self = remove_self
        self.func = func
        self.pin = pin
        self.edge = edge
        self.last_state = state

    def cancel(self):
        self.remove_self(self)

    def change_state(self):
        self.last_state = not self.last_state
        self.func(self.pin, self.last_state, 0)

class KeyboardMock:    
    def __init__(self) -> None:
        self.connected = True
        self.callbacks: list[Callback] = []

    def set_mode(self, _pin, _mode):
        pass
    def set_pull_up_down(self, _pin, _pull):
        pass

    def read(self, pin):
        return pygame.key.get_pressed()[PIN_TO_KEY[pin]] if pin in PIN_TO_KEY else 0

    def callback(self, pin, edge, func):
        if pin not in PIN_TO_KEY:
            raise NotImplementedError
        new_callback = Callback(func, self._remove_callback, edge, pin, self.read(pin))
        self.callbacks.append(new_callback)
        return new_callback

    def _remove_callback(self, _callback: Callback):
        try:
            self.callbacks.remove(_callback)
        except ValueError:
            logging.error("Multiple calls to callback.cancel()")

class PigpioWrapper(pigpio.pi):
    # pylint: disable-next=super-init-not-called
    def __init__(self, keyboard):
        self.keyboard = keyboard

    def __getattribute__(self, attr):
        return object.__getattribute__(self, "keyboard").__getattribute__(attr)

class PygameEmulator(luma_pygame):
    def __init__(self, width=128, height=64, rotate=0, mode="RGB", transform="scale2x", scale=2, frame_rate=60, **kwargs):
        super().__init__(width, height, rotate, mode, transform, scale, frame_rate, **kwargs)
        self.quit = False
        self._lock = Lock()

    def get_pygame(self):
        return self._pygame

    def abort(self):
        with self._lock:
            if not self.quit:
                self.quit = True

    def _abort(self):
        return False

    def display(self, image):
        with self._lock:
            if not self.quit:
                super().display(image)

#pylint: disable=invalid-name
def ConsoleDisplay():
    return partial(ScreenDisplay,
        Terminal(asciiblock(320, 120), font=ImageFont.truetype("DejaVuSansMono.ttf", 24)))
#pylint: enable=invalid-name


if __name__ == "__main__":
    main()
