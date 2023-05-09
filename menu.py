from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from threading import RLock
from enum import Enum
from datetime import datetime
import configparser
import os
import pytz
from util import ConfigManager, RepeatTimer, SensorType, SensorReadings, Key
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

class View(Enum):
    DATE = 0
    DUST = 1
    TEMP_PRES_HUMI = 2
    def next(self):
        return list(self.__class__)[self.value + 1 if self.value < 2 else 0]

class Interface:
    def __init__(self,*, menu: Menu, sensor_readings: SensorReadings, display: ScreenDisplay) -> None:
        self._root_menu = menu
        self._current_menu : Menu | None = None
        self._display = display
        self._lock = RLock()
        self._root_menu.set_display(display)
        self._readings = sensor_readings
        self.show_data()
        self.view = View.DATE
        self.dust_view = [SensorType.PM1, SensorType.PM2_5, SensorType.PM10]
        self.temp_view = [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.PRESSURE]
        self.view_timer = RepeatTimer(3, self.next_view)
        self.view_timer.start()

    def next_view(self):
        with self._lock:
            if self._current_menu is None:
                self.view = self.view.next()
                self.display_view()

    def close(self):
        self.view_timer.cancel()
        self.view_timer.join()

    def key_press(self, key: Key) -> None:
        """@brief react on pressed button"""
        with self._lock, self._display:
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
        with self._lock:
            self._current_menu = None
            self.view = View.DATE
            self.display_view()

    def display_view(self):
        with self._lock, self._display:
            self._display.clear()
            if self.view == View.DATE:
                hours = datetime.now(pytz.timezone('Europe/warsaw')).strftime("%I:%M %p")
                day_name = datetime.today().strftime('%a')
                day = datetime.now().day
                month = datetime.now().strftime('%b')
                year = datetime.now().year
                date = f"{day_name}, {day} {month} {year}"

                self._display.update_row(3, hours, col=6)
                self._display.update_row(4, date, col=4, fill=False)
                self._display.reset()
            elif self.view == View.DUST:
                names = ['PM 1', 'PM 2.5', 'PM 10']
                for i, sensor_type in enumerate(self.dust_view):
                    self._display.update_row(i * 2 + 1, f"{names[i]} = {self._readings.get(sensor_type)} μg/m3", col=2)
            else:
                names = ['Temperature', 'Humidity', 'Pressure']
                units = ['C', '%', 'hPa']
                for i, sensor_type in enumerate(self.temp_view):
                    self._display.update_row(i * 2 + 1, f"{names[i]} = {self._readings.get(sensor_type)} {units[i]}", col=2)

    def update_sensor(self, sensor_type: SensorType):
        """@brief update sensor sensor_type if currently shown on screen"""
        with self._lock, self._display:
            if self._current_menu is None:
                if self.view == View.DUST and sensor_type in self.dust_view:
                    self.display_view()
                    #self._display.update_row(self.dust_view.index(sensor_type), f"{sensor_type.name} = {self._readings.get(sensor_type)}")
                elif self.view == View.TEMP_PRES_HUMI and sensor_type in self.temp_view:
                    self.display_view()
                    #self._display.update_row(self.temp_view.index(sensor_type), f"{sensor_type.name} = {self._readings.get(sensor_type)}")

class TickMenu(CallableMenuElement):
    def __init__(self, display_str: str, ticked: bool = False) -> None:
        super().__init__(display_str)
        self.base_display_str = display_str
        self.ticked = ticked

    def call(self):
        self.ticked = not self.ticked
        self.display_str = f"{self.base_display_str} ✓" if self.ticked else self.base_display_str

class PoweroffMenu(CallableMenuElement):
    def __init__(self, display_str: str) -> None:
        super().__init__(display_str)
    
    def call(self):
        os.system("sudo shutdown now -h")

class RebootMenu(CallableMenuElement):
    def __init__(self, display_str: str) -> None:
        super().__init__(display_str)

    def call(self):
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
        # index of current freq
        try:
            self.current_frequency = int(frequency_list.index(int(config_val))) if config_val else 0
        except ValueError:
            self.current_frequency = 0
        self.new_frequency = self.current_frequency

        self._update_display_string()

    def _update_display_string(self):
        self.display_str = f"{self.base_display_str} {self.frequency_list[self.current_frequency]}s"

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
        self.display.update_row(4, "<", col=1)
        self.display.update_row(4, str(self.frequency_list[self.new_frequency]), col=10)
        self.display.update_row(4, ">", col=19)

class MeasurementsFrequency(CallableMenuElement):
    def __init__(self, display_str: str, ticked: bool = False) -> None:
        super().__init__(display_str)
        self.base_display_str = display_str
        self.ticked = ticked
    
    def call(self):
        self.ticked = not self.ticked
        if self.ticked:
            self.display_str = f"{self.base_display_str} ✓"

            # nie działa jak coś 
            config = configparser.ConfigParser()
            config['sensors_config']['humidity_dht22_freq'] = int(self.display_str[0])
            config['sensors_config']['particle_pm1_pmsa003-c_freq'] = int(self.display_str[0])
            config['sensors_config']['particle_pm25_pmsa003-c_freq'] = int(self.display_str[0])
            config['sensors_config']['particle_pm10_pmsa003-c_freq'] = int(self.display_str[0])
            config['sensors_config']['pressure_bmp280_freq'] = int(self.display_str[0])
            config['sensors_config']['temperature_bmp280_freq'] = int(self.display_str[0])
            config['sensors_config']['temperature_dht22_freq'] = int(self.display_str[0])

            with open("/etc/mini-air-quality/sensors_config.ini", 'w') as configfile:
                config.write(configfile)
        else:
            self.display_str = self.base_display_str
