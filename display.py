from typing import Literal
from PIL import ImageFont
from luma.core.device import device as luma_device
from luma.core.render import canvas

from base_display import BaseDisplayHandler

class ScreenDisplay(BaseDisplayHandler):
    def __init__(self, display: luma_device) -> None:
        super().__init__()
        self._font = ImageFont.truetype("DejaVuSans.ttf", 12)
        self._font_height = self._font.getsize("M")[1]
        self.rows = display.height // self._font_height
        self.highlight = -1
        self._text_lines: list[str] = []
        self._display_device = display
        self._display_device.show()

    def clear(self, layer: Literal["text", "top", "all"] = "text"):
        if layer == "all" or layer == "text":
            self._display_device.clear()
            self._text_lines.clear()

    def push_back(self, text: str):
        redraw = False
        if len(self._text_lines) >= self.rows:
            self._text_lines.pop(0)
            redraw = True
        self._text_lines.append(text)
        # TODO: only redraw when redraw is true if false update part of screen
        self._redraw()

    def push_front(self, text: str):
        if len(self._text_lines) >= self.rows:
            self._text_lines.pop()
        self._text_lines.insert(0, text)
        self._redraw()

    def highlight_text(self, row: int):
        self.highlight = row
        self._redraw() # TODO: redraw only rows that get/stop being highlighted

    def _redraw(self):
        self._display_device.clear()
        with canvas(self._display_device) as draw:
            for index, line in enumerate(self._text_lines):
                fill = "white"
                if index == self.highlight:
                    fill = "black"
                    draw.rectangle((
                        0, index * self._font_height,
                        self._display_device.width, (index + 1) * self._font_height), outline="white", fill="white")
                draw.text((0, index * self._font_height), line, fill=fill, font=self._font)

    def update_row(self, row: int, text: str):
        self._text_lines[row] = text
        self._redraw() # TODO: redraw only updated row