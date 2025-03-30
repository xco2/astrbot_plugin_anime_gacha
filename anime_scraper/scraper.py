import requests
from bs4 import BeautifulSoup, Tag
import re


def anime_html_table_to_json(table: BeautifulSoup) -> dict:
    """
    将番剧的HTML表格转换为JSON格式数据
    """
    result = {}

    # 提取标题部分（定位第一个包含两个<p>的<td>）
    title_td = table.select('td[rowspan="2"][colspan="2"]')
    if len(title_td) == 0:
        title_td = table.select('td[colspan="2"]')
    if title_td:
        titles = title_td[0].find_all('p')
        if len(titles) >= 2:
            result["title_cn"] = titles[0].get_text(strip=True)
            result["title_jp"] = titles[1].get_text(strip=True)

    # 提取动画类型
    try:
        result['anime_type'] = table.select('td[rowspan="2"][colspan="2"]')[0].parent.find_all("td")[1].get_text()
    except:
        result['anime_type'] = table.select('td[colspan="2"]')[0].parent.find_all("td")[1].get_text()

    # 提取类型和标签（定位第一个<tr>的第三个<td>）
    rows = table.find_all('tr')
    if len(rows) >= 2:
        for td in rows[0].find_all('td'):
            is_type_td = False
            for c in td.attrs.get("class", []):
                if c.startswith("type"):
                    is_type_td = True
                    break
            if is_type_td:
                result["type"] = td.get_text(strip=True)

        result["tags"] = []
        tag_td = rows[1].find_all('td')[0]
        for c in tag_td.attrs.get("class", []):
            if c.startswith("type_tag"):
                result["tags"] = tag_td.get_text(strip=True).split('/')

    # 提取制作人员（匹配中文职位名称）
    staff_pattern = re.compile(  # 匹配中英日职位名称
        r'([a-zA-Z\u4e00-\u9fa5\u3040-\u309F\u30A0-\u30FF\uff21-\uff3a\uff41-\uff5a]+)\s*：\s*(.+)$')
    staff_data = {}
    for td in table.select('td[rowspan="2"]'):
        is_staff_block = False
        for c in td.attrs.get('class', []):
            if c.startswith("staff"):
                is_staff_block = True
                break
        if not is_staff_block:
            continue
        lines = [line.strip() for line in td.stripped_strings]
        last_key = None
        for line in lines:
            if "/" in line and "：" in line:
                sublines = [l.strip() for l in line.split("/")]
            else:
                sublines = [line]
            for line in sublines:
                line = line.replace("\n", "").replace("\t", "").replace("&amp", "").replace("\u3000", "")
                match = staff_pattern.match(line)
                if match is not None:
                    key = match.group(1)
                    key = re.sub(r'\s', '', key)
                    last_key = key
                    value = match.group(2)
                    if key in staff_data:  # 处理多人同职位
                        staff_data[key] += f"、{value}"
                    else:
                        staff_data[key] = value
                else:  # 一个职位多个人的情况
                    if last_key is not None:
                        if "(" in line or ")" in line:
                            # 例如下的情况
                            # 原作：篠原健太
                            # (少年Jump/集英社)
                            staff_data[last_key] += line
                        else:
                            staff_data[last_key] += f"、{line}"
    result["staff"] = staff_data

    # 提取声优阵容（定位与制作人员同行的<td>）
    cast = []
    for td in table.select('td[rowspan="2"] + td[rowspan="2"]'):
        cast = [name.strip() for name in td.stripped_strings]
    result["cast"] = cast

    # 提取链接和播放信息（匹配特定文本特征）
    link_data = {}
    broadcast = {}
    for td in table.select('td:has(a):has(p)'):
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
        if len(blocks) >= 2:
            daily_anime = BeautifulSoup(blocks[-2], "html.parser")  # 每天更新的番剧
            details = BeautifulSoup(blocks[-1], "html.parser")  # 番剧的详细信息
        else:
            daily_anime = None
            # details = BeautifulSoup(blocks[0], "html.parser")
            details = soup

        if schedule_time == "202007":
            # 受疫情影响，7月番的档期被众多只能播出几集的4月番填补，已定档的新番大都顺延一个季度。
            # 所以这个季度的番剧数据会缺失，所以这里不再处理7月番的情况。
            daily_anime = None

        anime_datas["daily_anime"] = {}
        if daily_anime is not None:
            daily_animes = [item for item in daily_anime if isinstance(item, Tag)]
            while len(daily_animes) == 1:
                daily_animes = [item for item in daily_animes[0] if isinstance(item, Tag) and item.name == "div"]
            daily_animes = [[daily_animes[i], daily_animes[i + 1]] for i in range(0, len(daily_animes), 3)]
            for da in daily_animes:
                title = da[0].text.strip()  # 星期几
                anime_datas["daily_anime"][title] = {}
                for anime in [item for item in da[1] if isinstance(item, Tag)]:
                    if anime.find("td") is not None:
                        anime_name = anime.find("td").text.strip()  # 番剧名
                        anime_state = [p.text for p in anime.find_all("p") if
                                       p.get("class") != ["area"]]  # 番剧状态 播出时间和总集数
                        anime_image_url = anime.find("a").get("href") if anime.find("a") else ""  # 番剧封面图片链接
                        anime_datas["daily_anime"][title].update(
                            {anime_name: {"state": anime_state, "image_url": anime_image_url}})

        # -------------------------------------------------------------------------

        anime_details = details.find_all("table")

        anime_datas["anime_details"] = {}
        for ad in anime_details:
            d = anime_html_table_to_json(ad)
            anime_datas["anime_details"].update({d["title_cn"]: d})

    else:
        raise ValueError(f"获取番剧信息失败, 无法访问:{url}")

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
            raise ValueError(f"获取今日推荐番剧失败, 无法访问:{url}")

    return total_result


if __name__ == '__main__':
    import asyncio

    # data = asyncio.run(download_new_anime_datas("202501"))
    # data = asyncio.run(download_new_anime_datas("202110"))
    # print(data)
    # print(len(data2["anime_details"]))
    # data = asyncio.run(get_today_recommend())
    # print(data2)
