import os
import json
from urllib.parse import quote, unquote
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta
import re
import time

try:
    from anime_scraper.scraper import download_new_anime_datas, get_today_recommend
except ImportError:
    from .anime_scraper.scraper import download_new_anime_datas, get_today_recommend
from rdflib import Graph, URIRef, Literal, Namespace, RDF


def utc8_2_utc9(time_str: str):
    utc8 = timezone(timedelta(hours=8))
    utc9 = timezone(timedelta(hours=9))

    # 解析时间字符串为 datetime 对象，并设置为 UTC+8 时区
    dt_utc8 = datetime.strptime(time_str, '%H:%M').replace(tzinfo=utc8)

    # 转换到 UTC+9 时区
    dt_utc9 = dt_utc8.astimezone(utc9)

    return dt_utc9.strftime('%H:%M')


def quote_sparql(sparql: str) -> str:
    for uri_item in re.findall(r'<anime://(.*?)>', sparql, re.DOTALL):
        sparql = sparql.replace(f'<anime://{uri_item}>', f'<anime://{quote(uri_item)}>')
    return sparql


def create_uri(namespace: Namespace, text: str):
    return URIRef(namespace[quote(text)])


def log(logger, content: str):
    if logger is not None:
        logger.info(content)
    else:
        print(content)


# 限制一个函数调用的频率
def throttle(seconds, logger):
    def decorator(func):
        last_call_time = 0

        def wrapper(*args, **kwargs):
            nonlocal last_call_time
            current_time = time.time()
            elapsed_time = current_time - last_call_time
            if elapsed_time < seconds:
                wait_time = seconds - elapsed_time
                log(logger, f"爬取信息太快啦，等待：{wait_time:.2f}秒...")
                time.sleep(wait_time)
            result = func(*args, **kwargs)
            last_call_time = time.time()
            return result

        return wrapper

    return decorator


