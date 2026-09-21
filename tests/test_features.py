import pandas as pd
from src.features import extract_features, extract_price


def test_text_features():
    df=pd.DataFrame({"text_original":["Диван привезли быстро! Супер 🔥"],"text":["Диван привезли быстро! Супер 🔥"],"rating":[5]})
    out=extract_features(df)
    assert out.loc[0,"furniture_group"]=="soft"
    assert out.loc[0,"delivery_speed"]=="fast"
    assert out.loc[0,"word_count"]>=4
    assert extract_price("заплатил 25 тысяч рублей")==25000

