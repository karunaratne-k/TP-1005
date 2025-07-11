from tpi_controller2 import TPIController
import time

# Configuration parameters
PORT = "COM5"
RF_POWER_DBM = 0

# Analyzer parameters
START_KHZ = 1_606_250
STOP_KHZ = 1_636_250
STEP_KHZ = 5_000
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
MAX_POINTS_PER_PACKET = 50
AVERAGES_PER_POINT = 1    #1-8 permitted
CAPTURE_DURATION = 0.1
NUM_CAPTURES = 60

def calculate_num_points(start_khz, stop_khz, step_khz):
    num_points = (stop_khz - start_khz) / step_khz + 1
    if not num_points.is_integer():
        raise ValueError(f"The calculated number of points ({num_points}) must be an integer. "
                        f"Please adjust start_khz ({start_khz}), stop_khz ({stop_khz}), "
                        f"or step_khz ({step_khz}) accordingly.")
    return int(num_points)


def main():
    tpi = TPIController(PORT)
    tpi.enable_user_control()

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

    print("Confirming parameters:")
    params = tpi.read_analyzer_parameters_v2()
    for k, v in params.items():
        print(f"{k}: {v}")

    tpi.start_analyzer_v2()

    print("Receiving analyzer data...")
    print("Capturing packets until analyzer stops...")
    tpi.capture_packets_until_stopped(verbose=True)

    tpi.close()

    main()