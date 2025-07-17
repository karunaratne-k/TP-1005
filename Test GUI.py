import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
from typing import Dict, Tuple, List
# Add these imports at the top of the file
from Analyzer_Granular import FrequencyScanner, get_highest_baseline, evaluate_vswr_range
import os

COMPORT = "COM6"  # Static definition as requested

class VSWRAnalyzer(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Add initialization of current_params
        self.current_params = None
        
        self.title("VSWR Analyzer")
        self.geometry("1200x800")
        
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
        
        # Test Type Toggle Button
        self.test_btn = tk.Button(
            self.control_frame,
            textvariable=self.test_type,
            command=self.toggle_test_type,
            width=10
        )
        self.test_btn.place(x=120, y=10)
        
        # Combined type display
        self.type_label = tk.Label(
            self.control_frame,
            textvariable=self.combined_type
        )
        self.type_label.place(x=230, y=10)
        
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
        
        self.canvas = FigureCanvasTkAgg(self.figure, self.plot_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def toggle_device_type(self):
        """Toggle between E-Dot and E-Sq"""
        current = self.device_type.get()
        self.device_type.set("E-Sq" if current == "E-Dot" else "E-Dot")
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
        
    def get_params(self, combined_type: str) -> dict:
        """Get scanning parameters based on the combined type"""
        params = {
            "E-Dot-Final": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 600,
                "dwell_ms": 20,
                "vswr_start_khz": 1_616_000,
                "vswr_stop_khz": 1_626_500,
                "vswr_max": 1.5,
                "filename_template": "SERIAL_E-Dot-FINAL_VSWR-minF-nnnnnnn-VSWR-minV-m.mm_VSWR-min-x.xx_VSWR-mid-y.yy_VSWR-max-z.zz",
                "file_save_path": "C:\\data"
            },
            "E-Dot-Element": {
                "start_khz": 1_606_250,
                "stop_khz": 1_636_250,
                "step_khz": 600,
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
                "step_khz": 600,
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
                "step_khz": 600,
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
            self.baseline = get_highest_baseline(
                self.scanner,
                self.current_params['start_khz'],
                self.current_params['step_khz'],
                10
            )
            
            # Enable other buttons after baseline is complete
            self.scan_btn.config(state='normal')
            self.good_btn.config(state='normal')
            
            # Update status
            self.update_status("Baseline measurement complete")
            
        except Exception as e:
            messagebox.showerror("Baseline Error", f"Failed to get baseline: {str(e)}")

    def run_scan(self):
        """Run the VSWR scan"""
        try:
            # Get scan results from scanner with required parameters
            results_vswr = self.scanner.run(
                self.current_params['start_khz'],
                self.current_params['step_khz']
            )
            
            # Extract frequencies and VSWR values
            frequencies = [r[0] for r in results_vswr]
            vswr = [r[1] for r in results_vswr]
            vswr_data = list(zip(frequencies, vswr))
            
            # Evaluate VSWR range
            passed = evaluate_vswr_range(
                vswr_data,
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

if __name__ == "__main__":
    app = VSWRAnalyzer()
    app.mainloop()