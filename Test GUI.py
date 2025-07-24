import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import json
import random

from Analyzer_Granular import (
    FrequencyScanner, 
    get_highest_baseline,
    subtract_baseline,
    calculate_vswr,
    add_vswr_criterion_points,
    interpolated,
    get_vswr_at_frequency,
    find_min_vswr_frequency,
    process_vswr_data,
    evaluate_vswr_range,
    smoothed
)
import os

COMPORT = "COM16"  # Static definition as requested

class VSWRAnalyzer(tk.Tk):
    def __init__(self):
        super().__init__()

        # Add initialization of current_params
        self.current_params = None

        self.title("VSWR Analyzer")
        self.geometry("1200x800")

        # Add a variable to track continuous scanning
        self.continuous_scan = False
        self.after_id = None  # To store the ID of scheduled updates

        # Add counter for consecutive passing scans
        self.consecutive_passes = 0

        # Variables
        self.device_type = tk.StringVar(value="E-Dot")
        self.test_type = tk.StringVar(value="Element")
        self.combined_type = tk.StringVar()
        self.scanner = None
        self.baseline = None
        self.serial = None
        self.scan_mode = tk.StringVar(value="Single")  # Add this line

        # Create main frames
        self.control_frame = tk.Frame(self, height=300)
        self.control_frame.pack(fill='x', side='top')
        self.control_frame.pack_propagate(False)

        self.plot_frame = tk.Frame(self)
        self.plot_frame.pack(fill='both', expand=True)

        # Setup UI components
        self.setup_control_area()
        self.setup_plot_area()

        # Initially disable buttons that require selection
        self.update_button_states()

        # Add instance variables for storing scan data
        self.vswr_data = None
        self.last_scan_data = None

    def setup_control_area(self):
        # Device Type Toggle Button
        self.device_btn = tk.Button(
            self.control_frame,
            textvariable=self.device_type,
            command=self.toggle_device_type,
            width=10
        )
        self.device_btn.place(x=10, y=10)

        # Create device type button
        self.device_btn = tk.Button(
            self,
            textvariable=self.device_type,
            command=self.toggle_device_type,
            width=10
        )
        self.device_btn.place(x=10, y=10)

        # Create three separate radio buttons for test type
        self.test_type_frame = tk.Frame(self)
        self.test_type_frame.place(x=120, y=10)

        self.element_radio = tk.Radiobutton(
            self.test_type_frame,
            text="Element",
            variable=self.test_type,
            value="Element",
            command=self.update_combined_type
        )
        self.element_radio.pack(side=tk.LEFT)

        self.wet_radio = tk.Radiobutton(
            self.test_type_frame,
            text="Wet",
            variable=self.test_type,
            value="Wet",
            command=self.update_combined_type
        )
        self.wet_radio.pack(side=tk.LEFT)

        self.final_radio = tk.Radiobutton(
            self.test_type_frame,
            text="Final",
            variable=self.test_type,
            value="Final",
            command=self.update_combined_type
        )
        self.final_radio.pack(side=tk.LEFT)

        self.update_test_type_visibility()

        # Combined type display
        self.type_label = tk.Label(
            self.control_frame,
            textvariable=self.combined_type
        )
        self.type_label.place(x=230, y=30)

        # Run Parameters Display
        self.params_frame = tk.LabelFrame(
            self.control_frame,
            text="RUN PARAMS",
            width=400,
            height=200
        )
        self.params_frame.place(x=10, y=50)

        # Test Results Display
        self.results_frame = tk.LabelFrame(
            self.control_frame,
            text="TEST RESULTS",
            width=400,
            height=80
        )
        self.results_frame.place(x=420, y=50)

        # Action Buttons
        self.baseline_btn = tk.Button(
            self.control_frame,
            text="BASELINE",
            command=self.run_baseline,
            state='disabled',
            width=10
        )
        self.baseline_btn.place(x=10, y=260)

        self.scan_btn = tk.Button(
            self.control_frame,
            text="SCAN",
            command=self.on_scan_click,
            state='disabled',
            width=10
        )
        self.scan_btn.place(x=120, y=260)

        self.save_btn = tk.Button(
            self.control_frame,
            text="SAVE",
            command=self.mark_save,
            state='disabled',
            width=10
        )
        self.save_btn.place(x=230, y=260)

        self.exit_btn = tk.Button(
            self.control_frame,
            text="EXIT",
            command=self.exit_application,
            width=10
        )
        self.exit_btn.place(x=340, y=260)

        # Add this before the exit button
        self.scan_mode_btn = tk.Button(
            self.control_frame,
            textvariable=self.scan_mode,
            command=self.toggle_scan_mode,
            state='disabled',  # Initially disabled
            width=10
        )
        self.scan_mode_btn.place(x=450, y=260)  # Adjust x position as needed

    def setup_plot_area(self):
        self.figure = Figure(figsize=(12, 5))
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("VSWR")
        self.ax.set_xlabel("Frequency (kHz)")
        self.ax.set_ylabel("VSWR")

        # Set fixed Y-axis limits
        self.ax.set_ylim(1.0, 2.0)

        self.canvas = FigureCanvasTkAgg(self.figure, self.plot_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def toggle_device_type(self):
        """Toggle between E-Dot and E-Sq"""
        current = self.device_type.get()
        self.device_type.set("E-Sq" if current == "E-Dot" else "E-Dot")
        self.update_test_type_visibility()
        self.update_combined_type()

    def update_combined_type(self):
        """Update the combined type display and get parameters"""
        device = self.device_type.get()
        test = self.test_type.get()
        combined = f"{device}-{test}"
        self.combined_type.set(combined)
        self.get_params(combined)

        # Initialize scanner with current parameters
        try:
            if self.scanner:
                self.scanner.shutdown()
            self.scanner = FrequencyScanner(COMPORT, False)
            self.scanner.setup(
                self.current_params['start_khz'],
                self.current_params['stop_khz'],
                self.current_params['step_khz'],
                self.current_params['dwell_ms']
            )
            self.baseline_btn.config(state='normal')
            self.update_test_results("Scanner Initialized. Click BASELINE to begin")
        except Exception as e:
            messagebox.showerror("Scanner Error", f"Failed to initialize scanner: {str(e)}")
            self.baseline_btn.config(state='disabled')

    def update_test_type_visibility(self):
        """Show/hide Wet option based on device type"""
        if self.device_type.get() == "E-Dot":
            self.wet_radio.pack(side=tk.LEFT)
        else:
            if self.test_type.get() == "Wet":
                self.test_type.set("Element")
            self.wet_radio.pack_forget()

        self.consecutive_passes = 0

    def perform_continuous_scan(self):
        """Perform a single scan and schedule the next one if continuous scanning is enabled"""
        if self.continuous_scan:
            self.perform_scan()  # Your existing scan function
            self.after_id = self.after(100, self.perform_continuous_scan)  # Schedule next scan in 100ms

    def get_params(self, combined_type: str) -> dict:
        """Get scanning parameters based on the combined type from a configuration file"""


        # Try to load parameters from file
        try:
            with open('params.txt', 'r') as f:
                params = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("params.txt not found. Please ensure the configuration file exists.")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format in params.txt. Please check the file format.")

        # Validate that the requested combined_type exists
        if combined_type not in params:
            raise KeyError(f"Configuration for {combined_type} not found in params.txt")

        # Store the current parameters and update display
        self.current_params = params[combined_type]
        self.update_params_display()
        return self.current_params

    def update_params_display(self):
        """Update the RUN PARAMS display with current parameters"""
        params_text = (
            f"Start Frequency: {self.current_params['start_khz']} kHz\n"
            f"Stop Frequency: {self.current_params['stop_khz']} kHz\n"
            f"Step Size: {self.current_params['step_khz']} kHz\n"
            f"Dwell Time: {self.current_params['dwell_ms']} ms\n"
            f"VSWR Start: {self.current_params['vswr_start_khz']} kHz\n"
            f"VSWR Stop: {self.current_params['vswr_stop_khz']} kHz\n"
            f"VSWR Max: {self.current_params['vswr_max']}"
        )

        # Clear existing labels in params_frame
        for widget in self.params_frame.winfo_children():
            widget.destroy()

        # Add new label with parameters
        tk.Label(self.params_frame, text=params_text, justify='left').pack(padx=5, pady=5)

    def initialize_scanner(self):
        """Initialize the FrequencyScanner"""
        try:
            self.scanner = FrequencyScanner(COMPORT, False)
            self.scanner.setup(
                self.current_params['start_khz'],
                self.current_params['stop_khz'],
                self.current_params['step_khz'],
                self.current_params['dwell_ms']
            )
            return True
        except Exception as e:
            messagebox.showerror("Scanner Error", f"Failed to initialize scanner: {str(e)}")
            return False

    def run_baseline(self):
        """Run baseline measurement"""
        try:
            # Get baseline using the function from Analyzer_Granular
            self.baseline = get_highest_baseline(
                self.scanner,
                self.current_params['start_khz'],
                self.current_params['step_khz'],
                10  # Number of measurements to average
            )

            # Enable scan button and scan mode button after baseline is captured
            self.scan_btn.config(state='normal')
            self.scan_mode_btn.config(state='normal')  # Add this line

            # Ensure continuous scan is off until user clicks SCAN
            self.continuous_scan = False
            if hasattr(self, 'after_id') and self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None

            # Update status
            self.update_test_results("Baseline measurement complete - Click SCAN to proceed")

        except Exception as e:
            messagebox.showerror("Baseline Error", f"Failed to get baseline: {str(e)}")
            self.scan_btn.config(state='disabled')

    def update_test_results(self, text):
        """Update the test results display"""
        # Clear existing labels in results_frame
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Add new label with results
        tk.Label(self.results_frame, text=text, justify='left').pack(padx=5, pady=5)

    def plot_vswr_data(self, frequencies, vswr):
        """Plot VSWR data"""
        self.ax.clear()
        self.ax.plot(frequencies, vswr, '-o', markersize=2)  # Reduced marker size from default to 3
        self.ax.set_title("VSWR")
        self.ax.set_xlabel("Frequency (kHz)")
        self.ax.set_ylabel("VSWR")
        self.ax.grid(True)

        # Set fixed Y-axis limits after clearing
        self.ax.set_ylim(1.0, 2.0)

        # Add horizontal line at vswr_max
        self.ax.axhline(y=self.current_params['vswr_max'], color='r', linestyle='--', label='VSWR Max')

        # Add vertical lines for vswr_start_khz and vswr_stop_khz
        self.ax.axvline(x=self.current_params['vswr_start_khz'], color='g', linestyle='--', label='Start')
        self.ax.axvline(x=self.current_params['vswr_stop_khz'], color='g', linestyle='--', label='Stop')

        self.ax.legend()
        self.canvas.draw()

    def highlight_failed_plot(self):
        """Add red background to plot for failed tests"""
        self.ax.set_facecolor('mistyrose')
        self.canvas.draw()
        self.update_test_results("Failed: VSWR exceeds limit")

    def highlight_good_plot(self):
        """Add green background to plot for passing tests"""
        self.ax.set_facecolor('lightgreen')
        self.canvas.draw()
        self.update_test_results("Good: VSWR within limit")

    def highlight_normal_plot(self):
        """Add white background to plot for normal times tests"""
        self.ax.set_facecolor('white')
        self.canvas.draw()

    def mark_save(self):
        """Handle SAVE button click"""
        # Pause continuous scanning while saving
        self.pause_continuous_scan()
        self.update_test_results("Paused while saving plot")

        dialog = tk.Toplevel(self)
        dialog.title("Enter Serial Number")
        dialog.transient(self)
        dialog.grab_set()

        # Make dialog 4 times larger
        dialog_width = 400  # Original was about 100
        dialog_height = 200  # Original was about 50
        dialog.geometry(f"{dialog_width}x{dialog_height}")

        # Create a frame with padding
        frame = tk.Frame(dialog, padx=20, pady=20)
        frame.pack(expand=True, fill='both')

        # Add a label with larger font
        label = tk.Label(frame, text="Enter 5-character Serial Number:", font=('Arial', 14))
        label.pack(pady=(0, 20))

        # Create entry with larger font
        entry = tk.Entry(frame, font=('Arial', 24), width=10, justify='center')
        entry.pack()

        # Reset consectuive pass counter
        self.consecutive_passes = 0

        def validate_and_save(event=None):
            serial = entry.get().upper()
            if len(serial) == 5 and serial.isalpha():
                self.serial = serial
                self.save_plot()
                dialog.destroy()
                # Resume continuous scanning after successful save
                self.resume_continuous_scan()

            else:
                messagebox.showerror("Invalid Input", "Please enter exactly 5 alpha characters")

        entry.bind('<Return>', validate_and_save)

        # Center the dialog on the main window
        def center_dialog():
            # Wait for dialog to be rendered
            dialog.update_idletasks()

            # Get main window position and dimensions
            main_x = self.winfo_x()
            main_y = self.winfo_y()
            main_width = self.winfo_width()
            main_height = self.winfo_height()

            # Calculate position for dialog
            x = main_x + (main_width - dialog_width) // 2
            y = main_y + (main_height - dialog_height) // 2

            # Set dialog position
            dialog.geometry(f"+{x}+{y}")

        # Schedule centering after dialog is fully created
        self.after(10, center_dialog)

        entry.focus_set()

    def save_plot(self):
        """Save the plot with the correct filename"""
        if not self.serial:
            messagebox.showerror("Error", "No serial number provided")
            return

        try:
            # Calculate min, max, and mid VSWR values
            print(self.vswr_data)
            vswr_results = [v[1] for v in self.vswr_data]

            print(self.current_params['vswr_start_khz'])
            print(self.current_params['vswr_stop_khz'])
            print(self.current_params['vswr_mid_khz'])



            try:
                # Assign values with fallback to 5.0 if not found
                min_vswr = get_vswr_at_frequency(self.current_params['vswr_start_khz'], self.vswr_data)
                mid_vswr = get_vswr_at_frequency(self.current_params['vswr_mid_khz'], self.vswr_data)
                max_vswr = get_vswr_at_frequency(self.current_params['vswr_stop_khz'], self.vswr_data)

            except Exception:
                min_vswr = mid_vswr = max_vswr = 5.0


            # Find min vswr and freq between ROI limits
            min_freq_vswr = find_min_vswr_frequency(self.vswr_data,
                                               self.current_params['vswr_start_khz'],
                                               self.current_params['vswr_stop_khz']
                                               )

            min_freq = min_freq_vswr[0]
            lowest_vswr = min_freq_vswr[1]

            # Set the plot title using serial and combined type
            combined_type = f"{self.device_type.get()}-{self.test_type.get()}"
            new_title = f"{self.serial} {combined_type}"
            self.ax.set_title(new_title)
            self.canvas.draw()

            # Format the filename
            filename = self.current_params['filename_template']

            filename = filename.replace('SERIAL', self.serial)
            filename = filename.replace('nnnnnnn', f"{min_freq:07d}")
            filename = filename.replace('m.mm', f"{lowest_vswr:.2f}")
            filename = filename.replace('x.xx', f"{min_vswr:.2f}")
            filename = filename.replace('y.yy', f"{mid_vswr:.2f}")
            filename = filename.replace('z.zz', f"{max_vswr:.2f}")

            print(filename)

            # Add .png extension
            save_path = os.path.join(self.current_params['file_save_path'], filename + '.png')

            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save the plot
            self.figure.savefig(save_path, bbox_inches='tight', dpi=300)

            # Clear the serial number
            self.serial = None

            # Update the test results display
            self.update_test_results("")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plot: {str(e)}")
            # DO NOT add any scanning logic here

    def show_save_confirmation_dialog(self, save_path):
        """Show confirmation dialog after successful save"""
        dialog = tk.Toplevel(self)
        dialog.title("Success")

        # Set size 4x larger than default
        dialog_width = 400
        dialog_height = 200
        dialog.geometry(f"{dialog_width}x{dialog_height}")

        # Make dialog modal
        dialog.transient(self)
        dialog.grab_set()

        # Configure dialog
        dialog.configure(bg='white')
        dialog.resizable(False, False)

        # Add message with larger font
        message = tk.Label(dialog,
                          text=f"Plot saved successfully as:\n\n{save_path}",
                          font=('TkDefaultFont', 12),
                          wraplength=350,
                          justify='center',
                          bg='white')
        message.pack(expand=True, pady=20)

        # Add OK button with larger font
        ok_button = tk.Button(dialog,
                             text="OK",
                             command=dialog.destroy,
                             width=20,
                             font=('TkDefaultFont', 10))
        ok_button.pack(pady=20)

        # Center dialog in main window
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog_width) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog_height) // 2
        dialog.geometry(f"+{x}+{y}")

        # Wait for dialog to be closed
        self.wait_window(dialog)

    def exit_application(self):
        """Clean up and exit"""
        if self.scanner:
            try:
                self.scanner.shutdown()
            except Exception as e:
                messagebox.showerror("Shutdown Error", f"Error during scanner shutdown: {str(e)}")
        self.quit()

    def update_status(self, message):
        """Update status in results frame"""
        self.update_test_results(message)

    def update_button_states(self):
        """Update the state of buttons based on current conditions"""
        # Initially all buttons except device/test type are disabled
        self.baseline_btn.config(state='disabled')
        self.scan_btn.config(state='disabled')
        self.save_btn.config(state='disabled')

    def perform_scan(self):
        """Execute a single scan operation"""
        if not hasattr(self, 'scanner') or not self.scanner:
            return

        # Get scan parameters based on current mode
        params = self.get_params(f"{self.device_type.get()}-{self.test_type.get()}")

        try:
            # Use the run method instead of perform_scan
            raw_results = self.scanner.run(
                params['start_khz'],
                params['step_khz']
            )

            # Process the results if we have a baseline
            if self.baseline is not None:
                # Subtract baseline from raw results
                baseline_corrected = subtract_baseline(raw_results, self.baseline)

                # Convert return loss measurements to VSWR values
                vswr_results = [(freq, calculate_vswr(return_loss))
                               for freq, return_loss in baseline_corrected]
                # print(f"vswr_results: {vswr_results}")
                # Apply smoothing with required frequency parameters

                choice = 'cubic' # random.choice(['none', 'cubic', 'spline'])

                vswr_results = interpolated(
                    vswr_results,
                    interpolation_factor=3,
                    method= choice  # or 'spline' or 'none'
                )

                vswr_results = add_vswr_criterion_points(
                    vswr_results,
                    params['vswr_start_khz'],
                    params['vswr_stop_khz'],
                    params['vswr_mid_khz'],
                )

                vswr_results = smoothed(
                    vswr_results,
                    params['vswr_start_khz'],
                    params['vswr_stop_khz'],
                    params['vswr_mid_khz'],
                    interpolation_factor=3,
                    method= choice  # or 'spline' or 'none'
                )


                self.update_test_results('choice')

                # Store the VSWR data
                self.vswr_data = vswr_results  # Add this line

                # print(f"vswr_results: {vswr_results}")

                # Extract frequencies and VSWR values for plotting
                frequencies = [r[0] for r in vswr_results]
                vswr = [r[1] for r in vswr_results]
                
                # Update the plot
                self.plot_vswr_data(frequencies, vswr)
                
                # Check VSWR limits
                #We dont need vswr_mid_khz here - we are checking its below threshold in the start-stop range
                passed = evaluate_vswr_range(
                    vswr_results,
                    params['vswr_start_khz'],
                    params['vswr_stop_khz'],
                    params['vswr_max']
                )
                
                if passed:
                    self.highlight_good_plot()
                else:
                    self.highlight_failed_plot()
                
                # Store last successful scan data if passed
                if passed:
                    self.last_scan_data = self.vswr_data.copy()  # Make a copy of the data
                # Handle consecutive passes
                if passed:
                    self.consecutive_passes += 1
                    if self.consecutive_passes >= 5:
                        # Stop continuous scanning
                        self.continuous_scan = False
                        # Make sure we use the last successful scan data
                        self.vswr_data = self.last_scan_data
                        result_text = f"{self.consecutive_passes} Consecutive Passes - Do you want to save the plot?"
                        self.update_test_results(result_text)
                        return
                    else:
                        result_text = f"{self.consecutive_passes} Consecutive Passes"
                        self.update_test_results(result_text)
                else:
                    # Reset counter if test fails
                    self.consecutive_passes = 0
            else:
                # If no baseline, just plot raw data
                frequencies = [r[0] for r in raw_results]
                values = [r[1] for r in raw_results]
                self.plot_vswr_data(frequencies, values)

            self.save_btn.config(state='normal') #allow saving

        except Exception as e:
            print(f"Scan error: {str(e)}")
            self.continuous_scan = False
            

    def on_closing(self):
        """Handle window closing"""
        # Stop continuous scanning
        self.continuous_scan = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
    
        # Shutdown scanner and close
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.shutdown()
    
        self.quit()

    def on_scan_click(self):
        """Handler for scan button click"""
        if self.baseline is None:
            messagebox.showerror("Error", "Baseline measurement required before scanning")
            return
        
        # Clear any existing continuous scan
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        
        # Start scanning based on mode
        if self.scan_mode.get() == "Continuous":
            self.continuous_scan = True
            self.perform_continuous_scan()
        else:
            self.continuous_scan = False
            self.perform_scan()

    def pause_continuous_scan(self):
        """Temporarily pause continuous scanning"""
        self.continuous_scan = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def resume_continuous_scan(self):
        """Resume continuous scanning if in continuous mode"""
        if self.scan_mode.get() == "Continuous":
            self.continuous_scan = True
            self.perform_continuous_scan()

    def toggle_scan_mode(self):
        """Toggle between Single and Continuous scan modes"""
        current = self.scan_mode.get()
        new_mode = "Continuous" if current == "Single" else "Single"
        self.scan_mode.set(new_mode)
        
        if new_mode == "Single":
            # Stop continuous scanning
            self.continuous_scan = False
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
        else:
            # Start continuous scanning
            self.continuous_scan = True
            self.perform_continuous_scan()

if __name__ == "__main__":
    app = VSWRAnalyzer()
    app.mainloop()