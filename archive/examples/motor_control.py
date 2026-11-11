from rpi_hardware_pwm import HardwarePWM
import serial
import time
from textual.app import App, on
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Static, Input


class PID:
    def __init__(self, Kp=0.0, Ki=0.0, Kd=0.0, setpoint=0.0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, measurement, dt):
        error = self.setpoint - measurement
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt if dt > 0 else 0
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        self.prev_error = error
        return output

    def set_setpoint(self, setpoint):
        self.setpoint = setpoint


class ValueDisplay(Static):
    """A widget to display a labeled value."""
    value = reactive(None)

    def __init__(self, label: str, initial, id: str | None = None) -> None:
        self.label = label
        super().__init__(id=id)
        self.value = initial

    def watch_value(self, value) -> None:
        self.update(f"{self.label}{value}")


class MotorControlApp(App):
    """Textual app for motor control and serial monitoring."""
    CSS_PATH = "motor_control.tcss"

    def compose(self):
        yield Header()
        with Container(id="displays"):
            yield ValueDisplay("Counts: ", 0, id="counts")
            yield ValueDisplay("Rot: ", "0.00", id="rot")
            yield ValueDisplay("RPM Calc: ", "0.00", id="rpm_calc")
            yield ValueDisplay("RPM Received: ", "0.00", id="rpm_received")
            yield ValueDisplay("Distance: ", "0 mm", id="dist")
        with Container(id="controls"):
            yield Input(placeholder="Enter power (-100 to 100)", id="power_input")
            yield Button("Set Power", id="set_button")
        with Container(id="pid_controls"):
            yield Input(placeholder="Kp", id="kp_input")
            yield Input(placeholder="Ki", id="ki_input")
            yield Input(placeholder="Kd", id="kd_input")
            yield Button("Set PID Gains", id="set_gains")
            yield Input(placeholder="Desired RPM", id="setpoint_input")
            with Horizontal():
                yield Button("Set Setpoint", id="set_setpoint")
                yield Button("Enable PID", id="pid_toggle")       
        yield Button("Quit", id="quit_button")
        yield Footer()

    def on_mount(self) -> None:
        self.PWM_FREQUENCY = 50
        self.SERIAL_PORT = '/dev/ttyACM0'  # Change as needed
        self.BAUD_RATE = 115200
        self.TIMEOUT = 1
        self.stop_event = False

        self.pwm = HardwarePWM(pwm_channel=0, hz=self.PWM_FREQUENCY, chip=0)
        self.pwm.start(0)

        self.ser = serial.Serial(self.SERIAL_PORT, self.BAUD_RATE, timeout=self.TIMEOUT)
        self.title = f"Connected to {self.SERIAL_PORT} at {self.BAUD_RATE} baud."
        time.sleep(2)  # Wait for Arduino reset

        self.current_rpm = 0.0
        self.pid_enabled = False
        self.pid = PID()
        self.prev_rotations = 0.0
        self.prev_update_time = time.time()

        self.run_worker(self.read_serial_loop, thread=True)
        self.run_worker(self.pid_loop, thread=True)

    async def read_serial_loop(self) -> None:
        while True:
            if self.stop_event:
                break
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    parts = line.split(',')
                    if len(parts) == 4:
                        counts = int(parts[0])
                        rotations = float(parts[1])
                        rpm_received = float(parts[2])
                        distance_mm = int(parts[3])

                        self.call_from_thread(self.update_values, counts, rotations, rpm_received, distance_mm)
            except ValueError:
                pass  # Skip bad data

    def update_values(self, counts, rotations, rpm_received, distance_mm):
        current_time = time.time()
        dt = current_time - self.prev_update_time
        if dt > 0.001:
            rpm_calc = ((rotations - self.prev_rotations) / dt) * 60 / 4
            if rpm_calc == 0:
                rpm_calc = self.current_rpm  # Maintain last known if no change
        
        print(rotations, self.prev_rotations, rpm_calc)
        self.current_rpm = rpm_calc  # Using calculated for PID
        self.prev_rotations = rotations
        self.prev_update_time = current_time

        self.query_one("#counts").value = counts
        self.query_one("#rot").value = f"{rotations:.2f}"
        self.query_one("#rpm_calc").value = f"{rpm_calc:.2f}"
        self.query_one("#rpm_received").value = f"{rpm_received:.2f}"
        self.query_one("#dist").value = f"{distance_mm} mm"

    def pid_loop(self) -> None:
        last_time = time.time()
        while True:
            if self.pid_enabled:
                current_time = time.time()
                dt = current_time - last_time
                if dt > 0.001:
                    output = self.pid.compute(self.current_rpm, dt)
                    power = max(-100, min(100, output))
                    self.set_esc_power(power)
                last_time = current_time
            time.sleep(0.05)

    def set_esc_power(self, power: int):
        power = max(-100, min(100, power))
        pulse_width_us = 1000 + (power + 100) * (2000 - 1000) / 200
        duty_percent = (pulse_width_us / 20000) * 100
        self.pwm.change_duty_cycle(duty_percent)

    @on(Input.Submitted, "#power_input")
    @on(Button.Pressed, "#set_button")
    def handle_set_power(self, event) -> None:
        input_widget = self.query_one(Input)
        try:
            power = int(input_widget.value)
            self.set_esc_power(power)
            input_widget.value = ""
        except ValueError:
            pass  # Ignore invalid input

    @on(Button.Pressed, "#set_gains")
    def handle_set_gains(self) -> None:
        try:
            kp = float(self.query_one("#kp_input").value)
            ki = float(self.query_one("#ki_input").value)
            kd = float(self.query_one("#kd_input").value)
            self.pid.Kp = kp
            self.pid.Ki = ki
            self.pid.Kd = kd
        except ValueError:
            pass

    @on(Button.Pressed, "#set_setpoint")
    def handle_set_setpoint(self) -> None:
        try:
            setpoint = float(self.query_one("#setpoint_input").value)
            self.pid.set_setpoint(setpoint)
        except ValueError:
            pass

    @on(Button.Pressed, "#pid_toggle")
    def handle_pid_toggle(self) -> None:
        self.pid_enabled = not self.pid_enabled
        button = self.query_one("#pid_toggle")
        button.label = "Disable PID" if self.pid_enabled else "Enable PID"

    @on(Button.Pressed, "#quit_button")
    def handle_quit(self) -> None:
        self.stop_event = True
        self.pwm.stop()
        self.ser.close()
        self.exit()

    def on_unmount(self) -> None:
        if hasattr(self, 'pwm'):
            self.pwm.stop()
        if hasattr(self, 'ser'):
            self.ser.close()

if __name__ == "__main__":
    MotorControlApp().run()