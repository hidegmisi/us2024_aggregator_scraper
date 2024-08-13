#!/bin/bash

# Activate the conda environment (if needed)
source /Users/hidegmisi/miniforge3/bin/activate datasets

# Change to the directory containing your Python script
cd /Users/hidegmisi/Programming/Projects/us2024_polling/

# Run the Python script
python scraper.py

# Optional: Deactivate the conda environment
conda deactivate