from menu import CallableMenuElement, MenuList, TickMenu

SENSOR_MENU = MenuList("", [
    MenuList("Network", [
        MenuList("IP", [
            CallableMenuElement("Mask")
        ])
    ]),
    TickMenu("TAK/NIE"),
    MenuList("Empty1", [CallableMenuElement("Empty1")]),
    MenuList("Empty2", [CallableMenuElement("Empty2")]),
    MenuList("Empty3", [CallableMenuElement("Empty3")]),
    MenuList("Empty4", [CallableMenuElement("Empty4")]),
    CallableMenuElement("Empty5"),
    CallableMenuElement("Empty6"),
    CallableMenuElement("Empty7"),
    CallableMenuElement("Empty8"),
    CallableMenuElement("Empty9"),
    CallableMenuElement("Empty10"),
    CallableMenuElement("Empty11")
])