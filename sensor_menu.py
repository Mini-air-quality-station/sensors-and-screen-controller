from menu import CallableMenuElement, FreqencyChoice, MenuList, TickMenu, PoweroffMenu, RebootMenu
from util import SensorType

def get_menu(config_file: str, config_section: str):
    return MenuList("", [
        MenuList("Network", [
            MenuList("IP", [
                CallableMenuElement("Mask")
            ])
        ]),
        MenuList("Display frequency", [
            TickMenu("1 s"),
            TickMenu("2 s"),
            TickMenu("3 s"),
            TickMenu("4 s")
        ]),
        MenuList("Screensaver frequency", [
            TickMenu("1 s"),
            TickMenu("2 s"),
            TickMenu("3 s"),
            TickMenu("4 s")
        ]),
        FreqencyChoice("Humidity Frequency", config_file, config_section, SensorType.HUMIDITY.value, [1,2,3,4,5,10]),
        MenuList("Measurements", [
            MenuList("Temperature", [
                TickMenu("Yes"),
                TickMenu("No")
            ]),
            MenuList("Humidity", [
                TickMenu("Yes"),
                TickMenu("No")
            ]),
            MenuList("Pressure", [
                TickMenu("Yes"),
                TickMenu("No")
            ]),
            MenuList("PM", [
                TickMenu("Yes"),
                TickMenu("No")
            ])
        ]),
        RebootMenu("Reboot"),
        PoweroffMenu("Power off")
    ])
