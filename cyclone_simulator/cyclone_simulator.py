import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.io as pio
import webbrowser
import tempfile
import os
from openpyxl import load_workbook

def partition_curve(size, d50, separation_quality):
    return 1 / (1 + (size / d50) ** separation_quality)

def classification_efficiency(df):
    df["Efficiency"] = abs(df["Partition Probability"] - 0.5) * 200
    return df

def cumulative_distribution(df):
    df_sorted = df.sort_values("Size (microns)").copy()
    df_sorted["Cumulative Passing"] = df_sorted["Weight Fraction"].cumsum() * 100
    return df_sorted

def simulate_partition(df, d50, separation_quality):
    df["Partition Probability"] = df["Size (microns)"].apply(lambda x: partition_curve(x, d50, separation_quality))
    df["Overflow Fraction"] = df["Weight Fraction"] * df["Partition Probability"]
    df["Underflow Fraction"] = df["Weight Fraction"] * (1 - df["Partition Probability"])
    return df

class CycloneSimulator:
    def __init__(self, master):
        self.master = master
        self.master.title("⚙️ Cyclone Simulator with Interactive Graphs")
        self.master.geometry("1000x720")
        self.df = None
        self.result_df = None

        self.d50 = 50.0
        self.separation_quality = 2.0
        self.simulation_count = 1

        self.create_widgets()

    def create_widgets(self):
        title = ttk.Label(self.master, text="Cyclone Simulation Tool", font=("Segoe UI", 16))
        title.pack(pady=10)

        control_frame = ttk.Frame(self.master)
        control_frame.pack(pady=10)

        ttk.Button(control_frame, text="📂 Load Size Distribution CSV", command=self.load_csv).grid(row=0, column=0, padx=10)
        ttk.Label(control_frame, text="D50 (µm):").grid(row=0, column=1)
        self.d50_entry = ttk.Entry(control_frame, width=10)
        self.d50_entry.insert(0, str(self.d50))
        self.d50_entry.grid(row=0, column=2, padx=5)

        ttk.Button(control_frame, text="▶ Simulate & Visualize", command=self.run_simulation).grid(row=0, column=3, padx=10)
        ttk.Button(control_frame, text="💾 Export to Excel", command=self.export_to_excel).grid(row=0, column=4, padx=10)

    def load_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if filepath:
            try:
                self.df = pd.read_csv(filepath)
                if not {"Size (microns)", "Weight Fraction"}.issubset(self.df.columns):
                    raise ValueError("Invalid columns in CSV.")
                messagebox.showinfo("Success", "CSV loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def run_simulation(self):
        if self.df is None:
            messagebox.showerror("Error", "Please load a CSV file first.")
            return

        try:
            self.d50 = float(self.d50_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid D50 value.")
            return

        self.show_graph_interface()

    def update_slider_label(self, val):
        self.slider_label.config(text=f"{float(val):.1f}")
        self.separation_quality = float(val)
        self.update_plot()

    def update_plot(self):
        df_sim = simulate_partition(self.df.copy(), self.d50, self.separation_quality)
        df_sim = classification_efficiency(df_sim)
        df_sim = cumulative_distribution(df_sim)
        self.result_df = df_sim

        fig = make_subplots(rows=3, cols=2, subplot_titles=[
            "1. Partition Curve",
            "2. Classification Efficiency",
            "3. D50 Optimization Curve",
            "4. Tromp Curve",
            "5. Overflow vs Underflow",
            ""
        ])

        # Partition Curve
        fig.add_trace(go.Scatter(
            x=df_sim["Size (microns)"], y=df_sim["Partition Probability"],
            mode="lines+markers", name="Partition",
            hovertemplate="Size: %{x} µm<br>Prob: %{y:.2f}"
        ), row=1, col=1)

        # Efficiency
        fig.add_trace(go.Scatter(
            x=df_sim["Size (microns)"], y=df_sim["Efficiency"],
            mode="lines+markers", name="Efficiency",
            hovertemplate="Size: %{x} µm<br>Eff: %{y:.1f}%"
        ), row=1, col=2)

        # D50 Cumulative
        fig.add_trace(go.Scatter(
            x=df_sim["Size (microns)"], y=df_sim["Cumulative Passing"],
            mode="lines+markers", name="Cumulative Passing",
            hovertemplate="Size: %{x} µm<br>Passing: %{y:.1f}%"
        ), row=2, col=1)
        fig.add_shape(type="line", x0=self.d50, x1=self.d50, y0=0, y1=100,
                      line=dict(color="red", dash="dash"), row=2, col=1)

        # Tromp
        fig.add_trace(go.Scatter(
            x=df_sim["Size (microns)"], y=df_sim["Partition Probability"],
            mode="lines+markers", name="Tromp",
            hovertemplate="Size: %{x} µm<br>Prob: %{y:.2f}"
        ), row=2, col=2)

        # Overflow and Underflow
        fig.add_trace(go.Bar(
            x=df_sim["Size (microns)"], y=df_sim["Underflow Fraction"] * 100,
            name="Underflow %",
            marker=dict(color='blue'),
            hovertemplate="Size: %{x} µm<br>Underflow: %{y:.1f}%"
        ), row=3, col=1)

        fig.add_trace(go.Bar(
            x=df_sim["Size (microns)"], y=df_sim["Overflow Fraction"] * 100,
            name="Overflow %",
            marker=dict(color='orange'),
            hovertemplate="Size: %{x} µm<br>Overflow: %{y:.1f}%"
        ), row=3, col=1)

        # Axes labels
        for i in range(1, 4):
            fig.update_xaxes(title_text="Particle Size (µm)", row=i, col=1)
            fig.update_xaxes(title_text="Particle Size (µm)", row=i, col=2)
        fig.update_yaxes(title_text="Partition Probability", row=1, col=1)
        fig.update_yaxes(title_text="Efficiency (%)", row=1, col=2)
        fig.update_yaxes(title_text="Cumulative Passing (%)", row=2, col=1)
        fig.update_yaxes(title_text="Probability of Separation", row=2, col=2)
        fig.update_yaxes(title_text="Mass Fraction (%)", row=3, col=1)

        fig.update_layout(height=900, width=1200, title="Cyclone Simulation Results", showlegend=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            pio.write_html(fig, file=f.name, auto_open=True)

    def show_graph_interface(self):
        window = tk.Toplevel(self.master)
        window.title("Interactive Graphs & Separation Quality")
        window.geometry("400x120")

        ttk.Label(window, text="Separation Quality").pack(pady=(10, 0))
        self.slider = ttk.Scale(window, from_=1.0, to=10.0, orient=tk.HORIZONTAL, length=300,
                                command=self.update_slider_label)
        self.slider.set(self.separation_quality)
        self.slider.pack(pady=(0, 5))

        self.slider_label = ttk.Label(window, text=f"{self.separation_quality:.1f}")
        self.slider_label.pack()

        self.update_plot()

    def export_to_excel(self):
        if self.result_df is None:
            messagebox.showerror("Error", "Please run the simulation first.")
            return

        file_path = "exp_pro.xlsx"

        try:
            if os.path.exists(file_path):
                book = load_workbook(file_path)
                writer = pd.ExcelWriter(file_path, engine='openpyxl')
                writer.book = book
                sheet_name = f"Simulation_{len(book.sheetnames) + 1}"
            else:
                writer = pd.ExcelWriter(file_path, engine='openpyxl')
                sheet_name = "Simulation_1"

            self.result_df.to_excel(writer, sheet_name=sheet_name, index=False)
            writer.close()
            messagebox.showinfo("Success", f"Exported to {file_path} in sheet '{sheet_name}'")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CycloneSimulator(root)
    root.mainloop()
