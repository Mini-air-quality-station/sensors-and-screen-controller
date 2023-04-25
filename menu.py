from __future__ import annotations
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
        self.selected: int = 0
        self.selected_on_display: int = self.selected

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

    def key_press(self, key: Key) -> Menu | None:
        return_menu: Menu | None = None
        if key is Key.UP:
            if self.selected > 0:
                self.selected -= 1
                if self.selected_on_display == 0:
                    self.display.push_front(self.menu_elements[self.selected].display_str)
                else:
                    self.selected_on_display -= 1
                self.display.highlight_text(self.selected_on_display)
            return_menu = self

        if key is Key.DOWN:
            if self.selected + 1 < len(self.menu_elements):
                self.selected += 1
                if self.selected_on_display + 1 >= self.display.rows:
                    self.display.push_back(self.menu_elements[self.selected].display_str)
                else:
                    self.selected_on_display += 1
                self.display.highlight_text(self.selected_on_display)
            return_menu = self

        if key is Key.CANCEL:
            self.selected = 0
            self.selected_on_display = 0
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
                        self.display.update_row(self.selected_on_display, selected_menu.display_str)
            else:
                return_menu = self

        return return_menu

    def redraw(self) -> None:
        self.display.clear()
        self.display.highlight_text(self.selected_on_display)
        start_from = max(0, self.selected - self.selected_on_display)
        for index in range(start_from, min(len(self.menu_elements), self.display.rows + start_from)):
            self.display.push_back(self.menu_elements[index].display_str, False)

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
        for sensor_type in SensorType:
            self._display.push_back(f"{sensor_type.name} = {self._readings.get(sensor_type)}")

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