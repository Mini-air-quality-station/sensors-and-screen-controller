import os
from typing import Literal

class BaseDisplayHandler:
    """ Base Display Handler that does nothing """
    # pylint: disable=unused-argument
    def __init__(self) -> None:
        self.rows = 4
    def clear(self, layer: Literal["text", "top", "all"] = "text"):
        """ @brief clear text/top layer/all. """
    def push_back(self, text: str):
        """ @brief add next row of text. """
    def push_front(self, text: str):
        """ @brief add text to top. """
    def highlight_text(self, row: int):
        """ @brief highlight one row """
    def update_row(self, row: int, text: str):
        """ @brief update text displayed on row """

class ConsoleDisplay(BaseDisplayHandler):
    """ Display text on console """
    def __init__(self, rows: int = 4) -> None:
        super().__init__()
        self.rows = rows
        self._text_buf: list[str] = []
        self.highlight = -1

    def clear(self, _: Literal["text", "top", "all"] = "text"):
        os.system("clear")
        self.highlight = -1
        self._text_buf = []

    def redraw(self):
        os.system("clear")
        for index, row in enumerate(self._text_buf):
            highlight = ">" if index == self.highlight else " "
            print(f"{highlight}{row}")

    def push_back(self, text: str):
        self._text_buf.append(text)
        if len(self._text_buf) > self.rows:
            self._text_buf.pop(0)
            self.redraw()
        else:
            highlight = ">" if self.highlight == len(self._text_buf) - 1 else " "
            print(f"{highlight}{text}")

    def push_front(self, text: str):
        self._text_buf.insert(0, text)
        if len(self._text_buf) > self.rows:
            self._text_buf.pop()
        self.redraw()

    def highlight_text(self, row: int):
        if self.highlight != row:
            self.highlight = row
            if 0 <= self.highlight < len(self._text_buf):
                self.redraw()

    def update_row(self, row: int, text: str):
        if row < len(self._text_buf):
            self._text_buf[row] = text
        self.redraw()
