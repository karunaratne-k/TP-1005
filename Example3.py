from tpi_controller2 import TPIController
import struct

def main():
    port = "COM5"
    tpi = TPIController(port)
    tpi.enable_user_control()

    tpi.set_rf_power(0)

    tpi.set_analyzer_parameters_v2(
        start_khz=1_606_250,
        stop_khz=1_636_250,
        step_khz=5000,
        dwell_ms=20,
        num_points=7,
        auto_rf=True,
        max_points_per_packet=50,
        averages_per_point=1
    )

    params = tpi.read_analyzer_parameters_v2()
    print("Analyzer parameters confirmed:")
    for k, v in params.items():
        print(f"{k}: {v}")

    input("Safety check...Press Enter to continue.")

    tpi.start_analyzer_v2()

    print("Receiving analyzer packets until analyzer stops...")

    tpi.ser.timeout = 2
    all_points = {}

    while True:
        # Read header
        header = tpi.ser.read(4)
        if len(header) < 4:
            print("Timeout waiting for header.")
            continue

        if header[0] != 0xAA or header[1] != 0x55:
            print(f"Ignoring invalid header: {header.hex()}")
            continue

        length = (header[2] << 8) | header[3]

        body = tpi.ser.read(length)
        if len(body) < length:
            print("Incomplete body, skipping.")
            continue

        checksum = tpi.ser.read(1)
        if len(checksum) < 1:
            print("Missing checksum, skipping.")
            continue

        # Validate checksum
        chk = (0xFF - ((header[2] + header[3] + sum(body)) & 0xFF)) & 0xFF
        if checksum[0] != chk:
            print("Checksum error, skipping packet.")
            continue

        cmd = body[:2]

        if cmd == b'\x07\x3E':
            n_points = body[2]
            first_step = int.from_bytes(body[3:7], 'little')
            data_bytes = body[7:]

            if len(data_bytes) < n_points * 4:
                print("Incomplete data bytes, skipping packet.")
                continue

            print(f"\nData packet: {n_points} points starting at step {first_step}")

            for i in range(n_points):
                val_bytes = data_bytes[i * 4:(i + 1) * 4]
                dBm = struct.unpack('<f', val_bytes)[0]
                step_index = first_step + i
                freq = params["start_khz"] + step_index * params["step_khz"]
                all_points[step_index] = (freq, dBm)
                print(f"Step {step_index}: {freq} kHz, {dBm:.2f} dBm")

        elif cmd == b'\x07\x3F':
            print("\nAnalyzer stopped.")
            break

        else:
            print(f"Ignoring unknown packet type: {cmd.hex()}")

    print("\nFinal collected points:")
    for step in sorted(all_points):
        freq, dBm = all_points[step]
        print(f"{freq} kHz, {dBm:.2f} dBm")

    tpi.close()

if __name__ == "__main__":
    main()
