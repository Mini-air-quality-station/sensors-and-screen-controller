from __future__ import annotations
from abc import ABC, abstractmethod
import logging
import signal
from threading import RLock
from enum import Enum
from datetime import datetime
import os
import time
from util import ConfigManager, RepeatTimer, SensorType, SensorReadings, Key
from display import ScreenDisplay

CONFIG_SECTION = "sensors_config"
INTERNAL_CONFIG_SECTION = "display"
INTERNAL_CONFIG_FILE = "./config.ini"

def get_internal_config_value(key: str):
    return ConfigManager.get_config_value(INTERNAL_CONFIG_FILE,
                                          INTERNAL_CONFIG_SECTION,
                                          key,
                                          True)

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
        self.display.print_lines(display_str, highlight=self._display_row(self.selected))

class View(Enum):
    DATE = 0
    DUST = 1
    TEMP_PRES_HUMI = 2
    def next(self):
        return View(self.value + 1 if self.value < 2 else 0)
    def prev(self):
        return View(self.value - 1 if self.value > 0 else 2)

class Interface:
    def __init__(self,*, menu: Menu, sensor_readings: SensorReadings, display: ScreenDisplay) -> None:
        self._root_menu = menu
        self._current_menu : Menu | None = None
        self._display = display
        self._lock = RLock()
        self._root_menu.set_display(display)
        self._readings = sensor_readings
        self.view = View.DATE
        self.dust_view = [SensorType.PM1, SensorType.PM2_5, SensorType.PM10]
        self.temp_view = [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.PRESSURE]
        view_period = get_internal_config_value("view_period")
        view_period = int(view_period) if view_period else 3
        self.view_timer = RepeatTimer(view_period, self.next_view)
        self.view_timer.start()
        self.display_off = False
        self._display.turn_on()
        self.show_data()

    def next_view(self):
        with self._lock:
            if self._current_menu is None and not self.display_off:
                self.view = self.view.next()
                self.display_view()

    def close(self):
        self.view_timer.cancel()
        self.view_timer.join(1)
        self._display.clear()
        self._display.turn_off()

    def key_press(self, key: Key, long_press: bool) -> None:
        """@brief react on pressed button"""
        with self._lock, self._display:
            if long_press:
                if key is Key.CANCEL:
                    self.display_off = True
                    self._display.turn_off()
                    while self._current_menu is not None:
                        self._current_menu = self._current_menu.key_press(Key.CANCEL)
            elif self.display_off:
                self.display_off = False
                self.show_data()
                self._display.turn_on()
            elif self._current_menu is None:
                if key is Key.OK:
                    self._current_menu = self._root_menu
                    self._current_menu.redraw()
                elif key is Key.UP:
                    self.view = self.view.prev()
                    self.view_timer.reset()
                    self.display_view()
                elif key is Key.DOWN:
                    self.view = self.view.next()
                    self.view_timer.reset()
                    self.display_view()
            else:
                self._current_menu = self._current_menu.key_press(key)
                if self._current_menu is None:
                    self.show_data()

    def show_data(self):
        """@brief show sensor data"""
        with self._lock:
            self._current_menu = None
            self.view = View.DATE
            self.view_timer.reset(int(get_internal_config_value("view_period")))
            self.display_view()

    def display_view(self):
        def get_color(value: int, colors: list[tuple[int|float, str]]):
            last_color = colors[0][1]
            for threshold, color in colors:
                if value < threshold:
                    break
                else:
                    last_color = color
            return last_color
                
        with self._lock, self._display:
            self._display.clear()
            if self.view == View.DATE:
                hours = datetime.now().strftime("%I:%M %p")
                day_name = datetime.today().strftime('%a')
                day = datetime.now().day
                month = datetime.now().strftime('%b')
                year = datetime.now().year
                date = f"{day_name}, {day} {month} {year}"
                middle_row = int(self._display.rows/2)

                self._display.update_row(middle_row - 1, hours, col=int((self._display.cols - len(hours))/2))
                self._display.update_row(middle_row, date, col=int((self._display.cols - len(date))/2), fill=False)
                self._display.reset()
            elif self.view == View.DUST:
                thresholds = {
                    SensorType.PM1: ("PM1", [(float("-inf"), "green"), (7, "yellow"), (25, "red")]),
                    SensorType.PM2_5: ("PM2.5", [(float("-inf"), "green"), (35, "yellow"), (75, "red")]),
                    SensorType.PM10: ("PM10", [(float("-inf"), "green"), (50, "yellow"), (110, "red")])
                }
                show = [measurement for measurement in self.dust_view
                        if bool(int(get_internal_config_value(measurement.name)))]
                if not show:
                    self.next_view()
                    return
                
                for i, sensor_type in enumerate(show):
                    value = self._readings.get(sensor_type)
                    string = f"{thresholds[sensor_type][0]} = {value}"
                    row = int(((i + 1) * self._display.rows / (len(show) + 1)))
                    self._display.update_row(row, string, col=2)
                    self._display.background_color(get_color(value, thresholds[sensor_type][1]))
                    self._display.update_row(row, "μg/m³", col=3 + len(string), fill=False)
                    self._display.reset()
            else:
                units = [' °C', '%', ' hPa']
                show = [measurement for measurement in zip(self.temp_view, units)
                        if bool(int(get_internal_config_value(measurement[0].name)))]
                if not show:
                    self.next_view()
                    return
                for i, (sensor_type, unit) in enumerate(show):
                    self._display.update_row(
                        int(((i + 1) * self._display.rows / (len(show) + 1))),
                        f"{sensor_type.name.capitalize()} = {self._readings.get(sensor_type)}{unit}",
                        col=2
                    )

    def update_sensor(self, sensor_type: SensorType):
        """@brief update sensor sensor_type if currently shown on screen"""
        with self._lock, self._display:
            if self._current_menu is None:
                if self.view == View.DUST and sensor_type in self.dust_view:
                    self.display_view()
                elif self.view == View.TEMP_PRES_HUMI and sensor_type in self.temp_view:
                    self.display_view()

