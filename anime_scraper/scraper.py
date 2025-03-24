import requests
from bs4 import BeautifulSoup, Tag
import re
import os
from astrbot.api import logger


def anime_html_table_to_json(table: BeautifulSoup) -> dict:
    """
    将番剧的HTML表格转换为JSON格式数据
    """
    result = {}

    # 提取标题部分（定位第一个包含两个<p>的<td>）
    title_td = table.select('td[rowspan="2"][colspan="2"]')
    if title_td:
        titles = title_td[0].find_all('p')
        if len(titles) >= 2:
            result["title_cn"] = titles[0].get_text(strip=True)
            result["title_jp"] = titles[1].get_text(strip=True)

    # 提取类型和标签（定位第一个<tr>的第三个<td>）
    rows = table.find_all('tr')
    if len(rows) >= 2:
        type_td = rows[0].find_all('td')
        if len(type_td) >= 3:
            result["type"] = type_td[2].get_text(strip=True)

        tag_td = rows[1].find_all('td')
        if tag_td:
            result["tags"] = tag_td[0].get_text(strip=True).split('/')

    # 提取制作人员（匹配中文职位名称）
    staff_pattern = re.compile(r'([\u4e00-\u9fa5]+)\s*：\s*(.+)$')
    staff_data = {}
    for td in table.select('td[rowspan="2"]'):
        lines = [line.strip() for line in td.stripped_strings]
        for line in lines:
            match = staff_pattern.match(line)
            if match:
                key = match.group(1)
                value = match.group(2)
                if key in staff_data:  # 处理多人同职位
                    staff_data[key] += f"、{value}"
                else:
                    staff_data[key] = value
    result["staff"] = staff_data

    # 提取声优阵容（定位与制作人员同行的<td>）
    cast = []
    for td in table.select('td[rowspan="2"] + td[rowspan="2"]'):
        cast = [name.strip() for name in td.stripped_strings]
    result["cast"] = cast

    # 提取链接和播放信息（匹配特定文本特征）
    link_data = {}
    broadcast = {}
    for td in table.select('td:has(a), td:has(p)'):
        # 处理链接
        for a in td.find_all('a'):
            text = a.get_text(strip=True)
            if "官网" in text:
                link_data["official"] = a['href']
            elif "PV" in text:
                link_data["pv"] = a['href']

        # 处理播放信息
        for p in td.find_all('p'):
            text = p.get_text(strip=True)
            if "周" in text or "月" in text:
                broadcast["time"] = text
            elif "话" in text:
                broadcast["episodes"] = text.strip('()')

    result["links"] = link_data
    result["broadcast"] = broadcast

    return result


async def download_new_anime_datas(schedule_time: str) -> dict:
    """
    获取一个季度的番剧信息
    :param schedule_time: 季度，如202501 代表2025年1月新番
    """
    url = f"https://yuc.wiki/{schedule_time}"
    response = requests.get(url)
    anime_datas = {}
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        div = soup.find("div", {"class": "post-body"})
        blocks = str(div).split("<hr/>")
        daily_anime = BeautifulSoup(blocks[-2], "html.parser")  # 每天更新的番剧
        details = BeautifulSoup(blocks[-1], "html.parser")  # 番剧的详细信息

        anime_datas["daily_anime"] = {}
        daily_animes = [item for item in daily_anime if isinstance(item, Tag)]
        if len(daily_animes) == 1:
            daily_animes = [item for item in daily_animes[0] if isinstance(item, Tag) and item.name == "div"]
        daily_animes = [[daily_animes[i], daily_animes[i + 1]] for i in range(0, len(daily_animes), 3)]
        for da in daily_animes:
            title = da[0].text.strip()  # 星期几
            anime_datas["daily_anime"][title] = {}
            for anime in [item for item in da[1] if isinstance(item, Tag)]:
                anime_name = anime.find("td").text.strip()  # 番剧名
                anime_state = [p.text for p in anime.find_all("p") if p.get("class") != ["area"]]  # 番剧状态 播出时间和总集数
                anime_image_url = anime.find("a").get("href") if anime.find("a") else ""  # 番剧封面图片链接
                anime_datas["daily_anime"][title].update(
                    {anime_name: {"state": anime_state, "image_url": anime_image_url}})

        anime_details = details.find_all("table")

        anime_datas["anime_details"] = {}
        for ad in anime_details:
            d = anime_html_table_to_json(ad)
            anime_datas["anime_details"].update({d["title_cn"]: d})

        return anime_datas
    else:
        logger.error(f"获取番剧信息失败, 无法访问:{url}")
        return anime_datas


async def get_today_recommend() -> dict:
    """
    获取今日推荐番剧
    """
    total_result = {}
    for i in range(1, 6):
        url = f"https://www.agedm.org/recommend/{i}"
        response = requests.get(url)
        if response.status_code == 200:
            result = {}
            soup = BeautifulSoup(response.text, "html.parser")
            video_items = soup.find_all("div", {"class": "video_item"})
            for video_item in video_items:
                img_url = video_item.find("img").get("data-original")
                anime_name = video_item.find("a").text.strip()
                anime_url = video_item.find("a").get("href")
                result.update({anime_name: {"image_url": img_url, "url": anime_url}})
            total_result.update(result)
        else:
            logger.error(f"获取今日推荐番剧失败, 无法访问:{url}")

    return total_result


if __name__ == '__main__':
    import asyncio

    # data1 = asyncio.run(download_new_anime_datas("202501"))
    # data2 = asyncio.run(download_new_anime_datas("202301"))
    # print(data1)
    # print("-" * 60)
    # print(data2)
    data = asyncio.run(get_today_recommend())
    print(data)
