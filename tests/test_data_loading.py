import pandas as pd
from src.data_loading import load_raw_files, EXPECTED_COLUMNS


def test_load_raw_files(tmp_path):
    frame=pd.DataFrame({c:[None] for c in EXPECTED_COLUMNS}); frame["Наименование"]="Магазин"; frame["Текст"]="Отзыв"; frame.to_excel(tmp_path/"sample.xlsx",index=False)
    loaded=load_raw_files(tmp_path)
    assert len(loaded)==1 and loaded.loc[0,"source"]=="sample"

