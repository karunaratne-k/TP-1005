from tpi_controller import TPIController
import struct

def main():
    port = "COM3"

    tpi = None
    try:
        print(f"Opening connection to {port}...")
        tpi = TPIController(port)

        print("Enabling user mode...")
        tpi.enable_user_control()
        print("User mode enabled.")

        print("Setting RF power to 0 dBm...")
        tpi.set_rf_power(0)
        print("RF power set to 0 dBm.")

        print("Setting analyzer parameters...")
        tpi.set_analyzer_parameters_v2(
            start_khz=1_606_250,
            stop_khz=1_636_250,
            step_khz=306,
            dwell_ms=20,
            num_points=99,
            auto_rf=True,
            max_points_per_packet=25,
            averages_per_point=8
        )
        print("Analyzer parameters set.")

        print("Reading back analyzer parameters to confirm...")
        params = tpi.read_analyzer_parameters_v2()
        for k, v in params.items():
            print(f"{k}: {v}")

        print("Starting analyzer for one sweep...")
        tpi.start_analyzer_v2(
            sweeps=0,
            max_ms_between_packets=1000,
            aux_input=0
        )
        print("Analyzer started. Receiving data...")

        all_points = tpi.read_analyzer_data_v2(verbose=True, dump_raw=True)


        # Output the results as a table
        print("\nFrequency_kHz, dBm")
        f_start = params["start_khz"]
        f_step = params["step_khz"]

        for step in sorted(all_points):
            freq = f_start + step * f_step
            dBm = all_points[step]
            print(f"{freq},{dBm:.2f}")

    finally:
        if tpi:
            print("Closing connection.")
            tpi.close()
            del tpi
        print("Done.")

if __name__ == "__main__":
    main()
