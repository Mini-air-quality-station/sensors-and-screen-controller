import logging
import time
from typing import Literal
from luma.core.virtual import terminal as luma_terminal
from luma.lcd.device import st7789
from luma.core.interface.serial import spi
from PIL import ImageFont

class Terminal(luma_terminal):
    def __init__(self, device, font=None, color="white", bgcolor="black", tabstop=4, line_height=None, animate=False, word_wrap=False):
        super().__init__(device, font, color, bgcolor, tabstop, line_height, animate, word_wrap)
        self.scroll = True

    def goto(self, x: int, y: int):
        if (0 <= x < self.width) and (0 <= y < self.height):
            #pylint: disable=attribute-defined-outside-init
            self._cx = self._cw * x
            self._cy = self._ch * y
            #pylint: enable=attribute-defined-outside-init

    def println(self, text="", scroll = True):
        self.scroll = scroll
        super().println(text)
        self.scroll = True

    def newline(self):
        if self.scroll:
            super().newline()
        else:
            self.carriage_return()
            if self._cy + (2 * self._ch) < self._device.height:
                self._cy += self._ch
                self.flush()
            if self.animate:
                time.sleep(0.2)


class ScreenDisplay:
    def __init__(self, terminal: Terminal) -> None:
        self.highlight = -1
        self._text_lines: list[str] = []
        self._display = terminal
        self.rows = self._display.height
        #self._display._device.show()
    
    def clear(self, layer: Literal["text", "top", "all"] = "text"):
        if layer in {"all", "text"}:
            self._display.clear()
            self._text_lines.clear()
            self.highlight = -1

    def push_back(self, text: str, scroll = True):
        if len(self._text_lines) >= self._display.height:
            self._text_lines.pop(0)
        self._text_lines.append(text)
        self._display.println(text, scroll)

    def push_front(self, text: str):
        if len(self._text_lines) >= self._display.height:
            self._text_lines.pop()
        self._text_lines.insert(0, text)

        self._display.clear()
        for index, line in enumerate(self._text_lines):
            if index == self.highlight:
                self._display.reverse_colors()
                self._display.println(line)
                self._display.reverse_colors()
            else:
                self._display.println(line)

    def highlight_text(self, row: int):
        logging.info("Row: %d, current_highlight: %d", row, self.highlight)
        if 0 <= row < len(self._text_lines):
            tmp = self.highlight
            self.highlight = row
            if self.highlight >= 0:
                self._redraw_row(tmp)
            self._redraw_row(row)

    def _redraw_row(self, row: int):
        self._display.goto(0, row)
        logging.debug("text[%i]=%s", row, self._text_lines[row])
        if row == self.highlight:
            self._display.reverse_colors()
            self._display.println(self._text_lines[row].ljust(self._display.width))
            self._display.reverse_colors()
        else:
            # TODO: add correctly working ljust
            self._display.println(self._text_lines[row].ljust(self._display.width))

    def update_row(self, row: int, text: str):
        self._text_lines[row] = text
        self._redraw_row(row)

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
            font=ImageFont.truetype("DejaVuSans.ttf", 24)
        )
    )