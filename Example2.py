from tpi_controller2 import TPIController

def main():
    port = "COM3"
    tpi = TPIController(port)
    tpi.enable_user_control()

    print("Setting RF power to 0 dBm...")
    tpi.set_rf_power(0)

    print("Setting analyzer parameters...")
    tpi.set_analyzer_parameters_v2(
        start_khz=1_606_250,
        stop_khz=1_636_250,
        step_khz=10_000,
        dwell_ms=50,
        num_points=5,
        auto_rf=True,
        max_points_per_packet=50,
        averages_per_point=8
    )

    print("Confirming parameters:")
    params = tpi.read_analyzer_parameters_v2()
    for k,v in params.items():
        print(f"{k}: {v}")

    input("\n*** SAFETY CHECK ***\nNo antenna connected?\nPress Enter to continue.")

    tpi.start_analyzer_v2()

    print("Receiving analyzer data...")
    points = tpi.read_analyzer_data_v2(verbose=True, dump_raw=True)
    print("\nFrequency_kHz, dBm")
    for step in sorted(points):
        freq = params["start_khz"] + step*params["step_khz"]
        print(f"{freq},{points[step]:.2f}")

    tpi.close()

if __name__=="__main__":
    main()
