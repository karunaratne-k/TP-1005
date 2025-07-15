from tpi_controller2 import TPIController
import time
import struct
from typing import List, Tuple, Optional

def calculate_num_points(start_khz, stop_khz, step_khz):
    """Calculate the number of points for frequency scanning"""
    verbose = False
    num_points = (stop_khz - start_khz) / step_khz + 1
    if not num_points.is_integer():
        raise ValueError(f"The calculated number of points ({num_points}) must be an integer. "
                         f"Please adjust frequency parameters accordingly.")
    if verbose:
        print(f"Calculated number of points: {num_points}")
    return int(num_points)



class FrequencyScanner:
    # Constants that could be parameterized in future if needed
    RF_POWER_DBM = 0
    AUTO_RF = True
    MAX_POINTS_PER_PACKET = 40
    AVERAGES_PER_POINT = 8
    CAPTURE_DURATION = 0.1
    NUM_CAPTURES = 60

    def __init__(self, com_port: str, verbose: bool = False):
        """Initialize the frequency scanner."""
        self.com_port = com_port
        self.verbose = verbose
        self.tpi: Optional[TPIController] = None
        self.all_raw_data = bytearray()



    def setup(self, start_khz: int, stop_khz: int, step_khz: int, dwell_ms: int) -> None:
        """
        Set up the analyzer with the specified parameters.
        """
        if self.verbose:
            print("Initializing controller...")
        self.tpi = TPIController(self.com_port)

        try:
            if self.verbose:
                print("Enabling user mode...")
            self.tpi.enable_user_control()

            if self.verbose:
                print(f"Setting RF power to {self.RF_POWER_DBM} dBm...")
            self.tpi.set_rf_power(self.RF_POWER_DBM)

            if self.verbose:
                print("Setting analyzer parameters...")
            num_points_calc = calculate_num_points(start_khz, stop_khz, step_khz)

            self.tpi.set_analyzer_parameters_v2(
                start_khz=start_khz,
                stop_khz=stop_khz,
                step_khz=step_khz,
                dwell_ms=dwell_ms,
                num_points=num_points_calc,
                auto_rf=self.AUTO_RF,
                max_points_per_packet=self.MAX_POINTS_PER_PACKET,
                averages_per_point=self.AVERAGES_PER_POINT
            )

            # Turn detector and RF ON
            self.tpi.set_detector_state(True)
            self.tpi.set_rf_output_state(True)

        except Exception as e:
            self.shutdown()
            raise e

    def run(self, start_khz: int, step_khz: int) -> List[Tuple[int, float]]:
        """
        Run the frequency scan and return the results.
        """
        if not self.tpi:
            raise RuntimeError("Scanner not set up. Call setup() first.")

        results = []
        self.all_raw_data = bytearray()

        try:
            if self.verbose:
                print("Starting analyzer...")
            self.tpi.start_analyzer_v2()

            if self.verbose:
                print("Receiving analyzer data...")

            # Capture data
            for i in range(self.NUM_CAPTURES):
                raw_data = self.tpi.capture_analyzer_raw(duration=self.CAPTURE_DURATION)

                if len(raw_data) > 12:
                    processed_data = raw_data[11:-1]
                    self.all_raw_data.extend(processed_data)

                if len(raw_data) >= 7 and raw_data[-7:].hex() == "aa550002073fb7":
                    if len(self.all_raw_data) >= 7:
                        self.all_raw_data = self.all_raw_data[:-7]
                    break

            # Convert accumulated data to float values
            float_values = []
            for i in range(0, len(self.all_raw_data), 4):
                if i + 4 <= len(self.all_raw_data):
                    float_val = struct.unpack('<f', self.all_raw_data[i:i + 4])[0]
                    float_values.append(float_val)

            # Create results list with frequency and power values
            for i, value in enumerate(float_values):
                freq = start_khz + (i * step_khz)
                results.append((freq, value))
                if self.verbose:
                    print(f"{freq:10d} kHz    {value:8.2f} dBm")

            return results

        except Exception as e:
            self.shutdown()
            raise e

    def shutdown(self) -> None:
        """
        Clean up and close the connection.
        """
        if self.tpi:
            try:
                self.tpi.set_rf_output_state(False)
                self.tpi.set_detector_state(False)
            finally:
                self.tpi.close()
                self.tpi = None


def scan_frequency_range(com_port: str, start_khz: int, stop_khz: int,
                         step_khz: int, dwell_ms: int, verbose: bool = False) -> List[Tuple[int, float]]:
    """
    Backward compatibility wrapper for the original function.
    """
    scanner = FrequencyScanner(com_port, verbose)
    try:
        scanner.setup(start_khz, stop_khz, step_khz, dwell_ms)
        return scanner.run(start_khz, step_khz)
    finally:
        scanner.shutdown()


def visualize_results(frequencies, power_levels):
    """
    Create and display a visualization of the scan results.

    Args:
        frequencies: List of frequency values in kHz
        power_levels: List of power measurements in dBm
    """
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 6))
        plt.plot(frequencies, power_levels, 'b-', marker='o')
        plt.grid(True)
        plt.xlabel('Frequency (kHz)')
        plt.ylabel('Power (dBm)')
        plt.title('Frequency Scan Results')
        plt.ticklabel_format(style='plain')
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("Matplotlib is not installed. Skipping visualization.")
    except Exception as e:
        print(f"Error during visualization: {str(e)}")


def main():
    """
    Main function to demonstrate the scanner functionality with visualization
    """

    com_port = "COM5"
    start_khz = 1_606_250
    stop_khz = 1_636_250
    step_khz = 1200
    dwell_ms = 20
    verbose = False



    scanner = FrequencyScanner(com_port, False)
    scanner.setup(start_khz, stop_khz, step_khz, dwell_ms)

    try:
        for i in range(10):
            iteration_start = time.time()

            # Perform the scan
            results =  scanner.run(start_khz, step_khz)


            # Separate frequencies and power levels
            frequencies = [r[0] for r in results]
            power_levels = [r[1] for r in results]

            # Print summary
            print("\nScan Summary:")
            print(f"Points measured: {len(results)}")
            print(f"Frequency range: {min(frequencies):,} kHz to {max(frequencies):,} kHz")
            print(f"Power range: {min(power_levels):.2f} dBm to {max(power_levels):.2f} dBm")
            # Calculate and print timing
            iteration_time = time.time() - iteration_start
            print(f"Iteration time: {iteration_time:.2f} seconds")


            # Create visualization in a separate function
            visualize_results(frequencies, power_levels)
            iteration_time = time.time() - iteration_start
            print(f"Iteration time: {iteration_time:.2f} seconds")

    except Exception as e:
        print(f"Error during scan: {str(e)}")
        return False
    scanner.shutdown()
    return True

if __name__ == "__main__":
    main()
