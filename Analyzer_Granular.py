from tpi_controller2 import TPIController
import time
import struct
from typing import List, Tuple, Optional
from scipy.interpolate import CubicSpline, interp1d
import numpy as np


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


def find_min_vswr_frequency(vswr_data: list, start_khz: int, stop_khz: int) -> tuple:
    """
    Find the frequency with the lowest VSWR value within the specified range

    Args:
        vswr_data: List of tuples containing (frequency, vswr) pairs
        start_khz: Start frequency in kHz
        stop_khz: Stop frequency in kHz

    Returns:
        Tuple of (frequency, vswr) with the lowest VSWR value in the range
    """
    # Filter data points to only those within the specified range
    valid_points = [(f, v) for f, v in vswr_data if start_khz <= f <= stop_khz]

    # Return the point with minimum VSWR
    if valid_points:
        return min(valid_points, key=lambda x: x[1])
    return (start_khz, 5.0)  # Fallback if no valid points found


def get_vswr_at_frequency(frequency, vswr_data):
    """
    Get VSWR value at specified frequency

    Args:
        frequency: The frequency to look up
        vswr_data: List of tuples containing (frequency, vswr) pairs

    Returns:
        VSWR value at the specified frequency
    """
    return next(vswr for freq, vswr in vswr_data if freq == frequency)


def interpolated(vswr_data: List[Tuple[int, float]],
                 interpolation_factor: int = 3,
                 method: str = 'cubic') -> List[Tuple[int, float]]:
    """
    Interpolates VSWR data to add points between existing measurements while preserving original values.

    Args:
        vswr_data: List of tuples containing (frequency_khz, vswr_value)
        interpolation_factor: Number of points to add between each original point
        method: Interpolation method ('cubic' or 'none')

    Returns:
        List of tuples containing (frequency_khz (int), vswr_value (float))
        with interpolated points added, sorted by frequency
    """
    # Return original data if no interpolation requested
    if method.lower() == 'none' or interpolation_factor < 1:
        return [(int(f), round(float(v), 3)) for f, v in vswr_data]

    # Sort data by frequency and validate
    try:
        sorted_data = sorted((int(f), float(v)) for f, v in vswr_data)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid data point in input: {str(e)}")

    if len(sorted_data) < 4:
        raise ValueError("Need at least 4 points for cubic interpolation")

    # Extract frequencies and values
    orig_freqs = np.array([f for f, _ in sorted_data])
    orig_values = np.array([v for _, v in sorted_data])

    # Create interpolation points
    result = []

    # Add all original points to preserve exact values
    for freq, value in sorted_data:
        result.append((freq, round(value, 3)))

    # Create interpolation function
    try:
        cs = CubicSpline(orig_freqs, orig_values)
    except Exception as e:
        raise ValueError(f"Error creating cubic spline: {str(e)}")

    # Add interpolated points between each pair of original points
    for i in range(len(sorted_data) - 1):
        freq1, _ = sorted_data[i]
        freq2, _ = sorted_data[i + 1]

        # Calculate step size for interpolation
        step = (freq2 - freq1) // (interpolation_factor + 1)

        # Skip if step is too small
        if step < 1:
            continue

        # Add interpolated points
        for j in range(1, interpolation_factor + 1):
            new_freq = freq1 + (j * step)
            if new_freq >= freq2:
                break

            new_value = float(cs(new_freq))  # Convert from numpy float
            result.append((new_freq, round(new_value, 3)))

    # Sort by frequency and return
    return sorted(result, key=lambda x: x[0])

