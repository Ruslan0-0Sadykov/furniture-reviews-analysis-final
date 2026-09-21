import pandas as pd
from src.preprocessing import normalize_text, preprocess


def test_normalize_text_and_missing_rows():
    assert normalize_text("<b>Тест</b>  строки\n") == "Тест строки"
    raw=pd.DataFrame([{"Наименование":"М","Оценка":5,"Количество оценок":1,"Адрес":"А","Координаты объекта":"0,0","Количество отзывов":1,"Автор":"Я","Статус автора":"1","Оценка автора":5,"Дата":"3 марта 2024","Текст":" Хорошо ","Like":0,"Dislike":0,"source":"x","source_row":2},{"Наименование":"М","Оценка":5,"Количество оценок":1,"Адрес":"А","Координаты объекта":"0,0","Количество отзывов":1,"Автор":None,"Статус автора":None,"Оценка автора":None,"Дата":None,"Текст":None,"Like":None,"Dislike":None,"source":"x","source_row":3}])
    clean,audit=preprocess(raw,"2024-04-03")
    assert len(clean)==1 and audit["blank_or_nonreview_rows_removed"]==1

