import os
import sys
import csv
import pandas as pd # Now definitely needed for DataFrame handling
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QFileDialog, QProgressBar, QTextEdit, QLineEdit, QComboBox, QGroupBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QFont

# --- Import the backend logic ---
# Directly import the module. The script will fail if eegBandPower.py is not found.
import eegBandPower


# Thread class for performing EEG band power calculations in the background.
class EEGAnalyzerThread(QThread):
    # Signal to update the progress bar (0-100)
    progress = pyqtSignal(int)
    # Signal when calculation is complete -> emits DataFrame or Exception object
    finished = pyqtSignal(object) # Changed to object to emit DataFrame or Exception
    # Signal for status updates (strings)
    status_update = pyqtSignal(str)

    # Removed analysis_method from __init__
    def __init__(self, input_file, lower_bound, upper_bound, epoch_length, sample_frequency):
        super().__init__()
        self.input_file = input_file
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.epoch_length = epoch_length # This is the segment length for spectrogram
        self.sample_frequency = sample_frequency

    def run(self):
        """
        Calls the EEG band power calculation function (Welch principles, per epoch)
        and emits results as a DataFrame or an Exception.
        """
        try:
            # Assuming channel 0 for now
            results_df = eegBandPower.calculate_band_powers(
                file_path=self.input_file,
                lower_bound=self.lower_bound,
                upper_bound=self.upper_bound,
                epoch_length=self.epoch_length, # Pass segment length
                sample_frequency=self.sample_frequency,
                progress_callback=self.progress.emit,
                channel_index=0
            )
            # Backend now returns DataFrame directly or empty DataFrame on failure
            if results_df is None or results_df.empty:
                 self.status_update.emit("Calculation finished, but no results were generated.")
                 # Emit empty DataFrame to signal no results (handled in on_analysis_complete)
                 self.finished.emit(pd.DataFrame())
            else:
                self.status_update.emit(f"Calculation successful. Found {len(results_df)} epochs.")
                self.finished.emit(results_df) # Emit the DataFrame

        except Exception as e:
            error_msg = f"Error during calculation: {str(e)}"
            self.status_update.emit(error_msg)
            self.finished.emit(e) # Emit the exception object on error

