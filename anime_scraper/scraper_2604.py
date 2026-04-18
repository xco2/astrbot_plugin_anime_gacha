import requests
from bs4 import BeautifulSoup, Tag
import re
from astrbot.api import logger


STAFF_KEYWORDS = {
    "原作", "导演", "監督", "系列构成", "シリーズ構成", "脚本", "角色设计", "キャラクターデザイン",
    "总作画监督", "音响监督", "音楽", "音乐", "动画制作", "制作", "製作", "副导演", "美术监督",
    "色彩设计", "摄影监督", "剪辑", "編集", "CG导演", "3DCG", "总监督"
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _get_text_list(tag: Tag) -> list[str]:
    return [_normalize_text(text) for text in tag.stripped_strings if _normalize_text(text)]


def _looks_like_staff_line(text: str) -> bool:
    if "：" not in text:
        return False
    key = _normalize_text(text.split("：", 1)[0])
    return key in STAFF_KEYWORDS or len(key) <= 8


def _extract_title_info(table: BeautifulSoup, result: dict) -> None:
    title_candidates = []
    for td in table.find_all("td"):
        texts = _get_text_list(td)
        if len(texts) >= 2:
            title_candidates.append((td, texts))

    for td, texts in title_candidates:
        if len(texts) >= 2:
            result.setdefault("title_cn", texts[0])
            result.setdefault("title_jp", texts[1])

            row_tds = td.parent.find_all("td") if td.parent else []
            sibling_texts = [_normalize_text(item.get_text(" ", strip=True)) for item in row_tds if item is not td]
            sibling_texts = [text for text in sibling_texts if text]
            if sibling_texts:
                result.setdefault("anime_type", sibling_texts[0])
            return


def _extract_type_and_tags(table: BeautifulSoup, result: dict) -> None:
    result.setdefault("tags", [])
    for row in table.find_all("tr"):
        for td in row.find_all("td"):
            classes = td.attrs.get("class", [])
            text = _normalize_text(td.get_text(" ", strip=True))
            if not text:
                continue

            if any(c.startswith("type") and not c.startswith("type_tag") for c in classes):
                result["type"] = text
                if result.get("anime_type") == "未知":
                    result["anime_type"] = text

            if any(c.startswith("type_tag") for c in classes):
                result["tags"] = [item.strip() for item in re.split(r"[／/]", text) if item.strip()]


def _extract_staff_and_cast(table: BeautifulSoup, result: dict) -> None:
    staff_pattern = re.compile(
        r'([a-zA-Z\u4e00-\u9fa5\u3040-\u309F\u30A0-\u30FF\uff21-\uff3a\uff41-\uff5a0-9\-·・]+)\s*：\s*(.+)$'
    )
    staff_data = {}
    cast = []

    for td in table.find_all("td"):
        texts = _get_text_list(td)
        if not texts:
            continue

        classes = td.attrs.get("class", [])
        text_blob = "\n".join(texts)
        is_staff_block = any(c.startswith("staff") for c in classes) or any(_looks_like_staff_line(line) for line in texts)
        is_cast_block = any(c.startswith("cast") for c in classes) or any(
            keyword in text_blob for keyword in ["CV", "声优", "聲優", "CAST", "キャスト"]
        )

        if is_staff_block:
            last_key = None
            for line in texts:
                sublines = [item.strip() for item in line.split("/")] if "/" in line and "：" in line else [line]
                for subline in sublines:
                    subline = _normalize_text(subline.replace("&amp", ""))
                    match = staff_pattern.match(subline)
                    if match is not None:
                        key = re.sub(r'\s', '', match.group(1))
                        last_key = key
                        value = _normalize_text(match.group(2))
                        if key in staff_data:
                            staff_data[key] += f"、{value}"
                        else:
                            staff_data[key] = value
                    elif last_key is not None and subline:
                        if "(" in subline or ")" in subline:
                            staff_data[last_key] += subline
                        else:
                            staff_data[last_key] += f"、{subline}"

        if is_cast_block and not is_staff_block:
            for line in texts:
                normalized = _normalize_text(line)
                if normalized in {"CV", "CAST", "キャスト", "声优", "聲優"}:
                    continue
                if normalized.startswith(("CV：", "CV:", "声优：", "聲優：", "CAST：", "CAST:")):
                    normalized = normalized.split("：", 1)[1] if "：" in normalized else normalized.split(":", 1)[1]
                if normalized:
                    cast.append(normalized)

    result["staff"] = staff_data
    result["cast"] = cast


def _extract_links_and_broadcast(table: BeautifulSoup, result: dict) -> None:
    link_data = {}
    broadcast = {}

    for a in table.find_all('a'):
        text = _normalize_text(a.get_text(strip=True))
        href = a.get('href')
        if not href:
            continue
        if "官网" in text or "官方" in text:
            link_data["official"] = href
        elif "PV" in text.upper():
            link_data["pv"] = href

    for p in table.find_all('p'):
        classes = p.attrs.get('class', [])
        text = _normalize_text(p.get_text(" ", strip=True))
        if not text:
            continue

        if any('broadcast' in cls for cls in classes):
            if not broadcast.get("time"):
                broadcast["time"] = text.strip("()（）")
            continue

        if not broadcast.get("time") and ("周" in text or re.search(r"\d{1,2}/\d{1,2}", text)):
            broadcast["time"] = text.strip("()（）")

        if not broadcast.get("episodes") and ("话" in text or "集" in text):
            if re.search(r"\d+\s*[话集]", text):
                broadcast["episodes"] = text.strip("()（）")

    result["links"] = link_data
    result["broadcast"] = broadcast


def _is_detail_table(table: BeautifulSoup) -> bool:
    class_names = []
    for td in table.find_all("td"):
        class_names.extend(td.attrs.get("class", []))
    return any(
        cls.startswith("title_main") or cls.startswith("staff") or cls.startswith("cast") or cls.startswith("link_a")
        for cls in class_names
    )


def anime_html_table_to_json(table: BeautifulSoup) -> dict:
    """
    将番剧的HTML表格转换为JSON格式数据
    """
    result = {
        "anime_type": "未知",
        "tags": [],
        "staff": {},
        "cast": [],
        "links": {},
        "broadcast": {},
    }

    try:
        _extract_title_info(table, result)
        _extract_type_and_tags(table, result)
        _extract_staff_and_cast(table, result)
        _extract_links_and_broadcast(table, result)

        title_cn = result.get("title_cn", "")
        if title_cn:
            result["title_cn"] = title_cn.replace(" ", "").strip()

        title_jp = result.get("title_jp", "")
        if title_jp:
            result["title_jp"] = title_jp.strip()

    except Exception as e:
        logger.exception(e)

    return result


def _extract_daily_anime_from_new_block(daily_anime: BeautifulSoup) -> dict:
    result = {}

    root = daily_anime.find("body") or daily_anime
    day_headers = []
    for table in root.find_all("table"):
        class_names = table.attrs.get("class", [])
        if not any(cls.startswith("date") for cls in class_names):
            continue
        header_text = _normalize_text(table.get_text(" ", strip=True))
        if "周" in header_text:
            day_headers.append(table)

    for header in day_headers:
        title = _normalize_text(header.get_text(" ", strip=True))
        if title in result:
            continue

        container = header.find_parent("div")
        if container is None:
            continue
        sibling = container.find_next_sibling("div")
        if sibling is None:
            continue

        day_result = {}
        for anime in sibling.find_all("div", recursive=False):
            title_td = anime.find("td")
            if title_td is None:
                continue
            anime_name = title_td.get_text("", strip=True)
            if not anime_name:
                continue
            anime_state = [
                p.get_text(strip=True)
                for p in anime.find_all("p")
                if p.get("class") != ["area"] and p.get("class") != ["area_c"]
            ]
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
                if "周一 (月)" in block or "周二 (火)" in block or "周三 (水)" in block or "周四 (木)" in block or "周五 (金)" in block or "周六 (土)" in block or "周日 (日)" in block:
                    daily_anime_block = block
                elif "原作：" in block or "导演：" in block or "動畫制作：" in block or "动画制作：" in block or "監督：" in block:
                    details_block = block
                if daily_anime_block is not None and details_block is not None:
                    break
            daily_anime = BeautifulSoup(daily_anime_block, "html.parser") if daily_anime_block else None
            details = BeautifulSoup(details_block, "html.parser") if details_block else soup
        else:
            daily_anime = None
            details = soup

        anime_datas["daily_anime"] = {}
        if daily_anime is not None:
            anime_datas["daily_anime"] = _extract_daily_anime_from_new_block(daily_anime)

        anime_details = [table for table in details.find_all("table") if _is_detail_table(table)]

        anime_datas["anime_details"] = {}
        for ad in anime_details:
            d = anime_html_table_to_json(ad)
            if "title_cn" in d and d["title_cn"]:
                anime_datas["anime_details"].update({d["title_cn"]: d})

    else:
        raise ValueError(f"获取番剧信息失败, 无法访问:{url}")

    return anime_datas
