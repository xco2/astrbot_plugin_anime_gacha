import os
import json
import datetime

from .anime_scraper.scraper import download_new_anime_datas, get_today_recommend
from astrbot.api import logger

class DataHolder:
    def __init__(self):
        # 读取本地缓存的番剧数据
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'anime_datas.json')):
            try:
                with open(os.path.join(os.path.dirname(__file__), 'anime_datas.json'), "r", encoding='utf-8') as f:
                    self.anime_datas = json.load(f, ensure_ascii=False)
            except:
                self.anime_datas = {}
        else:
            self.anime_datas = {}

        # 今日番剧数据
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json')):
            try:
                with open(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json'), "r",
                          encoding='utf-8') as f:
                    self.today_recommend_anime = json.load(f, ensure_ascii=False)
            except:
                self.today_recommend_anime = {"time": ""}
        else:
            self.today_recommend_anime = {"time": ""}

    def save_anime_datas(self):
        with open(os.path.join(os.path.dirname(__file__), 'anime_datas.json'), 'w', encoding='utf-8') as f:
            json.dump(self.anime_datas, f, ensure_ascii=False)

    def save_today_recommend_anime(self):
        with open(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json'), 'w', encoding='utf-8') as f:
            json.dump(self.today_recommend_anime, f, ensure_ascii=False)

    # -------------------------------------------------------------

    # 获取每天更新的番剧数据
    async def get_daily_anime_datas(self, schedule_time: str) -> dict:
        if schedule_time not in self.anime_datas:
            self.anime_datas[schedule_time] = await download_new_anime_datas(schedule_time)
            self.save_anime_datas()

        return self.anime_datas[schedule_time]['daily_anime']

    # 获取每日推荐番剧
    async def get_today_recommend_animes(self) -> dict:
        # 获取现在时间
        now_time = datetime.datetime.now().strftime('%Y-%m-%d')

        if self.today_recommend_anime['time'] != now_time:
            self.today_recommend_anime.update({"time": now_time, "today_recommend_animes": await get_today_recommend()})
            self.save_today_recommend_anime()

        return self.today_recommend_anime['today_recommend_animes']

    # 获取今天更新的番剧
    async def get_today_update_animes(self) -> dict:
        # 获取现在时间
        now_time = datetime.datetime.now()
        year = now_time.strftime('%Y')
        mount = int(now_time.strftime('%m'))
        if mount < 4:
            quarter_time = year + '01'
        elif mount < 7:
            quarter_time = year + '04'
        elif mount < 10:
            quarter_time = year + '07'
        else:
            quarter_time = year + '10'
        # 获取现在周几
        weekday_str = ["周一 (月)", "周二 (火)", "周三 (水)", "周四 (木)", "周五 (金)", "周六 (土)", "周日 (日)"]
        weekday = weekday_str[datetime.datetime.now().weekday()]
        datas = await self.get_daily_anime_datas(quarter_time)
        datas = datas[weekday]
        return datas


if __name__ == '__main__':
    import asyncio

    data_holder = DataHolder()
    data = asyncio.run(data_holder.get_today_update_animes())
    print(data)
