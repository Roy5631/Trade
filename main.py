import json
import requests
import datetime
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from coincheck import account


# 過去のレートを取得する
def pastrate(pair, dt):
    URL = 'https://coincheck.com/ja/exchange/rates/search'
    t = datetime.timedelta(hours=9)
    dt -= t
    dt = str(dt)
    a, b = dt.split()
    b, c = b.split(".")
    time = "{}T{}.{}Z".format(a, b, c[:3])
    res = requests.get(URL, params={"pair": pair, "time": time}).json()
    return float(res["rate"]), res["time"]

# ~~T~~Zの形を、datetime型に変える


def henkan(s):
    s = s[:-1].split("T")
    a = s[0].split("-")
    b = s[1].split(":")
    c = b[-1].split(".")
    dt = datetime.datetime(int(a[0]), int(a[1]), int(a[2]),
                           int(b[0]), int(b[1]), int(c[0]), int(c[1].zfill(1)+"000"))
    dt += datetime.timedelta(hours=9)
    return dt


# datetime型を、~~T~~Zの形に変える

def henkan1(s):
    dt = str(s)
    a, b = dt.split()
    time = "{}T{}.000Z".format(a, b)
    return time


# データを指定したpair,回数,間隔でとってきて作る

def mkdata(pair, n, days=0, hours=0, minutes=0):
    t = datetime.timedelta(days=days, hours=hours, minutes=minutes)
    dt = datetime.datetime.now()
    data = []
    tdata = []
    for i in range(1, n+1):
        dt1 = dt-(n-i)*t
        rate, time = pastrate(pair, dt1)
        data.append(rate)
        tdata.append(time)
    ans = {"time": tdata, "rate": data}
    ans = pd.DataFrame(ans)
    return ans


# n日移動平均を足す

def mv(data, n):
    data["mv"+str(n)] = data["rate"].rolling(n).mean()
    return data


# n日のrsiを追加

def rsi(data, n):
    diff = data["rate"].diff()
    up = diff.copy()
    down = diff.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    up = up.rolling(n).mean()
    down = down.abs().rolling(n).mean()
    data["rsi"] = up/(up+down)*100
    return data


# kσ区間のボリンジャーバンドn個の標準偏差を用いる

def bband(data, n=20, k=2):
    mean = data["rate"].rolling(n).mean()
    std = data["rate"].rolling(n).std()
    data["bbup"] = mean+(std*k)
    data["bbdown"] = mean-(std*k)
    return data


# n個前からの線形回帰

def liner(data, n):
    t = np.array(data["rate"])
    x = np.arange(n).reshape(-1, 1)
    result = LinearRegression().fit(x, t[len(data)-n:].reshape(-1, 1))
    a = result.coef_[0][0]
    b = result.intercept_[0]
    y = []
    for i in range(n):
        y.append(a*i+b)
    data["liner"] = pd.Series(y, index=[len(data)-n+i for i in range(n)])
    return data, a


# 情報をとってくる

def getinfo(secret_key, access_key):
    a = account.Account(secret_key=secret_key, access_key=access_key)
    s = a.get_balance()
    dic = {"name": ['jpy', 'btc', 'eth', 'etc',
                    'lsk', 'fct', 'xrp', 'xem',
                    'ltc', 'bch', 'mona', 'xlm',
                    'qtum', 'bat', 'iost', 'enj'],
           "balance": [s['jpy'], s['btc'], s['eth'], s['etc'],
                       s['lsk'], s['fct'], s['xrp'], s['xem'], s['ltc'],
                       s['bch'], s['mona'], s['xlm'], s['qtum'],
                       s['bat'], s['iost'], s['enj']],
           "reserved": [s['jpy_reserved'], s['btc_reserved'], s['eth_reserved'], s['etc_reserved'],
                        s['lsk_reserved'], s['fct_reserved'], s['xrp_reserved'], s['xem_reserved'],
                        s['ltc_reserved'], s['bch_reserved'], s['mona_reserved'], s['xlm_reserved'],
                        s['qtum_reserved'], s['bat_reserved'], s['iost_reserved'], s['enj_reserved']]}
    dic = pd.DataFrame(dic)
    dic = dic.set_index("name")
    return dic


# LINEで通知

def note(line_notify_token, message):
    line_notify_token = line_notify_token
    line_notify_api = 'https://notify-api.line.me/api/notify'
    payload = {'message': message}
    headers = {'Authorization': 'Bearer ' + line_notify_token}
    return requests.post(line_notify_api, data=payload, headers=headers)


f = open("keys.json", "r")
g = json.load(f)
secret_key = g["secret_key"]
access_key = g["access_key"]
line_notify_token = g["line_notify_token"]
pairs = g["pairs"]


# # 総資産確認
# info = getinfo(secret_key, access_key)

x, y = str(datetime.datetime.now()).split()

message = "\n" + x + "\n" + y + "\n"
p = 0

for i in pairs:
    t = 0
    tmp = ""

    pair = i

    data = mkdata(pair, 21, minutes=10)

    data = mv(data, 3)
    data = mv(data, 7)
    data = rsi(data, 7)
    data = bband(data, 20)
    data, a = liner(data, 20)

    b, c = i.split("_")
    tmp += b.upper()+"\n"

    if data["mv3"][19] < data["mv7"][19] and data["mv3"][20] > data["mv7"][20]:
        tmp += "[買い]mv3がmv7を超えました\n"
        t += 1
    elif data["mv3"][19] > data["mv7"][19] and data["mv3"][20] < data["mv7"][20]:
        tmp += "[売り]mv3がmv7を下回りました\n"
        t += 1
    else:
        pass

    if data["rsi"][19] < 70 and data["rsi"][20] > 70:
        tmp += "[売り]rsiが70を超えました、買われすぎです\n"
        t += 1
    elif data["rsi"][19] > 30 and data["rsi"][20] < 30:
        tmp += "[買い]rsiが30を下回りました、売られすぎです\n"
        t += 1
    else:
        pass

    if data["bbup"][19] > data["rate"][19] and data["bbup"][20] < data["rate"][20]:
        tmp += "[売り]rateがbbupを超えました\n"
        t += 1
    elif data["bbdown"][19] > data["rate"][19] and data["bbdown"][20] < data["rate"][20]:
        tmp += "[買い]rateがbbdownを超えました\n"
        t += 1
    else:
        pass

    if t != 0:
        message += tmp
        p += 1

#     if a >= 0:
#         message += "(a>0)上昇トレンドです"
#     else:
#         message +=  "(a<0)下降トレンドです"

message = message[: len(message) - 1]
al = message.split("\n")
if p != 0:
    note(line_notify_token, message)
