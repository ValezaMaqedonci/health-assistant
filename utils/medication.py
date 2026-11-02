import pandas as pd
import os

def load_medications(file):

    if not os.path.exists(file):
        pd.DataFrame(
            columns=[
                "medicine",
                "dosage",
                "time",
                "taken"
            ]
        ).to_csv(file, index=False)

    return pd.read_csv(file)