class DataHolder:
    def __init__(self, logger=None):
        self.data_version = "v1.0.0"
        self.logger = logger
        self.log_head = "[Anime_Gacha_DataHolder] - "
        # 限制这个爬虫5秒只能用一次,否则等待
        self.download_new_anime_datas = throttle(6, self.logger)(download_new_anime_datas)

        if not os.path.exists(os.path.join(os.path.dirname(__file__), "anime_datas")):
            os.mkdir(os.path.join(os.path.dirname(__file__), "anime_datas"))

        # 读取本地缓存的番剧数据
        self.anime_datas_path = os.path.join(os.path.dirname(__file__), "anime_datas", 'anime_datas.json')
        if os.path.exists(self.anime_datas_path):
            try:
                with open(self.anime_datas_path, "r", encoding='utf-8') as f:
                    self.anime_datas = json.load(f)
            except Exception as e:
                self.anime_datas = {"version": self.data_version}
            # 检查数据版本是否一致
            if self.anime_datas.get("version", None) != self.data_version:
                self.anime_datas = {"version": self.data_version}
            log(self.logger,
                self.log_head + f"读取本地缓存的番剧数据，共{len(self.anime_datas) - 1}个季度数据")  # 有一行是版本信息
        else:
            self.anime_datas = {"version": self.data_version}

        # 今日推荐番剧数据
        self.today_recommend_anime_path = os.path.join(os.path.dirname(__file__), "anime_datas",
                                                       'today_recommend_anime.json')
        if os.path.exists(self.today_recommend_anime_path):
            try:
                with open(self.today_recommend_anime_path, "r", encoding='utf-8') as f:
                    self.today_recommend_anime = json.load(f)
            except Exception as e:
                self.today_recommend_anime = {"time": ""}
        else:
            self.today_recommend_anime = {"time": ""}

        # 构建图
        self.anime_graph_path = os.path.join(os.path.dirname(__file__), "anime_datas", 'anime_graph.ttl')
        self.all_anime_names_save_path = os.path.join(os.path.dirname(__file__), "anime_datas", 'all_anime_names.txt')
        self.anime_ns = Namespace("anime://")
        if os.path.exists(self.anime_graph_path) and os.path.exists(self.all_anime_names_save_path):
            self.anime_graph = Graph()
            self.anime_graph.parse(self.anime_graph_path, format='turtle')

            reload_data = False
            # 查询数据版本号
            for vision in self.anime_graph.objects(subject=self.anime_ns["version"], predicate=self.anime_ns["v"]):
                if vision != self.data_version:
                    reload_data = True
            if not reload_data:  # 版本正确
                with open(self.all_anime_names_save_path, "r", encoding='utf-8') as f:
                    self.all_anime_names = eval(f.read())
                log(self.logger, self.log_head + f"本地缓存图数据，共{len(self.anime_graph)}条数据")
            else:  # 版本落后
                self.all_anime_names = set()
                self.anime_graph = self.create_anime_graph()
                log(self.logger, self.log_head + f"从数据构建图，共{len(self.anime_graph)}条数据")
        else:
            self.all_anime_names = set()
            self.anime_graph = self.create_anime_graph()
            log(self.logger, self.log_head + f"从数据构建图，共{len(self.anime_graph)}条数据")

    # 保存番剧数据
    def save_anime_datas(self) -> None:
        self.anime_datas['version'] = self.data_version
        with open(self.anime_datas_path, 'w', encoding='utf-8') as f:
            json.dump(self.anime_datas, f, ensure_ascii=False)

    # 保存今日推荐番剧数据
    def save_today_recommend_anime(self) -> None:
        with open(self.today_recommend_anime_path, 'w', encoding='utf-8') as f:
            json.dump(self.today_recommend_anime, f, ensure_ascii=False)

    # -------------------------------------------------------------

    # 获取当前季度
    @staticmethod
    def get_now_schedule_time() -> str:
        # 获取现在时间
        now_time = datetime.now()
        year = now_time.strftime('%Y')
        month = int(now_time.strftime('%m'))
        if month < 4:
            quarter_time = year + '01'
        elif month < 7:
            quarter_time = year + '04'
        elif month < 10:
            quarter_time = year + '07'
        else:
            quarter_time = year + '10'
        return quarter_time

    # 获取每天更新的番剧数据
    async def get_daily_anime_datas(self, schedule_time: str, update_now: bool = False) -> dict:
        """
        获取每天更新的番剧数据
        :param schedule_time: 番剧档期
        :param update_now: 是否立即更新
        """
        if update_now or schedule_time not in self.anime_datas or self.anime_datas[schedule_time].get(
                "daily_anime") is None:
            log(self.logger, self.log_head + f"获取{schedule_time}季度的番剧数据")
            await self.update_anime_datas(schedule_time)

        return self.anime_datas[schedule_time].get('daily_anime', {})

    # -------------------------------------------------------------

    # 获取每日推荐番剧
    async def get_today_recommend_animes(self) -> dict:
        # 获取现在时间
        now_time = datetime.now().strftime('%Y-%m-%d')

        if self.today_recommend_anime['time'] != now_time:
            log(self.logger, self.log_head + f"获取今日推荐番剧数据")
            self.today_recommend_anime.update({"time": now_time, "today_recommend_animes": await get_today_recommend()})
            self.save_today_recommend_anime()

        return self.today_recommend_anime['today_recommend_animes']

    # -------------------------------------------------------------

    # 获取今天更新的番剧
    async def get_today_update_animes(self, update_now: bool = False) -> dict:
        quarter_time = self.get_now_schedule_time()
        # 获取现在周几
        weekday_str = ["周一 (月)", "周二 (火)", "周三 (水)", "周四 (木)", "周五 (金)", "周六 (土)", "周日 (日)"]
        weekday = weekday_str[datetime.now().weekday()]
        datas = await self.get_daily_anime_datas(quarter_time, update_now)
        datas = datas.get(weekday, {"没有记录": []})
        datas.update({"现在时间": f"{quarter_time} {weekday}"})
        return datas

    # 更新番剧数据
    async def update_anime_datas(self, schedule_time: str = None) -> None:
        if schedule_time is None:
            schedule_time = self.get_now_schedule_time()
        # 联网获取数据
        self.anime_datas[schedule_time] = await self.download_new_anime_datas(schedule_time)
        self.save_anime_datas()

        # 统计所有番剧名称
        self.get_all_anime_names()
        # 删除这个季度的数据
        self.delete_graph_nodes_with_sche(schedule_time)
        # 添加这个季度的数据到图中
        self.add_one_schedule_time_to_graph(self.anime_graph,
                                            schedule_time,
                                            self.anime_datas[schedule_time],
                                            self.anime_ns)
        self.save_graph(self.anime_graph)
        log(self.logger, self.log_head + f"已更新{schedule_time}季度的番剧数据")

    # 查询番剧详细信息
    async def get_anime_detail(self, anime_name: str) -> list[dict]:
        closest_anime_names = self.find_closest_anime(anime_name, return_all=True)
        all_result = []
        for closest_anime_name in closest_anime_names[:3]:
            log(self.logger, self.log_head + f"找到最接近的番剧名：{anime_name}->{closest_anime_name}")
            sparql = f"""SELECT ?p ?o
                WHERE {{
                    <anime://{closest_anime_name}> ?p ?o .
                }}
            """
            result = self.select_with_sparql(sparql)
            if len(result) == 0:
                result_dict = {"no_result": f"没有找到番剧: {closest_anime_name}"}
            else:
                # 构造为结构化的json
                result_dict = {"anime_name": closest_anime_name, "tags": [], "cv": [], "staff": {}}
                mapping = {
                    "anime://更新日": "update",
                    "anime://tag": "tags",
                    "anime://配音演员": "cv",
                    "anime://official": "官方网站",
                    "anime://pv": "PV",
                    "anime://其他信息": "other",
                    "anime://日文名": "title_jp",
                    "anime://总集数": "总集数",
                    "anime://放送开始日期": "放送开始日期",
                    "anime://档期": "档期",
                    "anime://更新时间": "更新时间",
                    "anime://番剧类型": "番剧类型"
                }

                for row in result:
                    row[1] = row[1].replace("anime://", "")
                    key = row[0]
                    if key in mapping:
                        target_key = mapping[key]
                        if isinstance(result_dict.get(target_key), list):
                            result_dict[target_key].append(row[1])
                        else:
                            result_dict[target_key] = row[1]
                    elif not key.startswith("anime://"):
                        continue
                    else:
                        k = key.replace("anime://", "")
                        if k in result_dict["staff"]:
                            result_dict["staff"][k] += "、" + row[1]
                        else:
                            result_dict["staff"].update({k: row[1]})
            all_result.append(result_dict)
        return all_result

    # -------------------------------------------------------------

    # 找到匹配的名称
    # 在详细信息部分的番剧名和时间表部分的番剧名可能不一致,需要找到匹配的名称
    def find_closest_anime(self, query_anime_name: str, threshold: float = 0.6, return_all=False) -> str | list:
        """
        找到匹配的名称
        :param query_anime_name: 查询的番剧名
        :param threshold: 匹配阈值
        :param return_all: 是否返回所有匹配的名称
        """
        if query_anime_name in self.all_anime_names:
            if return_all:
                return [query_anime_name]
            else:
                return query_anime_name

        closest_ = []
        for name in self.all_anime_names:
            name_without_space = name.replace(" ", "").lower()
            query_without_space = query_anime_name.replace(" ", "").lower()
            matcher = SequenceMatcher(None, name_without_space, query_without_space)
            size = sum([b.size for b in matcher.get_matching_blocks() if b.size > 1])
            if size > 3 and size >= min(len(query_without_space), len(name_without_space)) * threshold:
                closest_.append([name, size])

        # log(self.logger, self.log_head + f"找到{query_anime_name}的匹配结果：{closest_}")
        if len(closest_) == 0:
            if return_all:
                return [query_anime_name]
            else:
                return query_anime_name
        else:
            closest_ = sorted(closest_, key=lambda x: x[1], reverse=True)
            if return_all:
                return [c[0] for c in closest_]
            else:
                return closest_[0][0]

    # 添加一个季度的数据到图中
    def add_one_schedule_time_to_graph(self,
                                       anime_g: Graph,
                                       schedule_time: str,
                                       data: dict,
                                       anime_ns: Namespace) -> None:
        daily_data = data.get('daily_anime', {})
        data = data.get("anime_details")
        if data is None:
            return
        # ------------------------番剧详细信息--------------------------
        for anime_name, anime_info in data.items():
            anime_uri = create_uri(anime_ns, anime_name)

            anime_g.add((anime_uri, RDF.type, Literal("Anime")))  # 实体类型
            anime_g.add((anime_uri, create_uri(anime_ns, "档期"), Literal(schedule_time)))  # 番剧档期
            anime_g.add((anime_uri, create_uri(anime_ns, "日文名"), Literal(anime_info.get("title_jp", ""))))  # 日文名
            anime_g.add(
                (anime_uri, create_uri(anime_ns, "番剧类型"), Literal(anime_info.get("anime_type", ""))))  # 番剧类型

            # 番剧标签
            for tag in anime_info.get("tags", []):
                anime_g.add((anime_uri, create_uri(anime_ns, "tag"), Literal(tag)))

            # 番剧主要人员
            for staff_type, staff_name in anime_info.get("staff", {}).items():
                if "、" in staff_name:
                    staff_names = staff_name.split("、")
                else:
                    staff_names = [staff_name]
                for sn in staff_names:
                    staff_uri = create_uri(anime_ns, sn)
                    anime_g.add((staff_uri, RDF.type, Literal("People")))
                    anime_g.add((anime_uri, create_uri(anime_ns, staff_type), staff_uri))

            # 番剧配音
            for cast_name in anime_info.get("cast", []):
                if "：" in cast_name:  # 就数据是 角色名：演员名
                    cast_name = cast_name.split("：")[1]
                    cast_uri = create_uri(anime_ns, cast_name)
                    anime_g.add((cast_uri, RDF.type, Literal("People")))
                    anime_g.add((anime_uri, create_uri(anime_ns, "配音演员"), cast_uri))
                else:
                    for cv_name in cast_name.split():  # 新数据一行可能有多个cv
                        cv_uri = create_uri(anime_ns, cv_name)
                        anime_g.add((cv_uri, RDF.type, Literal("People")))
                        anime_g.add(
                            (anime_uri, create_uri(anime_ns, "配音演员"), cv_uri))

            # 链接
            for link_name, link_url in anime_info.get("links", {}).items():
                anime_g.add((anime_uri, create_uri(anime_ns, link_name), Literal(link_url)))

            # 总集数
            anime_g.add(
                (anime_uri, create_uri(anime_ns, "总集数"),
                 Literal(anime_info.get('broadcast', {}).get('episodes', ""))))

            # 放送开始日期
            anime_g.add(
                (anime_uri, create_uri(anime_ns, "放送开始日期"),
                 Literal(anime_info.get('broadcast', {}).get('time', ""))))

        # ---------------------------更新时间---------------------------
        for day, anime_info in daily_data.items():
            day_uri = Literal(day)
            for anime_name in anime_info.keys():
                # 寻找番剧的全称
                anime_uri = URIRef(anime_ns[quote(self.find_closest_anime(anime_name))])
                anime_g.add((anime_uri, anime_ns["更新日"], day_uri))  # 番剧更新日 星期几
                states = anime_info[anime_name].get('state', [])
                other_states = []
                for state in states:
                    if ":" in state:
                        anime_g.add((anime_uri, anime_ns["更新时间"], Literal(state)))
                    elif "/" in state:
                        continue  # 这个是首次放松时间,上面已经有了
                    else:
                        other_states.append(state)
                if len(other_states) > 0:
                    anime_g.add((anime_uri, anime_ns["其他信息"], Literal(";".join(other_states))))  # 番剧更新时间

    # 统计所有番剧名称
    def get_all_anime_names(self) -> None:
        for schedule_time, data in self.anime_datas.items():
            if schedule_time == "version":
                continue
            data = data.get("anime_details")
            if data is None:
                continue
            for name in data.keys():
                self.all_anime_names.add(name)

    # 构建图状数据
    def create_anime_graph(self) -> Graph:
        anime_g = Graph()
        anime_g.add((self.anime_ns["version"], self.anime_ns["v"], Literal(self.data_version)))

        # 统计所有番剧名称
        self.get_all_anime_names()

        # 构建图
        for schedule_time, data in self.anime_datas.items():
            if schedule_time == "version":
                continue
            # 添加一个季度的数据到图中
            self.add_one_schedule_time_to_graph(anime_g, schedule_time, data, self.anime_ns)

        # 持久化保存
        self.save_graph(anime_g)
        return anime_g

    # 持久化保存
    def save_graph(self, anime_g) -> None:
        anime_g.serialize(destination=self.anime_graph_path, format='turtle')
        with open(self.all_anime_names_save_path, 'w', encoding='utf-8') as f:
            f.write(str(self.all_anime_names))

    # 删除一个季度的数据
    def delete_graph_nodes_with_sche(self, schedule_time: str) -> None:
        delete_sparql = f"""
        DELETE {{
          ?del_item ?p1 ?o.
          ?s ?p2 ?del_item.
        }}
        WHERE  {{
            {{
            ?del_item ?p1 ?o.
            ?del_item <anime://档期> "{schedule_time}" .
            }}UNION{{
            ?s ?p2 ?del_item.
            ?del_item <anime://档期> "{schedule_time}" .
            }}
        }}
        """
        delete_sparql = quote_sparql(delete_sparql)
        self.anime_graph.update(delete_sparql)

    # 查询图数据
    def select_with_sparql(self, sparql: str) -> list[list[str]]:
        log(self.logger, self.log_head + f"查询SPARQL：{sparql}")
        sparql = quote_sparql(sparql)
        result = self.anime_graph.query(sparql)
        result_list = []
        for row in result:
            result_list.append([unquote(str(item)) for item in row])
        return result_list


if __name__ == '__main__':
    import asyncio

    data_holder = DataHolder()

    # 更新数据
    # asyncio.run(data_holder.update_anime_datas('202410'))
    # time.sleep(3)
    # asyncio.run(data_holder.update_anime_datas('202501'))
    # time.sleep(3)
    # asyncio.run(data_holder.update_anime_datas('202504'))

    data = asyncio.run(data_holder.get_anime_detail("mujica"))
    print(data)
    print(len(data))

    # 获取所有数据
    # for y in ["2025", "2024", "2023", "2022", "2021", "2020", "2019"]:
    #     if y == "2019":
    #         mm = ["10"]
    #     elif y == "2025":
    #         mm = ["01", "04"]
    #     else:
    #         mm = ["01", "04", "07", "10"]
    #     for m in mm:
    #         print(y + m)
    #         data = asyncio.run(data_holder.update_anime_datas(y + m))
    #         # print("data", len(data))
    #         print("=" * 60)
