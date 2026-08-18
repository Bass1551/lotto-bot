# -*- coding: utf-8 -*-
from scrapers.base import fetch_html, extract_digits, ScrapeError

SOURCES = {
    # ===== หวยรายวัน + หุ้นปกติ =====
    "laos_extra": {
        "url": "https://laoextra.com/",
        "selector": ".result-number"
    },
    "hanoi_asean": {
        "url": "https://hanoiasean.com",
        "selector": ".result-number"
    },
    "nikkei_morning": {
        "url": "https://indexes.nikkei.co.jp/en/nkave",
        "selector": ".price"
    },
    "china_morning": {
        "url": "http://www.szse.cn/English/index.html",
        "selector": ".index-value"
    },
    "laos_tv": {
        "url": "https://lao-tv.com",
        "selector": ".result"
    },
    "hangseng_morning": {
        "url": "https://www.hsi.com.hk/eng",
        "selector": ".index-value"
    },
    "hanoi_hd": {
        "url": "https://xosohd.com",
        "selector": ".result-number"
    },
    "hanoi_star": {
        "url": "https://minhngocstar.com",
        "selector": ".result"
    },
    "taiwan": {
        "url": "https://www.twse.com.tw/en/",
        "selector": ".index"
    },
    "korea": {
        "url": "http://global.krx.co.kr/main/main.jsp",
        "selector": ".index"
    },
    "nikkei_afternoon": {
        "url": "https://indexes.nikkei.co.jp/en/nkave",
        "selector": ".price"
    },
    "laos_hd": {
        "url": "https://laoshd.com",
        "selector": ".result"
    },
    "china_afternoon": {
        "url": "http://www.szse.cn/English/index.html",
        "selector": ".index-value"
    },
    "hanoi_tv": {
        "url": "https://minhngoctv.com/",
        "selector": ".result"
    },
    "hangseng_afternoon": {
        "url": "https://www.hsi.com.hk/eng",
        "selector": ".index-value"
    },
    "laos_star": {
        "url": "https://www.laostars.com",
        "selector": ".result"
    },
    "singapore": {
        "url": "https://www.sgx.com/wps/portal/sgxweb/home/marketinfo/indices/indice",
        "selector": ".index"
    },
    "thai_evening": {
        "url": "https://marketdata.set.or.th/mkt/marketsummary.do",
        "selector": ".set-index"
    },
    "hanoi_kachad": {
        "url": "https://xosoredcross.com/",
        "selector": ".result"
    },

    # ===== หุ้น VIP =====
    "nikkei_morning_vip": {
        "url": "https://nikkeivipstock.com",
        "selector": ".result"
    },
    "china_morning_vip": {
        "url": "https://shenzhenindex.com",
        "selector": ".result"
    },
    "hangseng_morning_vip": {
        "url": "https://hangsengvip.com",
        "selector": ".result"
    },
    "taiwan_vip": {
        "url": "https://tsecvipindex.com",
        "selector": ".result"
    },
    "korea_vip": {
        "url": "https://ktopvipindex.com",
        "selector": ".result"
    },
    "nikkei_afternoon_vip": {
        "url": "https://nikkeivipstock.com",
        "selector": ".result"
    },
    "china_afternoon_vip": {
        "url": "https://shenzhenindex.com",
        "selector": ".result"
    },
    "hangseng_afternoon_vip": {
        "url": "https://www.hsi-vip.com/",
        "selector": ".result"
    },
}


def scrape_generic(key: str) -> str:
    if key not in SOURCES:
        raise ScrapeError(f"ไม่พบการตั้งค่าแหล่งข้อมูลสำหรับ key='{key}' ใน SOURCES")

    cfg = SOURCES[key]
    soup = fetch_html(cfg["url"])
    element = soup.select_one(cfg["selector"])
    if element is None:
        raise ScrapeError(
            f"ไม่พบ element ตาม selector='{cfg['selector']}' ในหน้า {cfg['url']}"
        )
    return extract_digits(element.get_text())


def get_laos_extra():          return scrape_generic("laos_extra")
def get_hanoi_asean():         return scrape_generic("hanoi_asean")
def get_nikkei_morning():      return scrape_generic("nikkei_morning")
def get_china_morning():       return scrape_generic("china_morning")
def get_laos_tv():             return scrape_generic("laos_tv")
def get_hangseng_morning():    return scrape_generic("hangseng_morning")
def get_hanoi_hd():            return scrape_generic("hanoi_hd")
def get_hanoi_star():          return scrape_generic("hanoi_star")
def get_taiwan():              return scrape_generic("taiwan")
def get_korea():               return scrape_generic("korea")
def get_nikkei_afternoon():    return scrape_generic("nikkei_afternoon")
def get_laos_hd():             return scrape_generic("laos_hd")
def get_china_afternoon():     return scrape_generic("china_afternoon")
def get_hanoi_tv():            return scrape_generic("hanoi_tv")
def get_hangseng_afternoon():  return scrape_generic("hangseng_afternoon")
def get_laos_star():           return scrape_generic("laos_star")
def get_singapore():           return scrape_generic("singapore")
def get_thai_evening():        return scrape_generic("thai_evening")
def get_hanoi_kachad():        return scrape_generic("hanoi_kachad")

def get_nikkei_morning_vip():     return scrape_generic("nikkei_morning_vip")
def get_china_morning_vip():      return scrape_generic("china_morning_vip")
def get_hangseng_morning_vip():   return scrape_generic("hangseng_morning_vip")
def get_taiwan_vip():             return scrape_generic("taiwan_vip")
def get_korea_vip():              return scrape_generic("korea_vip")
def get_nikkei_afternoon_vip():   return scrape_generic("nikkei_afternoon_vip")
def get_china_afternoon_vip():    return scrape_generic("china_afternoon_vip")
def get_hangseng_afternoon_vip(): return scrape_generic("hangseng_afternoon_vip")


SCRAPER_FUNCTIONS = {
    "laos_extra": get_laos_extra,
    "hanoi_asean": get_hanoi_asean,
    "nikkei_morning": get_nikkei_morning,
    "china_morning": get_china_morning,
    "laos_tv": get_laos_tv,
    "hangseng_morning": get_hangseng_morning,
    "hanoi_hd": get_hanoi_hd,
    "hanoi_star": get_hanoi_star,
    "taiwan": get_taiwan,
    "korea": get_korea,
    "nikkei_afternoon": get_nikkei_afternoon,
    "laos_hd": get_laos_hd,
    "china_afternoon": get_china_afternoon,
    "hanoi_tv": get_hanoi_tv,
    "hangseng_afternoon": get_hangseng_afternoon,
    "laos_star": get_laos_star,
    "singapore": get_singapore,
    "thai_evening": get_thai_evening,
    "hanoi_kachad": get_hanoi_kachad,

    "nikkei_morning_vip": get_nikkei_morning_vip,
    "china_morning_vip": get_china_morning_vip,
    "hangseng_morning_vip": get_hangseng_morning_vip,
    "taiwan_vip": get_taiwan_vip,
    "korea_vip": get_korea_vip,
    "nikkei_afternoon_vip": get_nikkei_afternoon_vip,
    "china_afternoon_vip": get_china_afternoon_vip,
    "hangseng_afternoon_vip": get_hangseng_afternoon_vip,
}