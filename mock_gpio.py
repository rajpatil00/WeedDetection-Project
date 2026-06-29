BCM = "BCM"
OUT = "OUT"
IN = "IN"
LOW = 0
HIGH = 1

def setmode(mode):
    pass

def setwarnings(warnings):
    pass

def setup(pin, mode):
    pass

def output(pin, state):
    pass

def cleanup():
    pass

class PWM:
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency

    def start(self, duty_cycle):
        pass

    def ChangeDutyCycle(self, duty_cycle):
        pass

    def stop(self):
        pass
