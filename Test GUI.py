import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
from typing import Dict, Tuple, List
# Add these imports at the top of the file
from Analyzer_Granular import (
    FrequencyScanner, 
    get_highest_baseline,
    subtract_baseline,
    calculate_vswr,
    process_vswr_data,
    evaluate_vswr_range
)
import os

COMPORT = "COM6"  # Static definition as requested

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
        
        # Variables
        self.device_type = tk.StringVar(value="E-Dot")
        self.test_type = tk.StringVar(value="Element")
        self.combined_type = tk.StringVar()
        self.scanner = None
        self.baseline = None
        self.serial = None
        
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
            command=self.run_scan,
            state='disabled',
            width=10
        )
        self.scan_btn.place(x=120, y=260)
        
        self.good_btn = tk.Button(
            self.control_frame,
            text="GOOD",
            command=self.mark_good,
            state='disabled',
            width=10
        )
        self.good_btn.place(x=230, y=260)
        
        self.exit_btn = tk.Button(
            self.control_frame,
            text="EXIT",
            command=self.exit_application,
            width=10
        )
        self.exit_btn.place(x=340, y=260)
        
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

    def toggle_test_type(self):
        """Toggle between Element and Final"""
        current = self.test_type.get()
        self.test_type.set("Final" if current == "Element" else "Element")
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
        except Exception as e:
            messagebox.showerror("Scanner Error", f"Failed to initialize scanner: {str(e)}")
            self.baseline_btn.config(state='disabled')

    def update_test_type_visibility(self):
        """Show/hide Wet option based on device type and handle continuous scanning"""
        if self.device_type.get() == "E-Dot":
            self.wet_radio.pack(side=tk.LEFT)
            # If currently "Wet" and switching to E-Sq, change to "Element"
        else:
            if self.test_type.get() == "Wet":
                self.test_type.set("Element")
            self.wet_radio.pack_forget()
    
        # Update continuous scanning based on test type
        self.update_continuous_scan()

    def update_continuous_scan(self):
        """Start or stop continuous scanning based on test type"""
        test_type = self.test_type.get()
        
        # Cancel any existing scheduled updates
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        
        # Start continuous scanning for Element or Wet modes
        if test_type in ["Element", "Wet"]:
            self.continuous_scan = True
            self.perform_continuous_scan()
        else:
            self.continuous_scan = False

    def perform_continuous_scan(self):
        """Perform a single scan and schedule the next one if continuous scanning is enabled"""
        if self.continuous_scan:
            self.perform_scan()  # Your existing scan function
            self.after_id = self.after(100, self.perform_continuous_scan)  # Schedule next scan in 100ms

    def get_params(self, combined_type: str) -> dict:
        """Get scanning parameters based on the combined type"""
        params = {
            "E-Dot-Final": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 1200,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 1.5,
                "filename_template": "SERIAL_E-Dot-FINAL_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz",
                "file_save_path": "C:\\data"
            },
            "E-Dot-Wet": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 300,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 2.0,
                "filename_template": 'SERIAL_E-Dot-WET_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz',
                "file_save_path": 'C:\\data'
            },
            "E-Dot-Element": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 1200,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 1.5,
                "filename_template": "SERIAL_E-Dot-ELEMENT_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz",
                "file_save_path": "C:\\data"
            },
            "E-Sq-Final": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 1200,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 1.5,
                "filename_template": "SERIAL_E-Sq-FINAL_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz",
                "file_save_path": "C:\\data"
            },
            "E-Sq-Element": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 1200,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 1.5,
                "filename_template": "SERIAL_E-Sq-ELEMENT_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz",
                "file_save_path": "C:\\data"
            }
        }
        
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

    # Add these methods to the VSWRAnalyzer class

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
            
            # Enable scan button after baseline is captured
            self.scan_btn.config(state='normal')
            
            # Update status
            self.update_test_results("Baseline measurement complete")
            
        except Exception as e:
            messagebox.showerror("Baseline Error", f"Failed to get baseline: {str(e)}")
            self.scan_btn.config(state='disabled')

    def run_scan(self):
        """Run the VSWR scan"""
        try:
            if self.baseline is None:
                messagebox.showerror("Error", "Baseline measurement required before scanning")
                return
                
            # Get raw results from scanner
            raw_results = self.scanner.run(
                self.current_params['start_khz'],
                self.current_params['step_khz']
            )
            
            # Subtract baseline from raw results
            baseline_corrected = subtract_baseline(raw_results, self.baseline)
            
            # Convert return loss measurements to VSWR values
            vswr_results = [(freq, calculate_vswr(return_loss)) 
                           for freq, return_loss in baseline_corrected]
            
            # Store VSWR data for later use (needed for save_plot)
            self.vswr_data = vswr_results
            
            # Extract frequencies and VSWR values for plotting
            frequencies = [r[0] for r in vswr_results]
            vswr = [r[1] for r in vswr_results]
            
            # Evaluate VSWR range
            passed = evaluate_vswr_range(
                vswr_results,
                self.current_params['vswr_start_khz'],
                self.current_params['vswr_stop_khz'],
                self.current_params['vswr_max']
            )
            
            # Update test results display
            result_text = "VSWR test passed - all values within limits" if passed else "VSWR test failed - limit exceeded"
            self.update_test_results(result_text)
            
            # Plot the data
            self.plot_vswr_data(frequencies, vswr)
            
            # If in FINAL mode and test failed, highlight the plot
            if self.test_type.get() == "Final" and not passed:
                self.highlight_failed_plot()
                
            # Enable the GOOD button if test passed
            self.good_btn.config(state='normal' if passed else 'disabled')
                
        except Exception as e:
            messagebox.showerror("Scan Error", f"Failed to complete scan: {str(e)}")

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
        self.ax.plot(frequencies, vswr, '-o')
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

    def mark_good(self):
        """Handle GOOD button click"""
        dialog = tk.Toplevel(self)
        dialog.title("Enter Serial Number")
        dialog.transient(self)
        dialog.grab_set()
        
        entry = tk.Entry(dialog)
        entry.pack(padx=20, pady=10)
        
        def validate_and_save(event=None):
            serial = entry.get().upper()
            if len(serial) == 5 and serial.isalpha():
                self.serial = serial
                self.save_plot()
                dialog.destroy()
            else:
                messagebox.showerror("Invalid Input", "Please enter exactly 5 alpha characters")
        
        entry.bind('<Return>', validate_and_save)
        entry.focus_set()

    def save_plot(self):
        """Save the plot with the correct filename"""
        try:
            if not self.serial:
                messagebox.showerror("Error", "No serial number provided")
                return

            # Calculate min, max, and mid VSWR values
            vswr_values = [v[1] for v in self.vswr_data]
            min_vswr = min(vswr_values)
            max_vswr = max(vswr_values)
            mid_vswr = (min_vswr + max_vswr) / 2
            min_freq = min(v[0] for v in self.vswr_data)

            # Format the filename, removing any file extension from the template
            filename = self.current_params['filename_template']
            if filename.endswith('.zz'):
                filename = filename[:-3]  # Remove .zz extension if present

            filename = filename.replace('SERIAL', self.serial)
            filename = filename.replace('nnnnnnn', f"{min_freq:07d}")
            filename = filename.replace('m.mm', f"{min_vswr:.2f}")
            filename = filename.replace('x.xx', f"{min_vswr:.2f}")
            filename = filename.replace('y.yy', f"{mid_vswr:.2f}")
            filename = filename.replace('z.zz', f"{max_vswr:.2f}")

            # Add .png extension
            save_path = os.path.join(self.current_params['file_save_path'], filename + '.png')

            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save the plot
            self.figure.savefig(save_path, bbox_inches='tight', dpi=300)
            messagebox.showinfo("Success", f"Plot saved as {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save plot: {str(e)}")

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
        self.good_btn.config(state='disabled')

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
            
                # Extract frequencies and VSWR values for plotting
                frequencies = [r[0] for r in vswr_results]
                vswr = [r[1] for r in vswr_results]
            
                # Update the plot
                self.plot_vswr_data(frequencies, vswr)
            
                # Check VSWR limits
                passed = evaluate_vswr_range(
                    vswr_results,
                    params['vswr_start_khz'],
                    params['vswr_stop_khz'],
                    params['vswr_max']
                )
            
                # Update test results
                result_text = "VSWR test passed - all values within limits" if passed else "VSWR test failed - limit exceeded"
                self.update_test_results(result_text)
            
            else:
                # If no baseline, just plot raw data
                frequencies = [r[0] for r in raw_results]
                values = [r[1] for r in raw_results]
                self.plot_vswr_data(frequencies, values)
            
        except Exception as e:
            print(f"Scan error: {str(e)}")
            self.continuous_scan = False

    def on_closing(self):
        """Handle window closing"""
        # Stop continuous scanning
        self.continuous_scan = False
        if self.after_id:
            self.after_cancel(self.after_id)
    
        # Shutdown scanner and close
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.shutdown()
    
        self.quit()

if __name__ == "__main__":
    app = VSWRAnalyzer()
    app.mainloop()