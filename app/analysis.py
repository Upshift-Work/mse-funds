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
def avg_annual_return(start_price, end_price, years):
    total_return = (end_price / start_price) - 1
    return (1 + total_return) ** (1 / years) - 1

# Calculate metrics for each fund
current_date = df['Valuation date'].max()
metrics = []
for fund in df['Name of the open-end investment fund'].unique():
    fund_data = df[df['Name of the open-end investment fund'] == fund]

    current_price = fund_data['Last daily sale price per unit'].iloc[-1]

    # YTD return
    ytd_start = datetime(current_date.year, 1, 1)
    ytd_data = fund_data[fund_data['Valuation date'] >= ytd_start]
    if not ytd_data.empty:
        ytd_start_price = ytd_data['Last daily sale price per unit'].iloc[0]
        ytd_return = (current_price / ytd_start_price) - 1
    else:
        ytd_return = np.nan

    # 5-year return
    five_year_start = current_date - timedelta(days=5*365)
    five_year_data = fund_data[fund_data['Valuation date'] >= five_year_start]
    if not five_year_data.empty:
        five_year_start_price = five_year_data['Last daily sale price per unit'].iloc[0]
        five_year_return = avg_annual_return(five_year_start_price, current_price, 5)
    else:
        five_year_return = np.nan

    # 10-year return
    ten_year_start = current_date - timedelta(days=10*365)
    ten_year_data = fund_data[fund_data['Valuation date'] >= ten_year_start]
    if not ten_year_data.empty:
        ten_year_start_price = ten_year_data['Last daily sale price per unit'].iloc[0]
        ten_year_return = avg_annual_return(ten_year_start_price, current_price, 10)
    else:
        ten_year_return = np.nan

    # Calculate Sharpe Ratio (assuming risk-free rate of 2%)
    risk_free_rate = 0.02
    excess_returns = fund_data['Daily Return'] - risk_free_rate / 252  # 252 trading days in a year
    sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std()

    # Calculate maximum drawdown
    cumulative_returns = (1 + fund_data['Daily Return']).cumprod()
    peak = cumulative_returns.expanding(min_periods=1).max()
    drawdown = (cumulative_returns / peak) - 1
    max_drawdown = drawdown.min()

    metrics.append({
        'fund': fund,
        'current_price': current_price,
        'ytd_return': ytd_return,
        'five_year_return': five_year_return,
        'ten_year_return': ten_year_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown
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