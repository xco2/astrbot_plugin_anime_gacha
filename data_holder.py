import os
import json
import datetime

from anime_scraper.scraper import download_new_anime_datas, get_today_recommend


class DataHolder:
    def __init__(self):
        self.data_version = "v1.0.0"
        # 读取本地缓存的番剧数据
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'anime_datas.json')):
            try:
                with open(os.path.join(os.path.dirname(__file__), 'anime_datas.json'), "r", encoding='utf-8') as f:
                    self.anime_datas = json.load(f)
            except Exception as e:
                print(e)
                self.anime_datas = {}
            # 检查数据版本是否一致
            if self.anime_datas.get("version", None) != self.data_version:
                self.anime_datas = {}
        else:
            self.anime_datas = {}

        # 今日推荐番剧数据
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json')):
            try:
                with open(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json'), "r",
                          encoding='utf-8') as f:
                    self.today_recommend_anime = json.load(f, ensure_ascii=False)
            except:
                self.today_recommend_anime = {"time": ""}
        else:
            self.today_recommend_anime = {"time": ""}

    # 保存番剧数据
    def save_anime_datas(self):
        self.anime_datas['version'] = self.data_version
        with open(os.path.join(os.path.dirname(__file__), 'anime_datas.json'), 'w', encoding='utf-8') as f:
            json.dump(self.anime_datas, f, ensure_ascii=False)

    # 保存今日推荐番剧数据
    def save_today_recommend_anime(self):
        with open(os.path.join(os.path.dirname(__file__), 'today_recommend_anime.json'), 'w', encoding='utf-8') as f:
            json.dump(self.today_recommend_anime, f, ensure_ascii=False)

    # -------------------------------------------------------------

    # 获取每天更新的番剧数据
    async def get_daily_anime_datas(self, schedule_time: str) -> dict:
        if schedule_time not in self.anime_datas or self.anime_datas[schedule_time].get("daily_anime") is None:
            self.anime_datas[schedule_time] = await download_new_anime_datas(schedule_time)
            self.save_anime_datas()
            print("联网获取")

        return self.anime_datas[schedule_time].get('daily_anime', {})

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
        datas = datas.get(weekday, {"没有记录": []})
        return datas


if __name__ == '__main__':
    import asyncio
    import time

    data_holder = DataHolder()
    # data = asyncio.run(data_holder.get_today_update_animes())
    # print(data)

    # for y in ["2025", "2024", "2023", "2022", "2021", "2020", "2019"]:
    #     if y == "2019":
    #         mm = ["10"]
    #     elif y == "2025":
    #         mm = ["01", "04"]
    #     else:
    #         mm = ["01", "04", "07", "10"]
    #     for m in mm:
    #         print(y + m)
    #         data = asyncio.run(data_holder.get_daily_anime_datas(y + m))
    #         print("data", len(data))
    #         print("daily_anime", len(data.get('daily_anime', {})))
    #         print("anime_details", len(data.get('anime_details', {})))
    #         time.sleep(6)
    #         print("=" * 60)
