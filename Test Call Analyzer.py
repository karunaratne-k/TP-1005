from Analyzer import scan_frequency_range


def main():
    """
    Main function to demonstrate the scanner functionality with visualization
    """

    # Scanner parameters
    SCAN_PARAMS = {
        "com_port": "COM5",
        "start_khz": 1_606_250,
        "stop_khz": 1_636_250,
        "step_khz": 300,
        "dwell_ms": 20,
        "verbose": False
    }

    try:
        # Perform the scan
        results = scan_frequency_range(**SCAN_PARAMS)
        
        # Separate frequencies and power levels
        frequencies = [r[0] for r in results]
        power_levels = [r[1] for r in results]
        
        print(results)
        print(frequencies)
        print(power_levels)
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")


if __name__ == "__main__":
    main()