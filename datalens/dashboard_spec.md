# Спецификация дашборда Анализ отзывов покупателей мебели

Внешний источник: `datalens_dataset_public.csv`. Датасет агрегирован только по источнику, рейтингу и тональности; остальные признаки представлены счётчиками. В нём нет текстов, авторов, профилей, дат, адресов, компаний и идентификаторов отзывов.

## KPI

| Название | Тип | Dimension | Measure | Фильтры | Вычисляемое поле | Сортировка |
|---|---|---|---|---|---|---|
| Количество отзывов | Индикатор | — | SUM(review_count) | Общие селекторы | — | — |
| Средний рейтинг | Индикатор | — | SUM(rating * review_count) / SUM(review_count) | rating != 'unknown' | Weighted rating | — |
| Доля положительных | Индикатор | — | SUM(IF sentiment='positive' THEN review_count ELSE 0 END)/SUM(review_count) | Общие селекторы | Positive share | — |
| Доля негативных | Индикатор | — | SUM(IF sentiment='negative' THEN review_count ELSE 0 END)/SUM(review_count) | Общие селекторы | Negative share | — |

## Графики

| Название | Тип | Dimensions | Measures | Filters | Calculated fields | Сортировка |
|---|---|---|---|---|---|---|
| Распределение рейтингов | Столбчатая | rating | SUM(review_count) | rating != 'unknown' | — | rating ASC |
| Категории мебели | Столбчатая | метрика | SUM(furniture_soft_count), SUM(furniture_cabinet_count), SUM(furniture_other_count) | — | — | по значению |
| Основные жалобы | Столбчатая | sentiment | SUM(service_issue_count), SUM(product_quality_issue_count) | sentiment='negative' | — | по значению |
| Скорость доставки | Столбчатая | метрика | SUM(delivery_fast_count), SUM(delivery_normal_count), SUM(delivery_slow_count) | — | — | fast, normal, slow |
| Мягкая и корпусная мебель | Столбчатая | метрика | SUM(furniture_soft_count), SUM(furniture_cabinet_count) | — | — | по значению |

## Селекторы

- `rating`.
- `source`.
- `sentiment`.
