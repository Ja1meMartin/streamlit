import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

now = datetime.now()

first_dose = "people_vaccinated_per_hundred"
second_dose = "people_fully_vaccinated_per_hundred"

def s(rw, func):
    return rw.rolling(28, min_periods=1).apply(func)

def diff(window):
    return (window - window.shift(1)).replace(np.nan, 0)

def recent_days(df, days):
    return df[df.date > datetime.now() - pd.to_timedelta(f'{days}day')]

def add_future_dates(df):
    ftr =  (df['date'] + pd.Timedelta(56, unit='days')).to_frame()
    ftr["tag"] = "future"
    ftr=ftr.assign(
        diff1=recent_days(df,10).groupby(level=0)["diff1"].max(),
        diff2=recent_days(df,21).groupby(level=0)["diff1"].max()
    )

    # join the future data
    df1 = pd.concat([df, ftr], 
                    ignore_index=False).reset_index().drop_duplicates(
        subset=["location", "date"]
    ).set_index("location")
    
    df1["tag"] = df1.tag.replace(np.nan, "present")
    
    return df1

@st.cache
def load_df(y,m,h,d):
    """load the data every hour"""
    df = pd.read_csv("https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv")
    df['date'] = pd.to_datetime(df['date'])
    df = df[["location", "date", first_dose, second_dose]]
    df['tag'] = "present"
    df=df.set_index("location")

    df=df.assign(
        diff1=df.groupby(level=0)[first_dose].apply(diff),
        diff2=df.groupby(level=0)[second_dose].apply(diff)
    )

    df = add_future_dates(df).reset_index().set_index("location")
    return df

df = load_df(now.year, now.month, now.day, now.hour)

first_dose_efficacy = st.sidebar.slider("Percentage of vaccination from first dose", 0.2, 1.0, 0.8, 0.01)
first_dose_delay=st.sidebar.slider("How many days before first dose takes affect", 0, 21, 7, 1)
second_dose_days=st.sidebar.slider("How many days does the second dose need before maximum efficacy", 7, 14, 7, 1)

def score1(ls):
    return sum((first_dose_efficacy/(28-first_dose_delay)) * vaccines 
               for i, vaccines in enumerate(ls, start=1) 
               if  i > first_dose_delay) if len(ls) > first_dose_delay else 0

def score2(ls):
    return sum(((1-first_dose_efficacy)/second_dose_days) * vaccines 
               for i, vaccines in enumerate(ls, start=1) ) if ls is not None else 0




df = df.reset_index().assign(
    daily1=df.reset_index().groupby(["location"])['diff1'].apply(lambda rw: rw.rolling(28, min_periods=1).apply(score1)),
    daily2=df.reset_index().groupby(["location"])['diff2'].apply(lambda rw: rw.rolling(7, min_periods=1).apply(score2))
              )
df['daily1'].replace(np.nan, 0, inplace=True)
df['daily2'].replace(np.nan, 0, inplace=True)
df = df.assign(daily_total=df.daily1 + df.daily2)
df = df.assign(rolling_score=df.groupby("location").daily_total.cumsum())
df = df.assign(rolling_score=np.where(df.rolling_score <=100, df.rolling_score, 100))
df = df.assign(weekly=df.groupby("location")['rolling_score'].apply(lambda window: (window - window.shift(7)).replace(np.nan, 0)))


countries = st.multiselect("Choose locations:", list(set(df.location)), 
"Ireland,Northern Ireland,Israel,Chile,European Union,United States".split(","))

if countries:
    df = df[df.location.isin(countries)]


fig = px.line(df, x="date", y="rolling_score", color='location')

st.plotly_chart(fig)
