import pandas as pd
import os

import tempfile



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


def write_csv_atomic(df, path):
    """
    CSVを安全に保存する（途中で壊れないようにする）
    """
    dir_name = os.path.dirname(path)


    if dir_name == "":
        dir_name = "."


    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")


    try:
        os.close(fd)
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

