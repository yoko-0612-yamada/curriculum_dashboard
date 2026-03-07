import pandas as pd
import os




def safe_read_csv(path,
    required_cols=None,
    columns=None,
    stop_on_missing=False,
    show_message=True
):
    """
    CSVを安全に読み込む


    - required_cols: 必須列。無ければ空列を補う
    - columns: required_cols の別名としても使える
    - stop_on_missing: ファイルが無いときにエラーにする
    """


    # columns が渡されて、required_cols が未指定なら columns を使う
    if required_cols is None and columns is not None:
        required_cols = columns


    if not os.path.exists(path):
        if stop_on_missing:
            raise FileNotFoundError(path)


        if required_cols:
            return pd.DataFrame(columns=required_cols)


        return pd.DataFrame()


    df = pd.read_csv(path)


    if required_cols:
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""


        df = df[required_cols]


    return df