class OnOffConfig(CallableMenuElement):
    def __init__(self, display_str: str, config_value) -> None:
        self.base_display_str = display_str
        self.config_value = config_value
        on_off = get_internal_config_value(config_value)
        if on_off is None:
            self.on_off = True
            ConfigManager.update_config_values(INTERNAL_CONFIG_FILE,
                                               INTERNAL_CONFIG_SECTION,
                                               {config_value: str(int(True))},
                                               True)
        else:
            self.on_off = bool(int(on_off))
        super().__init__(f"{display_str}: {'ON' if self.on_off else 'OFF'}")

    def call(self):
        self.on_off = not self.on_off
        ConfigManager.update_config_values(INTERNAL_CONFIG_FILE,
                                           INTERNAL_CONFIG_SECTION,
                                           {self.config_value: str(int(self.on_off))},
                                           True)
        self.display_str = f"{self.base_display_str}: {'ON' if self.on_off else 'OFF'}"

class PoweroffMenu(CallableMenuElement):
    def call(self):
        signal.raise_signal(signal.SIGINT)
        time.sleep(2.5)
        os.system("sudo shutdown now -h")

class RebootMenu(CallableMenuElement):
    def call(self):
        signal.raise_signal(signal.SIGINT)
        time.sleep(2.5)
        os.system("sudo reboot")

class FreqencyChoice(Menu):
    def __init__(self, display_str, config_file, config_section, config_key: str, frequency_list: list[int]):
        super().__init__("")

        self.config_file = config_file
        self.config_section = config_section
        self.config_key = config_key
        self.frequency_list = frequency_list
        self.base_display_str = display_str
        config_val = ConfigManager.get_config_value(config_file, config_section, config_key)
        try:
            # index of current freq
            self.current_frequency = int(frequency_list.index(int(config_val))) if config_val else 0
        except ValueError:
            logging.warning("%s: [%s][%s] error", config_file, config_section, config_key)
            self.current_frequency = 0
        self.new_frequency = self.current_frequency

        self._update_display_string()

    def _update_display_string(self):
        self.display_str = f"{self.base_display_str}: {self.frequency_list[self.current_frequency]}s"

    def key_press(self, key: Key) -> Menu | None:
        if key == Key.CANCEL:
            self.new_frequency = self.current_frequency
            if self.parent:
                self.parent.redraw()
            return self.parent
        if key == Key.UP:
            if self.new_frequency > 0:
                self.new_frequency -= 1
            else:
                self.new_frequency = len(self.frequency_list) - 1 if len(self.frequency_list) else 0
            self.redraw()
            return self
        if key == Key.DOWN:
            if self.new_frequency < len(self.frequency_list) - 1:
                self.new_frequency += 1
            else:
                self.new_frequency = 0
            self.redraw()
            return self
        else: #Key.OK
            self.current_frequency = self.new_frequency
            self._update_display_string()
            ConfigManager.update_config_values(
                self.config_file,
                self.config_section,
                {self.config_key: str(self.frequency_list[self.current_frequency])}
            )
            if self.parent:
                self.parent.redraw()
            return self.parent

    def redraw(self) -> None:
        self.display.clear()
        self.display.update_row(0, self.base_display_str)
        self.display.update_row(1, "^", col=2)
        self.display.update_row(2, f"{self.frequency_list[self.new_frequency]}s".rjust(4))
        self.display.update_row(3, "v", col=2)
