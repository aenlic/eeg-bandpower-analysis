# eeg-bandpower-analysis


Analyzes multi-channel EEG data from a CSV file. It calculates band powers for EEG channels per epoch and writes results in CSV.

## Features

* Loads multi-channel EEG from CSV. For now only processes first column
* Applies high-pass filtering at specified bounding frequency.
* Handles non-numeric data and checks for sufficient data length.
* Key parameters (sample rate, filtering...) are configurable.

## Requirements

* Python 3.x
* Libraries: `pandas`, `numpy`, `scipy`, `PyQt6`

