import time
import digitalio
import board
from luma.core.interface.serial import i2c
from luma.core.device import device as luma_device
from luma.oled.device import ssd1306
from adafruit_dht import DHT22

from display import ScreenDisplay
from menu import Interface, CallableMenuElement, MenuList, Key

def get_ssd1306() -> luma_device:
    return ssd1306(i2c(port=1, address=0x3C))

class ReverseName(CallableMenuElement):
    def __init__(self, name: str) -> None:
        super().__init__(f"Nazwisko: {name}")
        self.name = name

    def call(self):
        self.name = self.name[::-1]
        self.display_str = f"Nazwisko: {self.name}"

class Ticker(CallableMenuElement):
    def __init__(self, display_str: str, ticked: bool = False) -> None:
        super().__init__(display_str)
        self.base_display_str = display_str
        self.ticked = ticked

    def call(self):
        self.ticked = not self.ticked
        self.display_str = f"{self.base_display_str} ✓" if self.ticked else self.base_display_str

def test_menu() -> Interface:
    menu = MenuList("", [
        MenuList("Network", [
            MenuList("IP", [
                ReverseName("Iwanicki")]),
            CallableMenuElement("Mask")]),
        MenuList("Sensors", [
            Ticker("TAK/NIE")]),
        MenuList("Empty0"),
        MenuList("Empty1", [CallableMenuElement("Empty1")]),
        MenuList("Empty2", [CallableMenuElement("Empty2")]),
        MenuList("Empty3", [CallableMenuElement("Empty3")]),
        MenuList("Empty4", [CallableMenuElement("Empty4")]),
        ])
    return Interface(menu=menu, display=ScreenDisplay(get_ssd1306()))

class Button:
    def __init__(self, pin) -> None:
        self.gpio = digitalio.DigitalInOut(pin)
        self.gpio.switch_to_input(digitalio.Pull.DOWN)
        self.last_state = self.gpio.value

    def pushed(self) -> bool:
        current_value = self.gpio.value
        return_value = False
        if current_value is True and current_value != self.last_state:
            return_value = True
        self.last_state = current_value
        return return_value

def main():
    buttons = {Key.UP: Button(board.D5), Key.DOWN: Button(board.D19), Key.CANCEL: Button(board.D6), Key.OK: Button(board.D13)}
    interface = test_menu()
    dht = DHT22(board.D4)
    now = time.time()

    while True:
        for key, button in buttons.items():
            if (button.pushed()):
                print(f"pushed: {key}")
                if interface.menu.current_menu is None and key == Key.CANCEL:
                    return
                interface.key_press(key)
            if interface.menu.current_menu is None and time.time() - now > 2:
                now = time.time()
                interface.display.clear()
                try:
                    temperature = dht.temperature
                    humidity = dht.humidity
                    interface.display.push_back(f"Temperature: {temperature}°C")
                    interface.display.push_back(f"Humidity: {humidity}%")
                except RuntimeError:
                    pass
                
if __name__ == "__main__":
    main()
