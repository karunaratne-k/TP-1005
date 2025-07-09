from tpi_controller import TPIController

def main():
    port = input("Enter COM port (e.g., COM3 or /dev/ttyUSB0): ").strip()
    tpi = TPIController(port)

    model = tpi.read_model_number()
    serial = tpi.read_serial_number()
    fw = tpi.read_firmware_version()
    freq = tpi.read_frequency()
    rf_on = tpi.read_rf_output_state()

    print(f"Model Number: {model}")
    print(f"Serial Number: {serial}")
    print(f"Firmware Version: {fw}")
    print(f"Frequency: {freq / 1e3:.3f} MHz")
    print(f"RF Output: {'ON' if rf_on else 'OFF'}")

    # Example: set frequency to 100 MHz
    tpi.set_frequency(100_000)

    # Turn RF output on
    tpi.set_rf_output(True)

    tpi.close()

if __name__ == "__main__":
    main()
