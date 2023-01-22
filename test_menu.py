from menu import CallableMenuElement, Key, MenuList, Interface
from base_display import ConsoleDisplay

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

def test1() -> Interface:
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
    return Interface(menu=menu, display=ConsoleDisplay())

def test2() -> Interface:
    menu = MenuList("")
    for i in range(10):
        child = MenuList(f"MenuList {i}")
        menu.add_element(child)
        for j in range(10):
            child.add_element(CallableMenuElement(f"CallableMenuElement {i}:{j}"))

    return Interface(menu=menu, display=ConsoleDisplay())

def main(menu: Interface):
    input_string = ""
    while input_string != "EXIT":
        try:
            input_string = input("[UP/DOWN/OK/CANCEL/EXIT]: ").upper()
            menu.key_press(Key[input_string])
        except KeyError:
            ...

if __name__ == "__main__":
    main(test1())
