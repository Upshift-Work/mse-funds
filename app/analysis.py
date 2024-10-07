import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# Load the data
df = pd.read_csv('combined_mutual_fund_data.csv', sep='\t')

# Convert date columns to datetime
df['Date of calculation'] = pd.to_datetime(df['Date of calculation'])
df['Valuation date'] = pd.to_datetime(df['Valuation date'])

# Sort the dataframe by fund name and valuation date
df = df.sort_values(['Name of the open-end investment fund', 'Valuation date'])

# Calculate daily returns
df['Daily Return'] = df.groupby('Name of the open-end investment fund')['Last daily sale price per unit'].pct_change()

# Calculate cumulative returns correctly
df['Cumulative Return'] = df.groupby('Name of the open-end investment fund').apply(lambda x: (1 + x['Daily Return']).cumprod() - 1).reset_index(level=0, drop=True)

# Function to calculate average annual return
def avg_annual_return(returns):
    total_return = returns.iloc[-1]
    years = len(returns) / 252  # Assuming 252 trading days per year
    return (1 + total_return) ** (1 / years) - 1

# Calculate metrics for each fund
current_date = df['Valuation date'].max()
metrics = []
for fund in df['Name of the open-end investment fund'].unique():
    fund_data = df[df['Name of the open-end investment fund'] == fund]

    # YTD return
    ytd_start = datetime(current_date.year, 1, 1)
    ytd_data = fund_data[fund_data['Valuation date'] >= ytd_start]
    if not ytd_data.empty:
        ytd_start_price = ytd_data['Last daily sale price per unit'].iloc[0]
        ytd_end_price = ytd_data['Last daily sale price per unit'].iloc[-1]
        ytd_return = (ytd_end_price / ytd_start_price) - 1
    else:
        ytd_return = np.nan

    # 5-year return
    five_year_start = current_date - timedelta(days=5*365)
    five_year_data = fund_data[fund_data['Valuation date'] >= five_year_start]
    five_year_return = avg_annual_return(five_year_data['Cumulative Return']) if not five_year_data.empty else np.nan

    # 10-year return
    ten_year_start = current_date - timedelta(days=10*365)
    ten_year_data = fund_data[fund_data['Valuation date'] >= ten_year_start]
    ten_year_return = avg_annual_return(ten_year_data['Cumulative Return']) if not ten_year_data.empty else np.nan

    metrics.append({
        'fund': fund,
        'ytd_return': ytd_return,
        'five_year_return': five_year_return,
        'ten_year_return': ten_year_return,
        'volatility': fund_data['Daily Return'].std() * np.sqrt(252),
        'avg_spread': (fund_data['Daily buying price per unit'] - fund_data['Last daily sale price per unit']).mean()
    })

metrics_df = pd.DataFrame(metrics)

# Get top and bottom 5 funds by 5-year, 10-year, and YTD returns
top_5_year = metrics_df.nlargest(5, 'five_year_return')[['fund', 'five_year_return']]
top_10_year = metrics_df.nlargest(5, 'ten_year_return')[['fund', 'ten_year_return']]
top_ytd = metrics_df.nlargest(5, 'ytd_return')[['fund', 'ytd_return']]
bottom_5_year = metrics_df.nsmallest(5, 'five_year_return')[['fund', 'five_year_return']]
bottom_10_year = metrics_df.nsmallest(5, 'ten_year_return')[['fund', 'ten_year_return']]
bottom_ytd = metrics_df.nsmallest(5, 'ytd_return')[['fund', 'ytd_return']]

# Prepare data for JavaScript output
js_data = {
    'fundList': df['Name of the open-end investment fund'].unique().tolist(),
    'fundMetrics': metrics_df.to_dict('records'),
    'fundData': {},
    'top5Year': top_5_year.to_dict('records'),
    'top10Year': top_10_year.to_dict('records'),
    'topYTD': top_ytd.to_dict('records'),
    'bottom5Year': bottom_5_year.to_dict('records'),
    'bottom10Year': bottom_10_year.to_dict('records'),
    'bottomYTD': bottom_ytd.to_dict('records')
}

for fund in js_data['fundList']:
    fund_data = df[df['Name of the open-end investment fund'] == fund]
    # Resample data to monthly frequency
    monthly_data = fund_data.resample('M', on='Valuation date').last()
    js_data['fundData'][fund] = {
        'dates': monthly_data.index.strftime('%Y-%m-%d').tolist(),
        'prices': monthly_data['Last daily sale price per unit'].tolist(),
        'returns': monthly_data['Cumulative Return'].tolist()
    }

# Write JavaScript file
with open('output/fund_data.js', 'w') as f:
    f.write('const fundData = ')
    json.dump(js_data, f)
    f.write(';')

print("Analysis complete. Data exported to 'output/fund_data.js'.")