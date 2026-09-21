from __future__ import annotations

import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family":"DejaVu Sans","axes.titlesize":13,"axes.labelsize":10,"figure.dpi":120})
COLORS={"blue":"#2563EB","teal":"#0F766E","orange":"#EA580C","red":"#B91C1C","gray":"#64748B","green":"#15803D"}


def _save(fig,path):
    fig.tight_layout(); fig.savefig(path,dpi=220,bbox_inches="tight",facecolor="white"); plt.close(fig)


def create_figures(df, results, h5data, output_dir):
    paths={}
    rating=df.rating.dropna().value_counts().sort_index(); fig,ax=plt.subplots(figsize=(7,4)); ax.bar(rating.index.astype(str),rating.values,color=COLORS["blue"]); ax.set(title="Распределение оценок покупателей",xlabel="Оценка",ylabel="Количество отзывов"); _save(fig,output_dir/"01_rating_distribution.png"); paths["rating"]=str(output_dir/"01_rating_distribution.png")
    sent=df.sentiment.value_counts().reindex(["positive","neutral","negative"]).fillna(0); fig,ax=plt.subplots(figsize=(7,4)); ax.bar(["Положительные","Нейтральные","Негативные"],sent.values,color=[COLORS["green"],COLORS["gray"],COLORS["red"]]); ax.set(title="Тональность по рейтингу",ylabel="Количество отзывов"); _save(fig,output_dir/"02_sentiment.png"); paths["sentiment"]=str(output_dir/"02_sentiment.png")
    complaints=pd.Series({"Сервис":int(df.service_issue.sum()),"Качество товара":int(df.product_quality_issue.sum()),"Доставка":int(((df.delivery_speed=="slow")&(df.rating<=3)).sum()),"Возврат или претензия":int(df.return_or_claim.sum())}).sort_values(); fig,ax=plt.subplots(figsize=(7,4)); ax.barh(complaints.index,complaints.values,color=COLORS["orange"]); ax.set(title="Основные категории жалоб",xlabel="Количество отзывов"); _save(fig,output_dir/"03_complaints.png"); paths["complaints"]=str(output_dir/"03_complaints.png")
    h1=results[0]["metrics"]; fig,ax=plt.subplots(figsize=(7,4)); vals=[h1["service_share"] or 0,h1["quality_share"] or 0]; ax.bar(["Сервис","Качество мебели"],vals,color=[COLORS["blue"],COLORS["orange"]]); ax.set(title="H1 Причины негативных отзывов",ylabel="Доля негативных отзывов",ylim=(0,max(vals+[.1])*1.25)); ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1)); _save(fig,output_dir/"04_h1_service_vs_quality.png"); paths["h1"]=str(output_dir/"04_h1_service_vs_quality.png")
    h2=results[1]["metrics"]["rates"]; labels=[x for x in ["fast","normal","slow"] if x in h2]; label_ru={"fast":"Быстро","normal":"В срок","slow":"Медленно"}; vals=[h2[x]["share"] for x in labels]; fig,ax=plt.subplots(figsize=(7,4)); ax.bar([label_ru[x] for x in labels],vals,color=[COLORS["green"],COLORS["blue"],COLORS["red"]][:len(labels)]); ax.set(title="H2 Скорость доставки и положительная оценка",ylabel="Доля положительных",ylim=(0,1)); ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1)); _save(fig,output_dir/"05_h2_delivery_speed.png"); paths["h2"]=str(output_dir/"05_h2_delivery_speed.png")
    rows=results[2]["metrics"]["reason_counts"][:8]; reason_ru={"mismatch_description":"Несоответствие описанию","quality_defect":"Дефект или качество","damage":"Повреждение","wrong_item":"Неверный товар","incomplete_set":"Некомплект","dimensions":"Размеры","color":"Цвет","delivery":"Доставка","assembly":"Сборка","other":"Другое"}; fig,ax=plt.subplots(figsize=(8,4.5)); ax.barh([reason_ru.get(x["reason"],x["reason"]) for x in rows][::-1],[x["count"] for x in rows][::-1],color=COLORS["orange"]); ax.set(title="H3 Причины возвратов и претензий",xlabel="Количество упоминаний"); _save(fig,output_dir/"06_h3_return_reasons.png"); paths["h3"]=str(output_dir/"06_h3_return_reasons.png")
    groups=[df.loc[df.furniture_group==g,"word_count"].clip(upper=df.word_count.quantile(.99)) for g in ["soft","cabinet"]]; fig,ax=plt.subplots(figsize=(7,4)); ax.boxplot(groups,tick_labels=["Мягкая","Корпусная"],showfliers=False); ax.set(title="H4 Длина отзывов по типу мебели",ylabel="Количество слов"); _save(fig,output_dir/"07_h4_length.png"); paths["h4_length"]=str(output_dir/"07_h4_length.png")
    groups=[df.loc[df.furniture_group==g,"emotion_intensity"] for g in ["soft","cabinet"]]; fig,ax=plt.subplots(figsize=(7,4)); ax.boxplot(groups,tick_labels=["Мягкая","Корпусная"],showfliers=False); ax.set(title="H4 Эмоциональность отзывов",ylabel="Индекс эмоциональности от 0 до 1"); _save(fig,output_dir/"08_h4_emotion.png"); paths["h4_emotion"]=str(output_dir/"08_h4_emotion.png")
    fig,ax=plt.subplots(figsize=(7,4));
    if len(h5data): ax.scatter(h5data.price_rub,h5data.detail_score,alpha=.45,s=18,color=COLORS["blue"]); ax.set_xscale("log")
    ax.set(title="H5 Цена и подробность отзыва",xlabel="Упомянутая цена, руб. логарифмическая шкала",ylabel="Индекс подробности"); _save(fig,output_dir/"09_h5_price_detail.png"); paths["h5"]=str(output_dir/"09_h5_price_detail.png")
    summary=pd.DataFrame([{"Гипотеза":r["hypothesis"],"Вердикт":r["verdict"],"n":r["n"]} for r in results]); fig,ax=plt.subplots(figsize=(10,3.4)); ax.axis("off"); table=ax.table(cellText=summary.values,colLabels=summary.columns,loc="center",cellLoc="left",colLoc="center",colWidths=[.15,.65,.15]); table.auto_set_font_size(False); table.set_fontsize(10); table.scale(1,1.7); [cell.set_facecolor("#DBEAFE") for cell in table.get_celld().values() if cell.get_text().get_text() in summary.columns]; ax.set_title("Итоги проверки гипотез",pad=16); _save(fig,output_dir/"10_hypotheses_summary.png"); paths["summary"]=str(output_dir/"10_hypotheses_summary.png")
    return paths
