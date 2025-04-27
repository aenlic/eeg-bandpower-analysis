import numpy as np
import pandas as pd
from scipy import signal
# Removed time import

# Define standard EEG frequency bands
DELTA_BAND = (1, 4)
THETA_BAND = (4, 8)
ALPHA_BAND = (8, 13)
BETA_BAND = (13, 30)
# Gamma often defined as 30-100 Hz, but upper bound is user-defined

# Store bands without descriptive keys for easier DataFrame column naming
BANDS_RANGES = {
    "Delta": DELTA_BAND,
    "Theta": THETA_BAND,
    "Alpha": ALPHA_BAND,
    "Beta": BETA_BAND,
}

def calculate_band_powers(
    file_path,
    lower_bound=1.0, # Default lower bound changed to 1Hz
    upper_bound=30.0,
    epoch_length=2.0, # Default epoch length changed to 2s
    sample_frequency=128.0,
    analysis_method="Welch", # Parameter kept for GUI compatibility, but ignored
    progress_callback=None,
    channel_index=0 # Index of the column to analyze in the CSV
):

  
    if progress_callback:
        progress_callback(0)

    results_list = [] # To store results for each epoch

    # --- 1. Load Data ---
    try:
        data = pd.read_csv(file_path, usecols=[channel_index], header=0, dtype=np.float64)
        eeg_data = data.iloc[:, 0].values # Get the specified column as numpy array
        if eeg_data.size == 0:
            raise ValueError(f"Selected channel ({channel_index}) contains no data.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {file_path}")
    except ValueError as e: # Catch issues like non-numeric data or wrong column index
         raise ValueError(f"Error reading CSV data (column {channel_index}): {e}. Ensure column exists and contains numeric data.")
    except Exception as e:
        raise Exception(f"Failed to load or process file {file_path}: {e}")

    if progress_callback:
        progress_callback(10)

    # --- 2. Parameters ---
    sf = float(sample_frequency)
    nperseg = int(epoch_length * sf) # Samples per segment
    noverlap = nperseg // 2 # 50% overlap is common

    # Ensure nperseg is valid given the data length
    if nperseg > len(eeg_data):
         print(f"Warning: Window length ({epoch_length}s) is longer than data duration. "
               f"No full segments can be analyzed.")
         return pd.DataFrame() # Return empty DataFrame
    elif nperseg <= 0:
        raise ValueError(f"Invalid epoch length ({epoch_length}s) resulting in non-positive samples per segment.")

    # --- Optional Preprocessing (Bandpass filter) ---
    # Apply before segmenting/spectrogram
    try:
        lowcut = 0.5 # Keep filtering slightly below lower_bound for better rolloff
        highcut = min(upper_bound + 5, sf / 2 - 1)
        if highcut <= lowcut: highcut = sf / 2 - 1
        if highcut > lowcut:
            sos = signal.butter(5, [lowcut, highcut], btype='bandpass', output='sos', fs=sf)
            eeg_data_filtered = signal.sosfiltfilt(sos, eeg_data)
            if progress_callback: progress_callback(20)
        else:
             print("Warning: Skipping bandpass filter due to invalid frequency range.")
             eeg_data_filtered = eeg_data
             if progress_callback: progress_callback(20)
    except Exception as e:
        print(f"Warning: Could not apply bandpass filter: {e}. Proceeding with unfiltered data.")
        eeg_data_filtered = eeg_data
        if progress_callback: progress_callback(20)

    # --- 3. Calculate Spectrogram (Provides PSD per segment) ---
    try:
        # Use spectrogram to get power density per segment
        # mode='psd' returns power spectral density
        freqs, times, Sxx = signal.spectrogram(
            eeg_data_filtered,
            fs=sf,
            window='hann', # Use Hann window as in Welch
            nperseg=nperseg,
            noverlap=noverlap,
            scaling='density', # Get power density (e.g., uV^2/Hz)
            mode='psd'
        )
        # Sxx shape: (n_freqs, n_times)
    except ValueError as e:
         raise ValueError(f"Error during Spectrogram calculation: {e}. Check data length and parameters.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during Spectrogram calculation: {e}")

    if Sxx is None or Sxx.size == 0:
        print("Warning: Spectrogram calculation produced no results.")
        return pd.DataFrame() # Return empty DataFrame

    if progress_callback: progress_callback(70)

    # --- 4. Calculate Band Powers per Epoch/Segment ---
    # Frequency resolution
    if len(freqs) > 1:
        freq_res = freqs[1] - freqs[0]
    else: freq_res = 1.0 # Should not happen with spectrogram usually

    # Calculate total power mask once
    total_power_indices = np.logical_and(freqs >= lower_bound, freqs < upper_bound)

    # Iterate through each time segment in the spectrogram
    num_epochs = Sxx.shape[1]
    for i in range(num_epochs):
        epoch_results = {}
        psd_epoch = Sxx[:, i] # PSD for the i-th time segment

        # Calculate power for defined bands within this epoch
        for band_name, (low_freq, high_freq) in BANDS_RANGES.items():
            band_indices = np.logical_and(freqs >= low_freq, freqs < high_freq)
            band_indices = np.logical_and(band_indices, freqs >= lower_bound) # Apply global bounds
            band_indices = np.logical_and(band_indices, freqs < upper_bound)
            band_power = np.sum(psd_epoch[band_indices]) * freq_res
            epoch_results[band_name] = band_power

        # Calculate total power for this epoch
        total_power = np.sum(psd_epoch[total_power_indices]) * freq_res
        epoch_results['Total Power'] = total_power

        # Add time - Round the center time before converting to integer
        epoch_results['Time'] = int(np.round(times[i]))

        results_list.append(epoch_results)

        if progress_callback:
            # Update progress more granularly during epoch processing
            progress = 70 + int(30 * (i + 1) / num_epochs)
            progress_callback(progress)

    # --- 5. Create DataFrame ---
    if not results_list:
        print("Warning: No epochs were processed.")
        return pd.DataFrame()

    # Define column order explicitly
    column_order = ['Time', 'Delta', 'Theta', 'Alpha', 'Beta', 'Total Power']
    results_df = pd.DataFrame(results_list)

    # Reorder columns if necessary (handles cases where a band might be empty)
    results_df = results_df[[col for col in column_order if col in results_df.columns]]

    # *** ADDED/MODIFIED LINE: Explicitly cast time column to integer ***
    if 'Time' in results_df.columns:
       # Use Int64 (capital I) to handle potential NaNs if they ever occur,
       # although they shouldn't with this logic. Regular int works too if no NaNs.
       try:
           results_df['Time'] = results_df['Time'].astype('Int64')
       except TypeError: # Fallback if casting fails for some reason
           print("Warning: Could not cast time column to integer.")
           results_df['Time'] = results_df['Time'].astype(int)


    if progress_callback:
        progress_callback(100)

    return results_df

