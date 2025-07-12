from tpi_controller2 import TPIController
import time
import struct

# Configuration parameters
PORT = "COM5"
RF_POWER_DBM = 0

# Analyzer parameters
START_KHZ = 1_606_250
STOP_KHZ = 1_636_250
STEP_KHZ = 300
# Note step must go into stop-start an integer number of times.
# "It may seem redundant to specify the number of points to measure
# as that information can be surmised from the stop frequency and the
# step frequency. However, it is up to the user to calculate this and
# supply the total number of points to be measured. Note that, for example,
# a scan from 100 MHz to 200 MHz with a step frequency of 1 MHz will measure
# 101 points."

DWELL_MS = 20
# Section 2.52.1 (Analyzer Parameters):
# n12…n13 is a 16-bit unsigned integer (LSB first)
# representing the dwell time per point in ms (2–500)
# Dwell time is the amount of time spent measuring each frequency
# point in the sweep. Increasing the dwell time can improve signal-to-noise
# ratio, especially when measuring low-level signals, but will increase sweep
# duration proportionally.

AUTO_RF = True
MAX_POINTS_PER_PACKET = 40
AVERAGES_PER_POINT = 8    #1-8 permitted
CAPTURE_DURATION = 0.1
NUM_CAPTURES = 60

def calculate_num_points(start_khz, stop_khz, step_khz):
    num_points = (stop_khz - start_khz) / step_khz + 1
    if not num_points.is_integer():
        raise ValueError(f"The calculated number of points ({num_points}) must be an integer. "
                        f"Please adjust start_khz ({start_khz}), stop_khz ({stop_khz}), "
                        f"or step_khz ({step_khz}) accordingly.")
    print(f"Calculated number of points: {num_points}")
    return int(num_points)


def main():
    tpi = TPIController(PORT)

    print("Enabling user mode...")
    tpi.enable_user_control()

    all_raw_data = bytearray()  # Create an empty bytearray to store all captures


    print(f"Setting RF power to {RF_POWER_DBM} dBm...")
    tpi.set_rf_power(RF_POWER_DBM)

    print("Setting analyzer parameters...")
    num_points_calc = calculate_num_points(START_KHZ, STOP_KHZ, STEP_KHZ)

    tpi.set_analyzer_parameters_v2(
        start_khz=START_KHZ,
        stop_khz=STOP_KHZ,
        step_khz=STEP_KHZ,
        dwell_ms=DWELL_MS,
        num_points=num_points_calc,
        auto_rf=AUTO_RF,
        max_points_per_packet=MAX_POINTS_PER_PACKET,
        averages_per_point=AVERAGES_PER_POINT
    )

    print("Confirming Analyzer parameters:")
    params = tpi.read_analyzer_parameters_v2()
    for k, v in params.items():
        print(f"{k}: {v}")

    print("Reading current RF output power...")
    power = tpi.read_rf_power()
    print(f"Current RF output power: {power} dBm")
    # Turn RF ON

    # Turn detector ON
    print("Turning detector ON...")
    tpi.set_detector_state(True)

    print("Turning RF ON...")
    tpi.set_rf_output_state(True)

    print("Starting analyzer...")
    tpi.start_analyzer_v2()

    print("Receiving analyzer data...")
    print(f"Capturing raw data {NUM_CAPTURES} times... -this is some arbitrary duration- that is long enough - loop stops when it RXs analyzer stopped")

    for i in range(NUM_CAPTURES):
        start_time = time.time()
        raw_data = tpi.capture_analyzer_raw(duration=CAPTURE_DURATION)
        elapsed = time.time() - start_time
        if len(raw_data) > 0:  # Only print if bytes were captured
            print(f"\nCapture #{i + 1}:")
            print(f"Captured {len(raw_data)} bytes in {elapsed:.2f} seconds")
            print(raw_data.hex())

            # Remove preamble (first 11 bytes) and checksum (last byte)
            if len(raw_data) > 12:  # Only process if packet is long enough
                processed_data = raw_data[11:-1]  # Remove preamble and checksum
                all_raw_data.extend(processed_data)

            # Check if last 2 bytes are 3fb7
            if len(raw_data) >= 7 and raw_data[-7:].hex() == "aa550002073fb7":
                print("Found packet ending with aa550002073fb7, exiting...")
                # Remove the sequence from all_raw_data if it exists at the end
                if len(all_raw_data) >= 7:
                    all_raw_data = all_raw_data[:-7]

                break

    print("\nComplete accumulated data (with preambles and checksums removed):")
    print(f"Total bytes captured: {len(all_raw_data)}")
    print(all_raw_data.hex())

    # Turn RF OFF
    print("Turning RF OFF...")
    tpi.set_rf_output_state(False)

    # Turn detector OFF
    print("Turning detector OFF...")
    tpi.set_detector_state(False)

    tpi.close()
    # Convert accumulated data to float values
    float_values = []
    # Process data in chunks of 4 bytes
    for i in range(0, len(all_raw_data), 4):
        if i + 4 <= len(all_raw_data):  # Make sure we have 4 complete bytes
            # '<f' format string means:
            # < : little-endian (LSB first)
            # f : 32-bit float (4 bytes)
            float_val = struct.unpack('<f', all_raw_data[i:i + 4])[0]
            float_values.append(float_val)

    print("\nConverted float values:")
    for i, value in enumerate(float_values):
        print(f"Value {i + 1}: {value}")

    print("\nConverted values with frequencies:")
    print("Frequency (kHz)    Level (dBm)")
    print("--------------------------------")
    for i, value in enumerate(float_values):
        # Calculate the frequency for this point
        freq = START_KHZ + (i * STEP_KHZ)
        print(f"{freq:10d} kHz    {value:8.2f} dBm")



if __name__ == "__main__":
    main()