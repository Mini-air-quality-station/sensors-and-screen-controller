from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from threading import Lock
from util import SensorType, SensorReadings, Key
from display import ScreenDisplay

class CallableMenuElement:
    def __init__(self, display_str: str) -> None:
        self.parent: Menu | None = None
        self.display_str = display_str

    def call(self) -> None:
        """ Do something when called from parent Menu """

class Menu(ABC):
    def __init__(self, display_str: str):
        super().__init__()
        self.parent: Menu | None = None
        self.display_str = display_str
        self.display: ScreenDisplay

    @abstractmethod
    def key_press(self, key: Key) -> Menu | None:
        """
        @brief Send information about key press to menu.
        @return active(currently to be displayed) menu or None if closed
        """

    @abstractmethod
    def redraw(self) -> None:
        """ redraw menu on display """

    def set_display(self, display: ScreenDisplay):
        self.display = display

class MenuList(Menu):
    def __init__(self, display_str: str, elements: list[Menu | CallableMenuElement] | None = None):
        super().__init__(display_str)
        self.menu_elements: list[Menu | CallableMenuElement] = elements or []
        for element in self.menu_elements:
            element.parent = self
        self.start_row: int = 0
        self.selected: int = 0
        #self.selected_on_display: int = self.selected

    def add_element(self, menu_element: Menu | CallableMenuElement):
        if isinstance(menu_element, Menu):
            menu_element.set_display(self.display)
        menu_element.parent = self
        self.menu_elements.append(menu_element)

    def set_display(self, display: ScreenDisplay):
        """Set display recursively for every menu element"""
        super().set_display(display)
        for element in self.menu_elements:
            if isinstance(element, Menu):
                element.set_display(display)
    
    def _display_row(self, menu_index):
        return menu_index - self.start_row
    
    def change_highlight(self, new_highlight: int, old_highlight: int):
        self.display.update_row(
            self._display_row(old_highlight),
            self.menu_elements[old_highlight].display_str,
            highlight=False
        )
        self.display.update_row(
            self._display_row(new_highlight),
            self.menu_elements[new_highlight].display_str,
            highlight=True
        )

    def key_press(self, key: Key) -> Menu | None:
        return_menu: Menu | None = None
        if key is Key.UP:
            if self.selected > 0:
                self.selected -= 1
                if self.start_row > self.selected:
                    self.start_row = self.selected
                    self.redraw()
                else:
                    self.change_highlight(self.selected, self.selected + 1)
            return_menu = self

        if key is Key.DOWN:
            if self.selected + 1 < len(self.menu_elements):
                self.selected += 1
                if self._display_row(self.selected) >= self.display.rows:
                    self.display.update_row(
                        self._display_row(self.selected) - 1,
                        self.menu_elements[self.selected - 1].display_str,
                        highlight=False
                    )
                    self.display.push_back(
                        self.menu_elements[self.selected].display_str,
                        highlight=True
                    )
                    self.start_row += 1
                else:
                    self.change_highlight(self.selected, self.selected - 1)
            return_menu = self

        if key is Key.CANCEL:
            self.selected = 0
            self.start_row = 0
            #self.selected_on_display = 0
            return_menu = self.parent
            if return_menu:
                return_menu.redraw()

        if key is Key.OK:
            if self.selected < len(self.menu_elements):
                selected_menu = self.menu_elements[self.selected]
                if isinstance(selected_menu, Menu):
                    selected_menu.redraw()
                    return_menu = selected_menu
                else:
                    old_name = selected_menu.display_str
                    selected_menu.call()
                    return_menu = self
                    if old_name != selected_menu.display_str:
                        self.display.update_row(
                            self._display_row(self.selected),
                            selected_menu.display_str,
                            highlight=True
                        )
            else:
                return_menu = self

        return return_menu

    def redraw(self) -> None:
        display_str = [
            menu.display_str
            for menu in self.menu_elements[self.start_row : self.start_row + self.display.rows]
        ]
        logging.debug("start=%d\ndisplay_str=%s", self.start_row, str(display_str))
        self.display.print_lines(display_str, highlight=self._display_row(self.selected))

class Interface:
    def __init__(self,*, menu: Menu, sensor_readings: SensorReadings, display: ScreenDisplay) -> None:
        self._root_menu = menu
        self._current_menu : Menu | None = None
        self._display = display
        self._lock = Lock()
        self._root_menu.set_display(display)
        self._readings = sensor_readings
        self.show_data()

    def key_press(self, key: Key) -> None:
        """@brief react on pressed button"""
        with self._lock:
            if self._current_menu is None:
                if key is not Key.CANCEL:
                    self._current_menu = self._root_menu
                    self._current_menu.redraw()
            else:
                self._current_menu = self._current_menu.key_press(key)
                if self._current_menu is None:
                    self.show_data()

    def show_data(self):
        """@brief show sensor data"""
        self._current_menu = None
        self._display.clear()
        for i, sensor_type in enumerate(SensorType):
            self._display.update_row(i, f"{sensor_type.name} = {self._readings.get(sensor_type)}")

    def update_sensor(self, sensor_type: SensorType):
        """@brief update sensor sensor_type if currently shown on screen"""
        with self._lock:
            if self._current_menu is None:
                self._display.update_row(SensorType.index(sensor_type), f"{sensor_type.name} = {self._readings.get(sensor_type)}")

class TickMenu(CallableMenuElement):
    def __init__(self, display_str: str, ticked: bool = False) -> None:
        super().__init__(display_str)
        self.base_display_str = display_str
        self.ticked = ticked

    def call(self):
        self.ticked = not self.ticked
        self.display_str = f"{self.base_display_str} ✓" if self.ticked else self.base_display_str
