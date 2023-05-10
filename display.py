from __future__ import annotations
from typing import List
from luma.core.virtual import terminal as luma_terminal
from luma.lcd.device import st7789
from luma.core.interface.serial import spi
from PIL import ImageFont

class Terminal(luma_terminal):
    def __init__(self, device, font=None, color="white", bgcolor="blue", tabstop=4, line_height=None, animate=False, word_wrap=False):
        # if > 0 then don't send image to device
        self.context_manager_depth = 0
        self.scroll = False
        super().__init__(device, font, color, bgcolor, tabstop, line_height, animate, word_wrap)

    def goto(self, x: int, y: int):
        if (0 <= x < self.width) and (0 <= y < self.height):
            #pylint: disable=attribute-defined-outside-init
            self._cx = self._cw * x
            self._cy = self._ch * y
            #pylint: enable=attribute-defined-outside-init

    @property
    def x(self):
        return self._cx // self._cw

    @property
    def y(self):
        return self._cy // self._ch

    def println(self, text="", *, highlight = False, fill = True, scroll_first = False):
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

    def newline(self):
        if self.scroll or self.y + 1 < self.height:
            super().newline()
        else:
            self.flush()
            self._cy += self._ch

    def flush(self):
        if self.context_manager_depth == 0:
            super().flush()


class ScreenDisplay:
    def __init__(self, terminal: Terminal) -> None:
        self._display = terminal
        self.rows = self._display.height
        self.cols = self._display.width

    def __enter__(self):
        self._display.context_manager_depth += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._display.context_manager_depth -= 1
        self._display.flush()

    def clear(self):
        self._display.clear()

    def print_lines(self, lines: List[str], *, highlight=-1):
        self._display.goto(0, 0)
        for i, line in enumerate(lines):
            self._display.println(line, highlight=(i == highlight))
        # clear unused part of screen
        for _ in range(self.rows - len(lines)):
            self._display.println()

    def push_back(self, text: str, *, highlight = False):
        self._display.goto(0, self._display.height - 1)
        self._display.println(text, highlight=highlight, scroll_first=True)

    def update_row(self, row: int, text: str, *, col: int = 0, highlight: bool = False, fill: bool = True):
        self._display.goto(col, row)
        self._display.println(text, highlight=highlight, fill=fill)

    def foreground_color(self, value):
        self._display.foreground_color(value)

    def background_color(self, value):
        self._display.background_color(value)

    def reset(self):
        self._display.reset()

    def turn_on(self):
        device: st7789 = self._display._device #pylint: disable=protected-access
        device.backlight(True)
        device.show()

    def turn_off(self):
        device: st7789 = self._display._device #pylint: disable=protected-access
        device.backlight(False)
        device.hide()

#pylint: disable-next=invalid-name
def ST7789Display():
    return ScreenDisplay(
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