def add_vswr_criterion_points(vswr_data: List[Tuple[int, float]],
                              vswr_start_khz: int,
                              vswr_mid_khz: int,
                              vswr_stop_khz: int) -> List[Tuple[int, float]]:
    """
    Add VSWR criterion frequency points using cubic interpolation.

    Args:
        vswr_data: List of tuples containing (frequency_khz, vswr_value)
        vswr_start_khz: Start frequency point to add
        vswr_mid_khz: Middle frequency point to add
        vswr_stop_khz: Stop frequency point to add

    Returns:
        List of tuples containing (frequency_khz (int), vswr_value (float))
        with vswr values rounded to 3 decimal places, sorted by frequency
    """

    # Convert input data to ensure correct types and rounding
    def convert_point(point: Tuple[int, float]) -> Tuple[int, float]:
        freq, val = point
        return (int(freq), round(float(val), 3))

    # Convert and validate input data
    try:
        typed_data = [convert_point(point) for point in vswr_data]
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid data point in input: {str(e)}")

    # Sort data by frequency
    sorted_data = sorted(typed_data, key=lambda x: x[0])

    # Extract frequencies and values
    freqs = [f for f, _ in sorted_data]
    values = [v for _, v in sorted_data]

    # Validate frequency range
    freq_min, freq_max = min(freqs), max(freqs)
    criterion_freqs = [vswr_start_khz, vswr_mid_khz, vswr_stop_khz]

    for freq in criterion_freqs:
        if freq < freq_min or freq > freq_max:
            raise ValueError(f"Criterion frequency {freq} kHz is outside the measured range "
                             f"({freq_min}-{freq_max} kHz)")

    # Create cubic interpolation function
    try:
        interp_func = interp1d(freqs, values, kind='cubic')
    except ValueError as e:
        raise ValueError(f"Error creating interpolation function: {str(e)}")

    # Create result set starting with original data
    result = set(typed_data)  # Use set to avoid duplicates

    # Add interpolated values at criterion frequencies
    for freq in criterion_freqs:
        if freq not in freqs:  # Only add if frequency doesn't already exist
            value = float(interp_func(freq))  # Convert from numpy float to Python float
            result.add((int(freq), round(value, 3)))

    # Convert back to list and sort by frequency
    return sorted(result, key=lambda x: x[0])


def smoothed(vswr_results: List[Tuple[int, float]], vswr_start_khz: int, vswr_stop_khz: int,
             vswr_mid_khz: int, interpolation_factor: int = 10, method: str = 'cubic') -> List[Tuple[int, float]]:
    """
    Smooths VSWR values using cubic interpolation while preserving original frequency points.

    Args:
        vswr_results: List of tuples containing (frequency_khz, vswr_value)
        vswr_start_khz: Start frequency in kHz (not used in smoothing)
        vswr_stop_khz: Stop frequency in kHz (not used in smoothing)
        vswr_mid_khz: Middle frequency in kHz (not used in smoothing)
        interpolation_factor: Not used in this version
        method: Smoothing method ('cubic' or 'none')

    Returns:
        List of tuples containing (frequency_khz, smoothed_vswr_value)
        Frequency is int, vswr_value is float rounded to 3 decimal places
    """

    def convert_types(freq, val):
        """Convert types and round VSWR to 3 decimal places"""
        try:
            return (int(freq), round(float(val), 3))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid data point ({freq}, {val}): {str(e)}")

    # Return original data converted to correct types if no smoothing requested
    if method.lower() == 'none':
        return [convert_types(f, v) for f, v in vswr_results]

    # Ensure input data uses correct types
    try:
        typed_data = [convert_types(f, v) for f, v in vswr_results]
    except ValueError as e:
        raise ValueError(f"Error converting input data: {str(e)}")

    # Filter out non-finite values
    filtered_data = [(freq, val) for freq, val in typed_data if np.isfinite(val)]

    if not filtered_data:
        raise ValueError("No finite values found in the input data")

    # Sort data by frequency
    sorted_data = sorted(filtered_data, key=lambda x: x[0])

    # Extract frequencies and values
    freqs = np.array([f for f, _ in sorted_data])
    values = np.array([v for _, v in sorted_data])

    # Create cubic interpolation function
    try:
        interp_func = interp1d(freqs, values, kind='cubic', fill_value='extrapolate')
    except ValueError as e:
        raise ValueError(f"Error creating interpolation function: {str(e)}")

    # Apply smoothing to original frequency points
    smoothed_values = interp_func(freqs)

    # Convert back to regular Python types with proper rounding
    return [convert_types(int(f), float(v)) for f, v in zip(freqs, smoothed_values)]


def calculate_vswr(return_loss_db: float) -> float:
    """
    Convert return loss in dB to VSWR, with results limited to range 1.1 to 5.0.

    Args:
        return_loss_db: Return loss in dB (positive value)

    Returns:
        VSWR value (between 1.1 and 5.0)
    """
    # Handle invalid input cases
    if not isinstance(return_loss_db, (int, float)) or np.isnan(return_loss_db):
        return 5.0

    # Convert return loss to linear scale
    reflection_coefficient = 10 ** (-abs(return_loss_db) / 20)

    # Calculate VSWR
    if reflection_coefficient >= 1:
        return 5.0

    vswr = (1 + reflection_coefficient) / (1 - reflection_coefficient)

    # Limit the range
    if vswr < 1.1:
        return 1.1
    elif vswr > 5.0:
        return 5.0

    return float(vswr)


