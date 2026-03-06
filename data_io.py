import pandas as pd
import os




def safe_read_csv(path, columns=None, stop_on_missing=False):


    if not os.path.exists(path):


        if stop_on_missing:
            raise FileNotFoundError(path)


        if columns:
            return pd.DataFrame(columns=columns)


        return pd.DataFrame()


    df = pd.read_csv(path)


    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = ""


        df = df[columns]


    return df
