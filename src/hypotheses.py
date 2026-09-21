from __future__ import annotations

import json
import math
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from .statistics import bootstrap_ci, bootstrap_corr_ci, wilson_interval, cliffs_delta_from_u, bh_adjust


def _or_ci(a,b,c,d):
    a,b,c,d=[x+.5 for x in (a,b,c,d)]
    estimate=a*d/(b*c); se=math.sqrt(1/a+1/b+1/c+1/d)
    return float(estimate), [float(math.exp(math.log(estimate)-1.96*se)), float(math.exp(math.log(estimate)+1.96*se))]


def h1(df):
    neg=df[df.rating<=2].copy(); n=len(neg)
    s=int(neg.service_issue.sum()); q=int(neg.product_quality_issue.sum()); both=int((neg.service_issue&neg.product_quality_issue).sum())
    service_only=int((neg.service_issue&~neg.product_quality_issue).sum()); quality_only=int((~neg.service_issue&neg.product_quality_issue).sum())
    test=stats.binomtest(service_only, service_only+quality_only, .5, alternative="greater") if service_only+quality_only else None
    diff=(s-q)/n if n else None
    boot=[]
    if n:
        arr=(neg.service_issue.astype(int)-neg.product_quality_issue.astype(int)).to_numpy(); boot=bootstrap_ci(arr,np.mean)
    verdict="невозможно достоверно проверить по имеющимся данным"
    if test:
        verdict="подтверждена" if test.pvalue<.05 and diff>0 else "не подтверждена"
    return {"hypothesis":"H1","n":n,"metrics":{"negative_definition":"rating <= 2","service_count":s,"service_share":s/n if n else None,"service_ci":wilson_interval(s,n),"quality_count":q,"quality_share":q/n if n else None,"quality_ci":wilson_interval(q,n),"both_count":both,"service_only":service_only,"quality_only":quality_only,"share_difference":diff,"difference_ci":boot},"test":"точный биномиальный тест для несогласованных пар (эквивалент точного McNemar)","p_value":float(test.pvalue) if test else None,"effect_size":diff,"verdict":verdict,"limitations":"Тематики извлечены правилами из текста; один отзыв может содержать обе причины."}


def h2(df):
    sub=df[df.delivery_speed.isin(["fast","normal","slow"]) & df.rating.notna()].copy(); sub["positive"]=(sub.rating>=4).astype(int)
    order=[x for x in ["fast","normal","slow"] if x in set(sub.delivery_speed)]
    table=pd.crosstab(sub.delivery_speed,sub.positive).reindex(order,fill_value=0)
    if 0 not in table: table[0]=0
    if 1 not in table: table[1]=0
    chi2,p,dof,expected=stats.chi2_contingency(table[[0,1]]) if len(table)>=2 and table.values.sum()>0 else (None,None,None,None)
    v=math.sqrt(chi2/(table.values.sum()*max(1,min(table.shape[0]-1,table.shape[1]-1)))) if chi2 is not None else None
    rates={k:{"n":int((sub.delivery_speed==k).sum()),"positive":int(sub.loc[sub.delivery_speed==k,"positive"].sum())} for k in order}
    for value in rates.values(): value["share"]=value["positive"]/value["n"] if value["n"] else None; value["ci"]=wilson_interval(value["positive"],value["n"])
    odds=odds_ci=None
    if "fast" in rates and "slow" in rates:
        a=rates["fast"]["positive"]; b=rates["fast"]["n"]-a; c=rates["slow"]["positive"]; d=rates["slow"]["n"]-c; odds,odds_ci=_or_ci(a,b,c,d)
    regression={}
    if len(sub)>=40 and sub.positive.nunique()==2:
        model_data=sub[["delivery_speed","furniture_group"]].copy()
        model_data["furniture_group"]=model_data.furniture_group.replace("other","unknown")
        X=pd.get_dummies(model_data,drop_first=True,dtype=float); X=sm.add_constant(X)
        try:
            fit=sm.Logit(sub.positive.astype(float),X).fit(disp=False,maxiter=100)
            regression={"n":len(sub),"coefficients":{k:float(v) for k,v in fit.params.items()},"p_values":{k:float(v) for k,v in fit.pvalues.items()},"odds_ratios":{k:float(math.exp(v)) for k,v in fit.params.items()}}
        except Exception as exc: regression={"error":type(exc).__name__}
    verdict="невозможно достоверно проверить по имеющимся данным"
    if p is not None: verdict="подтверждена" if p<.05 and rates.get("fast",{}).get("share",0)>rates.get("slow",{}).get("share",1) else "не подтверждена"
    return {"hypothesis":"H2","n":int(len(sub)),"metrics":{"positive_definition":"rating >= 4","rates":rates,"contingency":table.rename(columns={0:"not_positive",1:"positive"}).reset_index().to_dict("records"),"odds_ratio_fast_vs_slow":odds,"odds_ratio_ci":odds_ci,"logistic_regression":regression},"test":"chi-square; odds ratio fast vs slow; логистическая регрессия при достаточной выборке","p_value":float(p) if p is not None else None,"effect_size":v,"verdict":verdict,"limitations":"Скорость определена только по явным формулировкам текста; связь наблюдательная и не доказывает причинность."}


