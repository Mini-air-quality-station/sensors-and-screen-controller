from menu import (
    CONFIG_SECTION, FreqencyChoice, MenuList,
    OnOffConfig, PoweroffMenu, RebootMenu, INTERNAL_CONFIG_FILE, INTERNAL_CONFIG_SECTION
)
from util import SensorType

def get_menu(config_file: str):
    return MenuList("",
        [
            MenuList("Measurements Period", [
                FreqencyChoice("Humidity", config_file, CONFIG_SECTION,
                               SensorType.HUMIDITY.value, [5,10,15,30,60,120,240]),
                FreqencyChoice("Temperature", config_file, CONFIG_SECTION,
                               SensorType.TEMPERATURE.value, [5,10,15,30,60,120,240]),
                FreqencyChoice("Pressure", config_file, CONFIG_SECTION,
                               SensorType.PRESSURE.value, [1,2,3,5,10,15,30,60,120,240]),
                FreqencyChoice("PM1", config_file, CONFIG_SECTION,
                               SensorType.PM1.value, [3,5,10,15,30,60,120,240]),
                FreqencyChoice("PM2.5", config_file, CONFIG_SECTION,
                               SensorType.PM2_5.value, [3,5,10,15,30,60,120,240]),
                FreqencyChoice("PM10", config_file, CONFIG_SECTION,
                               SensorType.PM10.value, [3,5,10,15,30,60,120,240]),
            ]),
            MenuList("Display Settings", [
                FreqencyChoice("View Period", INTERNAL_CONFIG_FILE, INTERNAL_CONFIG_SECTION,
                               "view_period", [4,5,10,20]),
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
