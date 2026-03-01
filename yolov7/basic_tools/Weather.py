# -*- coding: utf-8 -*-
# @Time    : 2024/11/18 8:54
# @Author  : zlh
# @File    : Weather.py
import requests
def get_weather():
    url = 'https://restapi.amap.com/v3/weather/weatherInfo?parameters'
    params_realtime = {
        'key':'8bc7609b606cd650d35af22254fa3e0a',
        'city':'350100', # 从城市编码里获取的a丢包code
        'extensions':'base' # 获取实时天气
    }
    params_estimate = {
        'key':'8bc7609b606cd650d35af22254fa3e0a',
        'city':'350100',
        'extensions':'all' #获取预报天气
    }

    res = requests.get(url=url,params=params_estimate) # 预报天气
    res2 = requests.get(url=url,params=params_realtime) # 实时天气
    tianqi = res.json()
    # print(tianqi)
    tianqi2 = res2.json()
    # print(tianqi2)

    # print(tianqi.get('forecasts'))
    # province = tianqi.get('forecasts')[0].get("province") # 获取省份
    province = tianqi['forecasts'][0]["province"] # 获取省份
    city = tianqi.get('forecasts')[0].get("city") # 获取城市
    adcode = tianqi.get('forecasts')[0].get("adcode") # 获取城市编码
    reporttime = tianqi.get('forecasts')[0].get("reporttime") # 获取发布数据时间
    date = tianqi.get('forecasts')[0].get("casts")[0].get('date') # 获取日期
    week = tianqi.get('forecasts')[0].get("casts")[0].get('week') # 获取星期几
    dayweather = tianqi.get('forecasts')[0].get("casts")[0].get('dayweather') # 白天天气现象
    nightweather = tianqi.get('forecasts')[0].get("casts")[0].get('nightweather') # 晚上天气现象
    daytemp = tianqi.get('forecasts')[0].get("casts")[0].get('daytemp') # 白天温度
    nighttemp = tianqi.get('forecasts')[0].get("casts")[0].get('nighttemp') # 晚上温度
    daywind = tianqi.get('forecasts')[0].get("casts")[0].get('daywind') # 	白天风向
    nightwind = tianqi.get('forecasts')[0].get("casts")[0].get('nightwind') # 晚上风向
    daypower = tianqi.get('forecasts')[0].get("casts")[0].get('daypower') # 白天风力
    nightpower = tianqi.get('forecasts')[0].get("casts")[0].get('nightpower') # 晚上风力

    print("省份:", province)
    print("城市:", city)
    # # print("城市编码:",adcode)
    # print("发布数据时间:",reporttime)
    # print("日期:",reporttime)
    # print("星期:",week)
    print("今日天气:", dayweather)
    # print("晚上天气现象:",nightweather)
    print("白天温度: {}°".format(daytemp))
    # print("晚上温度:",nighttemp)
    # print("白天风向:",daywind)
    # print("晚上风向:",nightwind)
    # print("白天风力:",daypower)
    # print("晚上风力:",nightpower)

    lis = "  {} {}今日天气：{} 气温：{}°".format(province, city, dayweather, daytemp)
    return lis

# get_weather()