def h3(df):
    sub=df[df.return_or_claim].copy(); reasons=[x for cell in sub.return_reason for x in str(cell).split("|") if x]
    counts=pd.Series(reasons).value_counts(); n=len(sub); rows=[]
    for reason,count in counts.items(): rows.append({"reason":reason,"count":int(count),"share":float(count/n) if n else None,"ci":wilson_interval(int(count),n)})
    p=None; effect=None
    if len(counts)>=2:
        top,second=counts.index[:2]
        # paired comparison uses discordant records
        a=sub.return_reason.str.contains(fr"(?:^|\|){top}(?:\||$)",regex=True); b=sub.return_reason.str.contains(fr"(?:^|\|){second}(?:\||$)",regex=True)
        discord_top=int((a&~b).sum()); discord_second=int((~a&b).sum())
        if discord_top+discord_second: p=float(stats.binomtest(discord_top,discord_top+discord_second,.5,alternative="greater").pvalue)
        effect=float((counts.iloc[0]-counts.iloc[1])/n) if n else None
    top_name=counts.index[0] if len(counts) else None
    verdict="невозможно достоверно проверить по имеющимся данным"
    if top_name: verdict="подтверждена" if top_name=="mismatch_description" and p is not None and p<.05 else "не подтверждена"
    return {"hypothesis":"H3","n":n,"metrics":{"reason_counts":rows,"top_reason":top_name,"top_minus_second_share":effect},"test":"точный парный биномиальный тест между двумя лидирующими multi-label причинами","p_value":p,"effect_size":effect,"verdict":verdict,"limitations":"Возвраты и причины извлечены из текста; возможны пропуски и несколько причин в одном отзыве."}


def _group_stats(values):
    values=np.asarray(values,float); return {"n":int(len(values)),"mean":float(np.mean(values)),"median":float(np.median(values)),"iqr":float(np.quantile(values,.75)-np.quantile(values,.25)),"mean_ci":bootstrap_ci(values,np.mean),"median_ci":bootstrap_ci(values,np.median)}


def h4(df):
    sub=df[df.furniture_group.isin(["soft","cabinet"]) & (df.word_count>0)].copy(); soft=sub[sub.furniture_group=="soft"]; cab=sub[sub.furniture_group=="cabinet"]
    results={}; pvals=[]
    for metric in ["word_count","emotion_intensity"]:
        a=soft[metric].to_numpy(); b=cab[metric].to_numpy(); test=stats.mannwhitneyu(a,b,alternative="greater") if len(a) and len(b) else None
        results[metric]={"soft":_group_stats(a) if len(a) else {},"cabinet":_group_stats(b) if len(b) else {},"u":float(test.statistic) if test else None,"p_value":float(test.pvalue) if test else None,"cliffs_delta":cliffs_delta_from_u(test.statistic,len(a),len(b)) if test else None}
        pvals.append(float(test.pvalue) if test else 1.0)
    confirmed=[results[m]["p_value"] is not None and results[m]["p_value"]<.05 and results[m]["cliffs_delta"]>0 for m in results]
    verdict="подтверждена" if all(confirmed) else "частично подтверждена" if any(confirmed) else "не подтверждена"
    return {"hypothesis":"H4","n":int(len(sub)),"metrics":results,"test":"Mann-Whitney U отдельно для длины и эмоциональности","p_value":max(pvals),"component_p_values":pvals,"effect_size":min(results[m]["cliffs_delta"] for m in results if results[m]["cliffs_delta"] is not None),"verdict":verdict,"limitations":"Тип мебели определяется по словам в отзыве; отзывы без однозначного типа исключены."}


