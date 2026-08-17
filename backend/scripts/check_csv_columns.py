import os
import pandas as pd

states_dir = r"c:\Users\chnag\OneDrive\Attachments\Desktop\ingres1\states"
for f in os.listdir(states_dir):
    if f.endswith('.csv'):
        df = pd.read_csv(os.path.join(states_dir, f), nrows=5)
        # Search for columns containing allocation, discharge, or availability
        matching_cols = [c for c in df.columns if any(x in c.lower() for x in ['alloc', 'disch', 'avail', 'net'])]
        if matching_cols:
            print(f"{f}: {matching_cols}")
            break
else:
    print("No matching columns found in any CSV headers.")
