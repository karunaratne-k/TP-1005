import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_points, current_range):
        super().__init__(parent)
        self.title("Plot Settings")
        self.resizable(False, False)

        # Create and set up the main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Number of points
        ttk.Label(main_frame, text="Number of points:").grid(row=0, column=0, sticky=tk.W)
        self.points_var = tk.StringVar(value=str(current_points))
        self.points_entry = ttk.Entry(main_frame, textvariable=self.points_var)
        self.points_entry.grid(row=0, column=1, padx=5, pady=5)

        # Range settings
        ttk.Label(main_frame, text="Data range:").grid(row=1, column=0, sticky=tk.W)
        range_frame = ttk.Frame(main_frame)
        range_frame.grid(row=1, column=1, sticky=(tk.W, tk.E))

        self.min_var = tk.StringVar(value=str(current_range[0]))
        self.max_var = tk.StringVar(value=str(current_range[1]))

        ttk.Label(range_frame, text="Min:").pack(side=tk.LEFT)
        self.min_entry = ttk.Entry(range_frame, textvariable=self.min_var, width=10)
        self.min_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(range_frame, text="Max:").pack(side=tk.LEFT)
        self.max_entry = ttk.Entry(range_frame, textvariable=self.max_var, width=10)
        self.max_entry.pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)

        self.result = None

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def ok_clicked(self):
        try:
            points = int(self.points_var.get())
            min_val = float(self.min_var.get())
            max_val = float(self.max_var.get())

            if points < 2:
                raise ValueError("Number of points must be at least 2")
            if min_val >= max_val:
                raise ValueError("Maximum value must be greater than minimum value")

            self.result = (points, (min_val, max_val))
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    def cancel_clicked(self):
        self.destroy()


class PlotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Random Numbers Plot")
        
        # Plot settings
        self.num_points = 100
        self.data_range = (0, 1)
        self.data_generated = False
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create numeric entry frame
        self.entry_frame = ttk.Frame(self.main_frame)
        self.entry_frame.grid(row=0, column=0, pady=(0, 10), sticky=(tk.W, tk.E))
        
        # Create numeric entry with label
        ttk.Label(self.entry_frame, text="Enter a number:").pack(side=tk.LEFT, padx=(0, 5))
        self.numeric_entry = ttk.Entry(self.entry_frame, width=20)
        self.numeric_entry.pack(side=tk.LEFT)
        
        # Create figure frame
        self.fig_frame = ttk.Frame(self.main_frame)
        self.fig_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create figure
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.fig_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create button frame
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=2, column=0, pady=10, sticky=(tk.W, tk.E))
        
        # Create buttons
        self.refresh_btn = ttk.Button(self.button_frame, text="Generate New Data",
                                    command=self.refresh_plot)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        self.settings_btn = ttk.Button(self.button_frame, text="Plot Settings",
                                    command=self.show_settings)
        self.settings_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(self.button_frame, text="Save Plot",
                                command=self.save_plot)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.close_btn = ttk.Button(self.button_frame, text="Close Window",
                                command=self.root.destroy, state='disabled')
        self.close_btn.pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)  # Make the figure frame expandable
        
        # Initial plot
        self.ax.set_title("Click 'Generate New Data' to begin")
        self.canvas.draw()
        
        # Set focus to the numeric entry
        self.numeric_entry.focus_set()
        
        # Optional: Select any pre-existing text in the entry
        self.numeric_entry.select_range(0, tk.END)

    def show_settings(self):
        dialog = SettingsDialog(self.root, self.num_points, self.data_range)
        self.root.wait_window(dialog)

        if dialog.result:
            self.num_points, self.data_range = dialog.result
            self.refresh_plot()

    def refresh_plot(self):
        # Generate new random data with current settings
        self.data = np.random.uniform(
            self.data_range[0],
            self.data_range[1],
            self.num_points
        )

        # Find the peak value and its index
        peak_index = np.argmax(self.data)
        peak_value = self.data[peak_index]

        # Clear the plot and redraw
        self.ax.clear()
        
        # Plot all points in blue
        self.ax.plot(self.data, '-o', color='blue', label='Values')
        
        # Plot peak point in red
        self.ax.plot(peak_index, peak_value, 'ro', markersize=10, label='Peak Value')
        
        self.ax.set_title(f'{self.num_points} Random Numbers')
        self.ax.set_xlabel('Index')
        self.ax.set_ylabel('Value')
        self.ax.grid(True)
        self.ax.legend()

        # Add peak value text
        self.ax.text(0.02, 0.98, f'Peak Value: {peak_value:.2f}',
                    transform=self.ax.transAxes,
                    verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Enable close button after first data generation
        self.close_btn.configure(state='normal')

        # Refresh the canvas
        self.canvas.draw()

    def save_plot(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[
                ('PNG files', '*.png'),
                ('JPEG files', '*.jpg'),
                ('PDF files', '*.pdf'),
                ('All files', '*.*')
            ]
        )

        if file_path:
            try:
                self.fig.savefig(file_path, bbox_inches='tight', dpi=300)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save the plot: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = PlotApp(root)
    root.mainloop()