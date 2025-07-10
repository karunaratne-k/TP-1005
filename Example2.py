from tpi_controller2 import TPIController
import time

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
        dwell_ms=500,
        num_points=5,
        auto_rf=True,
        max_points_per_packet=50,
        averages_per_point=8
    )

    print("Confirming parameters:")
    params = tpi.read_analyzer_parameters_v2()
    for k,v in params.items():
        print(f"{k}: {v}")


    tpi.start_analyzer_v2()

    print("Receiving analyzer data...")
    print("Capturing raw data 100 times...")

    for i in range(100):
        start_time = time.time()  # Fixed: Using time.time() instead of time()
        raw_data = tpi.capture_analyzer_raw(duration=0.1)
        elapsed = time.time() - start_time  # Fixed: Using time.time() instead of time()
        print(f"\nCapture #{i+1}:")
        print(f"Captured {len(raw_data)} bytes in {elapsed:.2f} seconds")
        print(raw_data.hex())



    tpi.close()

if __name__=="__main__":
    main()
