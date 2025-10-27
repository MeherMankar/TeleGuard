"""Update AccountAgeEstimator with accurate anchor ranges"""
import csv

# Read the accurate ranges we created
ranges = []
with open('teleguard/data/id_ranges.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        start = int(row['start_id'])
        end = int(row['end_id'])
        date_str = row['utc_date']
        ranges.append(f"        ({start}, {end}, datetime.datetime.fromisoformat('{date_str}')),")

# Generate the Python code
code = '\n'.join(ranges)

print("Copy this into account_age_estimator.py ID_RANGES:")
print()
print(code)
