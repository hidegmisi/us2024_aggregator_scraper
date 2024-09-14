import pandas as pd

# Load the raw CSV data
raw_data = pd.read_csv('scrape_history.csv')

# Convert 'date' column to datetime
raw_data['date'] = pd.to_datetime(raw_data['date'])

# Group by date, aggregator, and candidate to calculate daily average for each aggregator
daily_averages_by_aggregator = raw_data.groupby(['date', 'aggregator', 'candidate'])['value'].mean().round(3).reset_index()

# Calculate the total average for each candidate across all aggregators
daily_overall_averages = raw_data.groupby(['date', 'candidate'])['value'].mean().round(3).reset_index()

# Add a column to mark these as 'Total Avg'
daily_overall_averages['aggregator'] = 'Average'

# Combine both the aggregator averages and total averages into one dataframe
combined_data = pd.concat([daily_averages_by_aggregator, daily_overall_averages], ignore_index=True)

# Sort the combined data by date and aggregator
sort_categories = pd.CategoricalDtype(categories=['538', 'NS', 'NYT', 'RCP', 'Economist', 'Average'], ordered=True)
combined_data['aggregator'] = combined_data['aggregator'].astype(sort_categories)
combined_data.sort_values(['date', 'aggregator'], inplace=True)

# Save the combined result to a CSV
combined_data.to_csv('daily_aggregates.csv', index=False)