from menu import CallableMenuElement, MenuList, TickMenu, PoweroffMenu, RebootMenu

SENSOR_MENU = MenuList("", [
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
    MenuList("Measurement frequency", [
        TickMenu("1 s"),
        TickMenu("2 s"),
        TickMenu("3 s"),
        TickMenu("4 s"),
        TickMenu("5 s")
    ]),
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