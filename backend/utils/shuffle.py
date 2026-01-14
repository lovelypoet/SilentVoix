import pandas as pd
import os

RAW_DATA_PATH = os.path.join(os.path.dirname(__file__), '../data/raw_data.csv')
SHUFFLED_DATA_PATH = os.path.join(os.path.dirname(__file__), '../data/shuffled_data.csv')

if __name__ == "__main__":
    # Read the raw data
    df = pd.read_csv(RAW_DATA_PATH)
    # Shuffle the rows
    df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)
    # Write to shuffled_data.csv
    df_shuffled.to_csv(SHUFFLED_DATA_PATH, index=False)
    print(f"Shuffled data written to {SHUFFLED_DATA_PATH} with {len(df_shuffled)} rows.") 