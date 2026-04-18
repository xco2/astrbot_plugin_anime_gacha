import requests
from bs4 import BeautifulSoup, Tag
import re
from astrbot.api import logger


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
    except Exception as e:
        try:
            result['anime_type'] = table.select('td[colspan="2"]')[0].parent.find_all("td")[1].get_text()
        except Exception as e:
            result['anime_type'] = "未知"
            logger.warning(f"无法获取动画类型: {e}")

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
    staff_pattern = re.compile(
        r'([a-zA-Z\u4e00-\u9fa5\u3040-\u309F\u30A0-\u30FF\uff21-\uff3a\uff41-\uff5a]+)\s*：\s*(.+)$'
    )
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
                    if key in staff_data:
                        staff_data[key] += f"、{value}"
                    else:
                        staff_data[key] = value
                else:
                    if last_key is not None:
                        if "(" in line or ")" in line:
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
        for a in td.find_all('a'):
            text = a.get_text(strip=True)
            if "官网" in text:
                link_data["official"] = a['href']
            elif "PV" in text:
                link_data["pv"] = a['href']

        for p in td.find_all('p'):
            text = p.get_text(strip=True)
            if "周" in text or "月" in text:
                broadcast["time"] = text
            elif "话" in text:
                broadcast["episodes"] = text.strip('()')

    result["links"] = link_data
    result["broadcast"] = broadcast

    return result


def _extract_daily_anime_from_legacy_block(daily_anime: BeautifulSoup) -> dict:
    result = {}

    daily_root = daily_anime.find("details") or daily_anime
    day_headers = []
    for table in daily_root.find_all("table"):
        class_names = table.attrs.get("class", [])
        if not any(cls.startswith("date") for cls in class_names):
            continue
        header_text = table.get_text(" ", strip=True)
        if "周" in header_text:
            day_headers.append(table)

    for header in day_headers:
        title = header.get_text(" ", strip=True)
        title = title.replace("周一", "周一 (月)").replace("周二", "周二 (火)").replace("周三", "周三 (水)")
        title = title.replace("周四", "周四 (木)").replace("周五", "周五 (金)").replace("周六", "周六 (土)")
        title = title.replace("周日", "周日 (日)")

        container = header.find_parent("div")
        if container is None:
            continue
        sibling = container.find_next_sibling("div")
        if sibling is None:
            continue

        day_result = {}
        for anime in sibling.find_all("div", recursive=False):
            if anime.find("td") is None:
                continue
            title_td = anime.find("td")
            anime_name = title_td.get_text("", strip=True)
            if not anime_name:
                continue
            anime_state = [p.get_text(strip=True) for p in anime.find_all("p") if p.get("class") != ["area"] and p.get("class") != ["area_c"]]
            anime_image_url = anime.find("a").get("href") if anime.find("a") else ""
            day_result[anime_name] = {"state": anime_state, "image_url": anime_image_url}

        if day_result:
            result[title] = day_result

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
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        div = soup.find("div", {"class": "post-body"})
        blocks = str(div).split("<hr/>") if div else []
        if len(blocks) >= 2:
            daily_anime_block = None
            details_block = None
            for block in blocks:
                if (
                    "周一 (月)" in block or "周二 (火)" in block or "周三 (水)" in block or "周四 (木)" in block
                    or "周五 (金)" in block or "周六 (土)" in block or "周日 (日)" in block
                    or "<details>" in block or "<summary>" in block
                ):
                    daily_anime_block = block
                elif "原作：" in block or "导演：" in block or "动画制作：" in block or "動畫制作：" in block:
                    details_block = block
                if daily_anime_block is not None and details_block is not None:
                    break
            daily_anime = BeautifulSoup(daily_anime_block, "html.parser") if daily_anime_block else None
            details = BeautifulSoup(details_block, "html.parser") if details_block else soup
        else:
            daily_anime = None
            details = soup

        if schedule_time == "202007":
            daily_anime = None

        anime_datas["daily_anime"] = {}
        if daily_anime is not None:
            anime_datas["daily_anime"] = _extract_daily_anime_from_legacy_block(daily_anime)

        anime_details = details.find_all("table")

        anime_datas["anime_details"] = {}
        for ad in anime_details:
            d = anime_html_table_to_json(ad)
            if "title_cn" in d:
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