def h5(df):
    sub=df[df.price_rub.notna() & (df.price_rub>0) & (df.word_count>0)].copy()
    components=[]
    for col in ["word_count","sentence_count","unique_words","aspects_count"]:
        values=np.log1p(sub[col].astype(float)); sd=values.std(ddof=0); sub[f"z_{col}"]=(values-values.mean())/sd if sd else 0; components.append(f"z_{col}")
    sub["detail_score"]=sub[components].mean(axis=1) if len(sub) else np.nan
    rho=p=None; ci=[None,None]; regression={}
    if len(sub)>=5:
        test=stats.spearmanr(sub.price_rub,sub.detail_score); rho=float(test.statistic); p=float(test.pvalue); ci=bootstrap_corr_ci(sub.price_rub,sub.detail_score)
    if len(sub)>=30:
        X=pd.DataFrame({"log_price":np.log(sub.price_rub)}); X=pd.concat([X,pd.get_dummies(sub.furniture_group,prefix="group",drop_first=True,dtype=float)],axis=1); X=sm.add_constant(X)
        try:
            fit=sm.RLM(sub.detail_score,X,M=sm.robust.norms.HuberT()).fit(); regression={"n":len(sub),"coefficients":{k:float(v) for k,v in fit.params.items()},"p_values":{k:float(v) for k,v in fit.pvalues.items()}}
        except Exception as exc: regression={"error":type(exc).__name__}
    verdict="невозможно достоверно проверить по имеющимся данным" if len(sub)<50 else ("подтверждена" if p is not None and p<.05 and rho>0.1 else "не подтверждена")
    bins=[]
    if len(sub)>=4:
        try:
            sub["price_bin"]=pd.qcut(sub.price_rub,4,duplicates="drop"); bins=sub.groupby("price_bin",observed=True).agg(n=("review_id","size"),median_price=("price_rub","median"),mean_detail=("detail_score","mean"),median_words=("word_count","median")).reset_index().astype({"price_bin":str}).to_dict("records")
        except ValueError: pass
    return {"hypothesis":"H5","n":int(len(sub)),"metrics":{"price_coverage":float(len(sub)/len(df)) if len(df) else 0,"detail_formula":"Среднее z-оценок log1p(word_count), log1p(sentence_count), log1p(unique_words), log1p(aspects_count)","spearman_rho":rho,"rho_ci":ci,"price_bins":bins,"robust_regression":regression},"test":"Spearman; bootstrap 95% CI; robust regression detail_score ~ log(price) + furniture_group","p_value":p,"effect_size":rho,"verdict":verdict,"limitations":"Цена отсутствует как поле и извлечена только из явных сумм в тексте; сумма может относиться не к товару, поэтому причинный вывод невозможен."}, sub


def evaluate_all(df):
    r1=h1(df); r2=h2(df); r3=h3(df); r4=h4(df); r5,h5data=h5(df); results=[r1,r2,r3,r4,r5]
    raw=[]; refs=[]
    for i,r in enumerate(results):
        if r["hypothesis"]=="H4":
            for j,p in enumerate(r["component_p_values"]): raw.append(p); refs.append((i,j))
        elif r["p_value"] is not None: raw.append(r["p_value"]); refs.append((i,None))
    adjusted=bh_adjust(raw) if raw else []
    for value,(i,j) in zip(adjusted,refs):
        if j is None: results[i]["adjusted_p_value"]=value
        else: results[i].setdefault("component_adjusted_p_values",[]).append(value)
    return results,h5data


def save_results(results, path):
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
