from __future__ import annotations
from typing import List
from luma.core.virtual import terminal as luma_terminal
from luma.lcd.device import st7789, backlit_device
from luma.core.interface.serial import spi
from PIL import ImageFont


class Terminal(luma_terminal):
    def __init__(self, device: backlit_device, font=None, color="white", bgcolor="blue",
                 tabstop=4, line_height=None, animate=False, word_wrap=False):
        # if depth > 0 then don't flush (don't display on device just write to bitmap/image)
        self.context_manager_depth = 0
        self.scroll = False
        super().__init__(device, font, color, bgcolor, tabstop, line_height, animate, word_wrap)

    def goto(self, x: int, y: int) -> None:
        if (0 <= x < self.width) and (0 <= y < self.height):
            # pylint: disable=attribute-defined-outside-init
            self._cx = self._cw * x
            self._cy = self._ch * y
            # pylint: enable=attribute-defined-outside-init

    @property
    def x(self):
        return self._cx // self._cw

    @property
    def y(self):
        return self._cy // self._ch

    def println(self, text="", *, highlight=False, fill=True, scroll_first=False) -> None:
        if fill:
            text = text.ljust(self.width - self.x)
        if scroll_first:
            self.scroll = True
            self.newline()
            self.scroll = False
        if highlight:
            self.reverse_colors()
            super().println(text)
            self.reverse_colors()
        else:
            super().println(text)

    def newline(self) -> None:
        if self.scroll or self.y + 1 < self.height:
            super().newline()
        else:
            self.flush()
            self._cy += self._ch

    def flush(self) -> None:
        if self.context_manager_depth == 0:
            super().flush()

    def turn_on(self) -> None:
        self._device.backlight(True)
        self._device.show()

    def turn_off(self) -> None:
        self._device.backlight(False)
        self._device.hide()


class ScreenDisplay:
    def __init__(self, terminal: Terminal) -> None:
        self._display = terminal
        self.rows = self._display.height
        self.cols = self._display.width

    def __enter__(self) -> None:
        self._display.context_manager_depth += 1

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._display.context_manager_depth -= 1
        self._display.flush()

    def clear(self) -> None:
        self._display.clear()

    def print_lines(self, lines: List[str], *, highlight: int = -1) -> None:
        self._display.goto(0, 0)
        for i, line in enumerate(lines):
            self._display.println(line, highlight=(i == highlight))
        # clear unused part of screen
        for _ in range(self.rows - len(lines)):
            self._display.println()

    def push_back(self, text: str, *, highlight: bool = False) -> None:
        self._display.goto(0, self._display.height - 1)
        self._display.println(text, highlight=highlight, scroll_first=True)

    def update_row(self, row: int, text: str, *, col: int = 0, highlight: bool = False, fill: bool = True) -> None:
        self._display.goto(col, row)
        self._display.println(text, highlight=highlight, fill=fill)

    def foreground_color(self, value) -> None:
        self._display.foreground_color(value)

    def background_color(self, value) -> None:
        self._display.background_color(value)

    def reset(self) -> None:
        self._display.reset()

    def turn_on(self) -> None:
        self._display.turn_on()

    def turn_off(self) -> None:
        self._display.turn_off()


class ST7789Display(ScreenDisplay):
    def __init__(self) -> None:
        super().__init__(
            Terminal(
                st7789(
                    spi(gpio_DC=27, gpio_RST=17),
                    width=320,
                    height=240,
                    rotate=0,
                    active_low=False
                ),
                font=ImageFont.truetype("DejaVuSansMono.ttf", 24)
            )
        )