def process_vswr_data(results: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    """
    Convert frequency and return loss measurements to frequency and VSWR.

    Args:
        results: List of tuples containing (frequency_khz, return_loss_db)

    Returns:
        List of tuples containing (frequency_khz, vswr)
    """
    return [(freq, calculate_vswr(return_loss)) for freq, return_loss in results]


def subtract_baseline(results: List[Tuple[int, float]],
                      baseline: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    """
    Subtract baseline values from results.

    Args:
        results: List of tuples containing (frequency_khz, value)
        baseline: List of tuples containing (frequency_khz, value)

    Returns:
        List of tuples containing (frequency_khz, value_minus_baseline)
    """
    # Create a dictionary of baseline values keyed by frequency
    baseline_dict = {freq: value for freq, value in baseline}

    # Subtract baseline values from results
    subtracted_results = []
    for freq, value in results:
        if freq in baseline_dict:
            subtracted_value = value - baseline_dict[freq]
            subtracted_results.append((freq, subtracted_value))
        else:
            # Handle case where frequency doesn't exist in baseline
            subtracted_results.append((freq, value))

    return subtracted_results


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

def get_highest_baseline(scanner: FrequencyScanner, start_khz: int, step_khz: int, num_captures: int = 10) -> List[
    Tuple[int, float]]:
    """
    Capture multiple baseline measurements and return the one with highest values.

    Args:
        scanner: FrequencyScanner instance
        start_khz: Start frequency in kHz
        step_khz: Step size in kHz
        num_captures: Number of baseline captures to perform

    Returns:
        List of tuples containing (frequency_khz, value) for the highest baseline
    """
    baselines = []
    baseline_averages = []
    print(f"Capturing {num_captures} baselines...")
    for i in range(num_captures):
        baseline = scanner.run(start_khz, step_khz)
        # Calculate average value for this baseline immediately
        values = [value for _, value in baseline]
        avg_value = sum(values) / len(values)
        print(f"Capturing baseline {i + 1}/{num_captures}, average value: {avg_value:.2f} dBm")
        baselines.append(baseline)
        baseline_averages.append(avg_value)
    # Find the baseline with highest average value
    highest_idx = baseline_averages.index(max(baseline_averages))
    highest_baseline = baselines[highest_idx]

    print(f"Selected baseline {highest_idx + 1} with average value: {baseline_averages[highest_idx]:.2f} dBm")
    return highest_baseline


def find_lowest_reflected_results(current_results: List[Tuple[int, float]],
                                  previous_lowest_results: Optional[List[Tuple[int, float]]] = None) -> Tuple[
    List[Tuple[int, float]], float]:
    """
    Determine if the current results have lower values than the previous lowest results.
    Args:
        current_results: Current scan results as list of (frequency, value) tuples
        previous_lowest_results: Previous lowest results as list of (frequency, value) tuples, or None
    Returns:
        Tuple containing:
            - List of (frequency, value) tuples representing the lowest results
            - Average value of the lowest results
    """
    current_average = sum(value for _, value in current_results) / len(current_results)

    if previous_lowest_results is None:
        return current_results, current_average

    lowest_average = sum(value for _, value in previous_lowest_results) / len(previous_lowest_results)

    if current_average < lowest_average:
        print(f"New lowest results found with average value: {current_average:.2f} dBm")
        return current_results, current_average

    print(f"Current results have higher average value than previous lowest results: {current_average:.2f} dBm > {lowest_average:.2f} dBm")
    return previous_lowest_results, lowest_average


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


def evaluate_vswr_range(vswr_data: List[Tuple[int, float]],
                        freq_low: int,
                        freq_high: int,
                        vswr_limit: float) -> bool:
    """
    Evaluate if VSWR measurements are below the specified limit within the given frequency range.
    Uses linear interpolation between measurement points for accurate assessment.

    Args:
        vswr_data: List of tuples containing (frequency_khz, vswr_value)
        freq_low: Lower frequency bound in kHz
        freq_high: Upper frequency bound in kHz
        vswr_limit: Maximum acceptable VSWR value

    Returns:
        bool: True if all VSWR values (including interpolated) are below limit, False otherwise
    """
    # Sort data by frequency to ensure proper interpolation
    sorted_data = sorted(vswr_data, key=lambda x: x[0])

    # Validate frequency range
    min_freq = sorted_data[0][0]
    max_freq = sorted_data[-1][0]
    if freq_low < min_freq or freq_high > max_freq:
        raise ValueError(f"Requested frequency range ({freq_low}-{freq_high} kHz) is outside "
                         f"measured range ({min_freq}-{max_freq} kHz)")

    # Find relevant measurement points within and adjacent to our frequency range
    relevant_points = []
    for i, (freq, vswr) in enumerate(sorted_data):
        if freq >= freq_low or (i > 0 and sorted_data[i - 1][0] < freq_low):
            relevant_points.append((freq, vswr))
        if freq > freq_high:
            break

    # Check each segment
    for i in range(len(relevant_points) - 1):
        freq1, vswr1 = relevant_points[i]
        freq2, vswr2 = relevant_points[i + 1]

        # Skip if segment is entirely outside our range of interest
        if freq1 > freq_high or freq2 < freq_low:
            continue

        # If either point exceeds limit, check if the interpolated values between them also exceed
        if vswr1 > vswr_limit or vswr2 > vswr_limit:
            # Calculate slope for interpolation
            slope = (vswr2 - vswr1) / (freq2 - freq1)

            # Determine check points: segment endpoints within our range
            check_start = max(freq1, freq_low)
            check_end = min(freq2, freq_high)

            # Check interpolated values at endpoints of the relevant segment
            vswr_start = vswr1 + slope * (check_start - freq1)
            vswr_end = vswr1 + slope * (check_end - freq1)

            if max(vswr_start, vswr_end) > vswr_limit:
                print(f"VSWR limit exceeded between {check_start} kHz ({vswr_start:.2f}) "
                      f"and {check_end} kHz ({vswr_end:.2f})")
                return False

            # If slope is not zero, check the peak/valley point if it falls within our segment
            if abs(slope) > 0:
                # No need to check intermediate points as linear interpolation means
                # the maximum/minimum will be at the endpoints we already checked
                pass

    return True

def main():
    """
    Main function to demonstrate the scanner functionality with visualization
    """

    com_port = "COM6"
    start_khz = 1_606_250
    stop_khz = 1_636_250
    step_khz = 600
    dwell_ms = 20
    verbose = False



    scanner = FrequencyScanner(com_port, False)
    scanner.setup(start_khz, stop_khz, step_khz, dwell_ms)

    input('Disconnect Antenna and hit enter to continue:')
    baseline = get_highest_baseline(scanner, start_khz, step_khz,10)
    input('Connect Antenna and hit enter to continue:')

    try:

        lowest_reflected_results = None
        lowest_average = float('inf')

        for i in range(10):
            # Perform the scan
            results_reflected =  scanner.run(start_khz, step_khz)

            # Find lowest results
            lowest_reflected_results, lowest_average = find_lowest_reflected_results(
                results_reflected,
                lowest_reflected_results
            )

            results_corrected = subtract_baseline(results_reflected, baseline)

            results_vswr = process_vswr_data(results_corrected)


            # Separate frequencies and power levels
            frequencies = [r[0] for r in results_vswr]
            vswr = [r[1] for r in results_vswr]

            vswr_data = list(zip(frequencies, vswr))

            # Check if VSWR is below 1.5 between 1616000 kHz and 1626500 kHz
            passed = evaluate_vswr_range(vswr_data, 1616000, 1626500, 1.5)
            if passed:
                print("VSWR test passed - all values within limits")
            else:
                print("VSWR test failed - limit exceeded")

            # Print summary
            print("\nScan Summary:")
            print(f"Points measured: {len(results_vswr)}")
            print(f"Frequency range: {min(frequencies):,} kHz to {max(frequencies):,} kHz")
            print(f"Power range: {min(vswr):.2f} dBm to {max(vswr):.2f} dBm")

            # Create visualization in a separate function
            visualize_results(frequencies, vswr)


    except Exception as e:
        print(f"Error during scan: {str(e)}")
        return False
    scanner.shutdown()
    return True

if __name__ == "__main__":
    main()