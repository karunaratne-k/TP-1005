from Analyzer import scan_frequency_range
import matplotlib.pyplot as plt

def main():
    """
    Main function to demonstrate the scanner functionality with visualization
    """
    import matplotlib
    matplotlib.use('TkAgg')  # Use TkAgg backend for separate window
    import matplotlib.pyplot as plt
    
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
        
        # Create visualization
        plt.figure(figsize=(12, 8))
        
        # Plot main data
        plt.plot(frequencies, power_levels, 'b-', marker='o', label='Power Levels', zorder=1)
        
        # Find the exact point at 1616150 kHz
        target_freq = 1_616_150
        target_idx = frequencies.index(target_freq)
        target_power = power_levels[target_idx]
        
        # Add marker and label
        plt.plot(target_freq, target_power, 'r^', markersize=12, label='Target', zorder=2)
        plt.annotate(f'{target_freq} kHz\n{target_power:.2f} dBm',
                    xy=(target_freq, target_power),
                    xytext=(30, 30),
                    textcoords='offset points',
                    bbox=dict(facecolor='yellow', alpha=0.7, edgecolor='red'),
                    arrowprops=dict(arrowstyle='->', color='red', lw