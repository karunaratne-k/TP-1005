from tpi_controller import TPIController

def main():
    port = input("Enter COM port: ").strip()
    tpi = TPIController(port)

    # Configure Analyzer
    tpi.set_analyzer_parameters(
        start_freq_khz=100_000,
        stop_freq_khz=200_000,
        num_points=50,
        dwell_per_point_ms=10,
        mode=0,  # Forward mode
        auto_rf=True,
        continuous=False,
        rf_level_dbm=0.0
    )
    print("Analyzer parameters set.")

    # Start analyzer
    tpi.start_analyzer()
    print("Analyzer started. Waiting for completion...")
    tpi.wait_for_analyzer_stop(timeout=30)

    # After first scan, now safe to read parameters
    params = tpi.read_analyzer_parameters()
    print("Analyzer Configuration after scan:")
    for k, v in params.items():
        print(f"  {k}: {v}")

    # Read analyzer data
    data = tpi.read_analyzer_data()

    # Compute frequencies
    freq_step = (params["stop_kHz"] - params["start_kHz"]) / (params["num_points"] - 1)
    print("Frequency (MHz)   Level (dBm)")
    for i, val in enumerate(data):
        freq_mhz = (params["start_kHz"] + i * freq_step) / 1e3
        print(f"{freq_mhz:8.3f}        {val:6.2f}")

    tpi.close()

if __name__ == "__main__":
    main()
