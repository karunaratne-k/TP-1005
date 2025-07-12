from tpi_controller2 import TPIController
import time
import struct
from typing import List, Tuple


def calculate_num_points(start_khz, stop_khz, step_khz):
    verbose = False
    num_points = (stop_khz - start_khz) / step_khz + 1
    if not num_points.is_integer():
        raise ValueError(f"The calculated number of points ({num_points}) must be an integer. "
                         f"Please adjust frequency parameters accordingly.")
    if verbose:
        print(f"Calculated number of points: {num_points}")
    return int(num_points)

def scan_frequency_range(com_port: str, start_khz: int, stop_khz: int, 
                        step_khz: int, dwell_ms: int, verbose: bool = False) -> List[Tuple[int, float]]:
    """
    Scan a frequency range and return power measurements.
    
    Args:
        com_port: Serial port identifier (e.g. 'COM5')
        start_khz: Start frequency in kHz
        stop_khz: Stop frequency in kHz
        step_khz: Step size in kHz
        dwell_ms: Dwell time per point in ms (2-500)
        verbose: Enable debug printing if True
    
    Returns:
        List of tuples containing (frequency_khz, power_dbm)
    """
    # Constants that could be parameterized in future if needed
    RF_POWER_DBM = 0
    AUTO_RF = True
    MAX_POINTS_PER_PACKET = 40
    AVERAGES_PER_POINT = 8
    CAPTURE_DURATION = 0.1
    NUM_CAPTURES = 60



    # Initialize results list
    results = []
    all_raw_data = bytearray()

    # Initialize controller
    tpi = TPIController(com_port)

    try:
        if verbose:
            print("Enabling user mode...")
        tpi.enable_user_control()

        if verbose:
            print(f"Setting RF power to {RF_POWER_DBM} dBm...")
        tpi.set_rf_power(RF_POWER_DBM)

        if verbose:
            print("Setting analyzer parameters...")
        num_points_calc = calculate_num_points(start_khz, stop_khz, step_khz)

        tpi.set_analyzer_parameters_v2(
            start_khz=start_khz,
            stop_khz=stop_khz,
            step_khz=step_khz,
            dwell_ms=dwell_ms,
            num_points=num_points_calc,
            auto_rf=AUTO_RF,
            max_points_per_packet=MAX_POINTS_PER_PACKET,
            averages_per_point=AVERAGES_PER_POINT
        )

        # Turn detector and RF ON
        tpi.set_detector_state(True)
        tpi.set_rf_output_state(True)

        if verbose:
            print("Starting analyzer...")
        tpi.start_analyzer_v2()

        if verbose:
            print("Receiving analyzer data...")

        # Capture data
        for i in range(NUM_CAPTURES):
            raw_data = tpi.capture_analyzer_raw(duration=CAPTURE_DURATION)
            
            if len(raw_data) > 12:
                processed_data = raw_data[11:-1]
                all_raw_data.extend(processed_data)

            if len(raw_data) >= 7 and raw_data[-7:].hex() == "aa550002073fb7":
                if len(all_raw_data) >= 7:
                    all_raw_data = all_raw_data[:-7]
                break

        # Convert accumulated data to float values
        float_values = []
        for i in range(0, len(all_raw_data), 4):
            if i + 4 <= len(all_raw_data):
                float_val = struct.unpack('<f', all_raw_data[i:i + 4])[0]
                float_values.append(float_val)

        # Create results list with frequency and power values
        for i, value in enumerate(float_values):
            freq = start_khz + (i * step_khz)
            results.append((freq, value))
            if verbose:
                print(f"{freq:10d} kHz    {value:8.2f} dBm")

    finally:
        # Cleanup
        tpi.set_rf_output_state(False)
        tpi.set_detector_state(False)
        tpi.close()

    return results


def main():
    """
    Main function to demonstrate the scanner functionality with visualization
    """
    import matplotlib.pyplot as plt
    from typing import List, Tuple

    # Scanner parameters
    SCAN_PARAMS = {
        "com_port": "COM5",
        "start_khz": 1_606_250,
        "stop_khz": 1_636_250,
        "step_khz": 300,
        "dwell_ms": 20,
        "verbose": False
    }

    print("Starting frequency scan...")
    print(f"Range: {SCAN_PARAMS['start_khz']} kHz to {SCAN_PARAMS['stop_khz']} kHz")
    print(f"Step size: {SCAN_PARAMS['step_khz']} kHz")

    try:
        # Perform the scan
        results = scan_frequency_range(**SCAN_PARAMS)

        # Separate frequencies and power levels
        frequencies = [r[0] for r in results]
        power_levels = [r[1] for r in results]

        # Print summary
        print("\nScan Summary:")
        print(f"Points measured: {len(results)}")
        print(f"Frequency range: {min(frequencies):,} kHz to {max(frequencies):,} kHz")
        print(f"Power range: {min(power_levels):.2f} dBm to {max(power_levels):.2f} dBm")

        # Create visualization
        plt.figure(figsize=(10, 6))
        plt.plot(frequencies, power_levels, 'b-', marker='o')
        plt.grid(True)
        plt.xlabel('Frequency (kHz)')
        plt.ylabel('Power (dBm)')
        plt.title('Frequency Scan Results')

        # Format x-axis to show frequencies in MHz for better readability
        plt.ticklabel_format(style='plain')

        # Show the plot
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"Error during scan: {str(e)}")
        return False

    return True


if __name__ == "__main__":
    main()
