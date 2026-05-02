import os
import json
import pandas as pd


def load_data(folder_path):
    data = []

    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            with open(os.path.join(folder_path, file), "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data.append(json.loads(line))
                    except:
                        continue

    return pd.DataFrame(data)