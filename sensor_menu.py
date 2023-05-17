from menu import FreqencyChoice, MenuList, RebootMenu, OnOffConfig, PoweroffMenu
from util import SensorType


def get_menu():
    return MenuList("", [
            MenuList("Measurements Period", [
                FreqencyChoice("Humidity", False, SensorType.HUMIDITY.value, [5, 10, 15, 30, 60, 120, 240]),
                FreqencyChoice("Temperature", False, SensorType.TEMPERATURE.value, [5, 10, 15, 30, 60, 120, 240]),
                FreqencyChoice("Pressure", False, SensorType.PRESSURE.value, [1, 2, 3, 5, 10, 15, 30, 60, 120, 240]),
                FreqencyChoice("PM1", False, SensorType.PM1.value, [3, 5, 10, 15, 30, 60, 120, 240]),
                FreqencyChoice("PM2.5", False, SensorType.PM2_5.value, [3, 5, 10, 15, 30, 60, 120, 240]),
                FreqencyChoice("PM10", False, SensorType.PM10.value, [3, 5, 10, 15, 30, 60, 120, 240]),
            ]),
            MenuList("Display Settings", [
                FreqencyChoice("View Period", True, "view_period", [4, 5, 10, 20]),
                MenuList("Show Measurements", [
                    OnOffConfig("Temperature", SensorType.TEMPERATURE.name),
                    OnOffConfig("Humidity", SensorType.HUMIDITY.name),
                    OnOffConfig("Pressure", SensorType.PRESSURE.name),
                    OnOffConfig("PM1", SensorType.PM1.name),
                    OnOffConfig("PM2.5", SensorType.PM2_5.name),
                    OnOffConfig("PM10", SensorType.PM10.name),
                ]),
            ]),
            RebootMenu("Reboot"),
            PoweroffMenu("Power off")
        ]
    )