# Main GUI class for EEG Band Power Analysis
class EEGBandPowerGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("EEG Band Power Calculator") # Updated title
        self.setGeometry(100, 100, 600, 480)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # --- File Selection Section ---
        file_box = QGroupBox("File Selection")
        file_box.setStyleSheet("""
            QGroupBox { font-weight: bold; margin-top: 20px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }
        """)
        file_layout = QHBoxLayout()
        layout.addSpacing(20) 

        self.file_label = QLabel("No file selected.")
        self.file_label.setWordWrap(True)
        file_layout.addWidget(self.file_label, 1)

        self.file_button = QPushButton("Choose File")
        self.file_button.clicked.connect(self.open_file_dialog)
        file_layout.addWidget(self.file_button)

        file_box.setLayout(file_layout)
        layout.addWidget(file_box)

        # --- Analysis Parameters Section ---
        analysis_box = QGroupBox("Analysis Parameters")
        analysis_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                margin-top: 1.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
            }
        """)
        
        analysis_layout = QVBoxLayout()
        layout.addSpacing(20)

        # Analysis Parameters (Segment Length & Sample Frequency) - Row 1
        param_layout = QGridLayout()
        # Label changed to reflect segment length for spectrogram/Welch
        self.epoch_label = QLabel("Epoch Length (s):")
        self.epoch_input = QLineEdit("2") # Default 2s
        self.epoch_input.setFixedWidth(60)
        self.epoch_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sample_frequency_label = QLabel("Sample Frequency (Hz):")
        self.sample_frequency_input = QLineEdit("128")
        self.sample_frequency_input.setFixedWidth(60)
        self.sample_frequency_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        param_layout.addWidget(self.epoch_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        param_layout.addWidget(self.epoch_input, 0, 1)
        param_layout.addWidget(self.sample_frequency_label, 0, 2, Qt.AlignmentFlag.AlignRight)
        param_layout.addWidget(self.sample_frequency_input, 0, 3)
        param_layout.setColumnStretch(1, 1)
        param_layout.setColumnStretch(3, 1)
        param_layout.setHorizontalSpacing(15)
        analysis_layout.addLayout(param_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        analysis_layout.addWidget(divider)

        # Frequency Range Selection - Row 2
        freq_layout = QGridLayout()
        self.lower_bound_label = QLabel("Lower Bound (Hz):")
        self.lower_bound_input = QLineEdit("1") # Default 1Hz
        self.lower_bound_input.setFixedWidth(60)
        self.lower_bound_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.upper_bound_label = QLabel("Upper Bound (Hz):")
        self.upper_bound_input = QLineEdit("30")
        self.upper_bound_input.setFixedWidth(60)
        self.upper_bound_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        freq_layout.addWidget(self.lower_bound_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        freq_layout.addWidget(self.lower_bound_input, 0, 1)
        freq_layout.addWidget(self.upper_bound_label, 0, 2, Qt.AlignmentFlag.AlignRight)
        freq_layout.addWidget(self.upper_bound_input, 0, 3)
        freq_layout.setColumnStretch(1, 1)
        freq_layout.setColumnStretch(3, 1)
        freq_layout.setHorizontalSpacing(15)
        analysis_layout.addLayout(freq_layout)

        analysis_box.setLayout(analysis_layout)
        layout.addWidget(analysis_box)
        layout.addSpacing(20)
        # --- Calculate Button ---
        self.calculate_button = QPushButton("Calculate Band Powers")
        self.calculate_button.clicked.connect(self.start_analysis)
        self.calculate_button.setFixedHeight(40)
        self.calculate_button.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.calculate_button)


        
        # --- Export Button ---
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setFixedHeight(40)
        self.export_button.setEnabled(False)  # Disabled until results are available
        layout.addWidget(self.export_button)
        layout.addSpacing(10)
        
        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        
        # --- Status/Log Display ---
        log_box = QGroupBox() # Renamed from Log / Results

        log_layout = QVBoxLayout()
        
        self.results_display = QTextEdit() # Use QTextEdit primarily for logging now
        self.results_display.setReadOnly(True)
        # Adjust height if needed, or let it expand
        self.results_display.setFixedHeight(220) # Example fixed height
        self.results_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        
        # *** Set Monospaced Font ***
        mono_font = QFont("Courier") # Or "Consolas", "Monospace", etc.
        mono_font.setPointSize(12)   # Set point size to 10
        self.results_display.setFont(mono_font)
        
        log_layout.addWidget(self.results_display)
        log_box.setLayout(log_layout)
        
        layout.addWidget(log_box)




        self.setLayout(layout)
        self.file_path = ""
        self.results_df = pd.DataFrame() # Store results DataFrame
        self.analysis_thread = None

        self.log_message("Please select a file and set parameters.")


    def log_message(self, message):
        """Appends a message to the status/log display."""
        self.results_display.append(message)
        self.results_display.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()

    def open_file_dialog(self):
        """Opens a dialog to select the input CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select EEG File", "", "EEG Files (*.csv)")
        if file_path:
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
            self.log_message(f"Input file set: {self.file_path}")
        else:
             self.log_message("File selection cancelled.")

    def start_analysis(self):
        """Validates inputs and starts the background analysis thread."""
        if not self.file_path:
            QMessageBox.warning(self, "Input Error", "Please select an EEG data file first.")
            self.log_message("Error: No input file selected.")
            return

        if not os.path.exists(self.file_path):
             QMessageBox.critical(self, "File Error", f"The selected file does not exist:\n{self.file_path}")
             self.log_message(f"Error: File not found at {self.file_path}")
             return

        try:
            lower_bound = float(self.lower_bound_input.text().strip())
            upper_bound = float(self.upper_bound_input.text().strip())
            # Ensure 'epoch_length' from GUI is used as segment length
            segment_length = float(self.epoch_input.text().strip())
            sample_frequency = float(self.sample_frequency_input.text().strip())

            if lower_bound < 0 or upper_bound <= lower_bound:
                raise ValueError("Invalid frequency range (upper must be > lower, lower >= 0).")
            # Check segment length validity
            if segment_length <= 0:
                raise ValueError("Invalid segment length (must be > 0).")
            if sample_frequency <= 0:
                raise ValueError("Invalid sample frequency (must be > 0).")

        except ValueError as e:
            QMessageBox.critical(self, "Parameter Error", f"Invalid analysis parameters entered:\n{e}\nPlease enter valid numbers.")
            self.log_message(f"Error: Invalid parameters - {e}")
            return

        # Disable buttons, clear log (optional), reset progress
        self.calculate_button.setEnabled(False)
        self.calculate_button.setText("Calculating...")
        self.export_button.setEnabled(False)
        self.log_message("-" * 72)
        self.log_message(f"Starting analysis for {os.path.basename(self.file_path)}...")
        self.progress_bar.setValue(0)
        self.results_df = pd.DataFrame() # Clear previous results DataFrame

        # Start the background thread
        self.analysis_thread = EEGAnalyzerThread(
            self.file_path, lower_bound, upper_bound, segment_length, sample_frequency
        )
        # Connect signals
        self.analysis_thread.progress.connect(self.progress_bar.setValue)
        self.analysis_thread.status_update.connect(self.log_message)
        # Connect finished signal to the new handler
        self.analysis_thread.finished.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    # Modified handler for the 'finished' signal
    def on_analysis_complete(self, result_obj):
        """Handles the finished signal from the analysis thread."""
        self.progress_bar.setValue(100)

        # Re-enable calculate button immediately
        self.calculate_button.setEnabled(True)
        self.calculate_button.setText("Calculate Band Powers")

        if isinstance(result_obj, pd.DataFrame):
            self.results_df = result_obj # Store the DataFrame
            if not self.results_df.empty:
                # Display first few rows in log as confirmation (optional)
                self.log_message("\n------------------- Results Summary (First 5 Epochs) -------------------\n")
                # Format output for better readability in the log
                try:
                    summary_text = self.results_df.head().to_string(index=False, float_format="%.4f")
                except Exception: # Fallback if formatting fails
                    summary_text = str(self.results_df.head())
                self.log_message(summary_text)
                self.export_button.setEnabled(True) # Enable export
            else:
                 # Log message already emitted by thread if no results were generated
                 # Only show MessageBox if no error occurred during calculation
                 # (Error message box is shown if result_obj is an Exception)
                 self.export_button.setEnabled(False)
                 QMessageBox.warning(self, "Analysis Warning", "Calculation completed, but no epochs were generated.\nCheck input file length and segment settings.")
        elif isinstance(result_obj, Exception):
            # Error messages are already logged by the thread's status_update signal
            QMessageBox.critical(self, "Analysis Error", f"An error occurred during analysis:\n{result_obj}")
            self.results_df = pd.DataFrame() # Ensure empty DataFrame on error
            self.export_button.setEnabled(False)
        else:
            # Handle unexpected result type
            self.log_message(f"Analysis finished with unexpected result type: {type(result_obj)}")
            self.results_df = pd.DataFrame()
            self.export_button.setEnabled(False)


    def export_results(self):
        """Prompts user for save location and exports the results DataFrame."""
        if self.results_df.empty: # Check if DataFrame is empty
            QMessageBox.warning(self, "Export Error", "No results available to export!")
            self.log_message("Export attempt failed: No results data.")
            return

        try:
            base, _ = os.path.splitext(os.path.basename(self.file_path))
            default_filename = f"{base}_bandpowers.csv" # Updated suffix

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Epoch Band Power Results",
                default_filename,
                "CSV Files (*.csv)"
            )

            if save_path:
                self.log_message(f"Exporting results to: {save_path}")
                # Export the DataFrame directly using pandas
                self.results_df.to_csv(save_path, index=False, float_format='%.4f') # Use pandas export

                self.log_message("Export successful.")
                QMessageBox.information(self, "Export Successful", f"Epoch results saved to:\n{os.path.basename(save_path)}")
            else:
                self.log_message("Export cancelled by user.")

        except PermissionError:
             QMessageBox.critical(self, "Export Error", f"Permission denied. Could not save file to:\n{save_path}\nChoose a different location.")
             self.log_message(f"Error: Permission denied saving to {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An unexpected error occurred during export:\n{e}")
            self.log_message(f"Error during export: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setStyle('Fusion') # Optional styling

    window = EEGBandPowerGUI()
    window.show()
    sys.exit(app.exec())
    