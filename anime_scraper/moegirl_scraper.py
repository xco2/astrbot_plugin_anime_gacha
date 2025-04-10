import requests
import time
import random
import aiohttp
from bs4 import BeautifulSoup, Tag
import html2text
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; rv:84.0) Gecko/20100101 Firefox/84.0",
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Accept-Language": "en-GB,en;q=0.5",
}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.1.2 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.1 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
]


# 清理文本，去除空格、换行符等
async def _tidy_text(text: str) -> str:
    """清理文本，去除空格、换行符等"""
    return text.strip().replace("\n\n", "\n").replace("\r", " ").replace("  ", " ")


# 过滤内部链接
def convert_internal_links(soup: BeautifulSoup) -> BeautifulSoup:
    """
    将BeautifulSoup对象中同域链接的<a>标签转换为<span>标签，保留内容，跨域链接保持不变

    :param soup: BeautifulSoup对象
    """
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if not href:
            continue

        # 解析URL
        parsed = urlparse(href)

        # 判断是否同域
        is_internal = False
        if not parsed.netloc:  # 相对路径
            is_internal = True

        # 处理同域链接
        if is_internal:
            # 创建新的<p>标签并转移内容
            p_tag = Tag(soup, name='span')

            # 复制所有子节点（保留原有标签结构）
            for child in list(a_tag.contents):
                child.extract()
                p_tag.append(child)

            # 替换原<a>标签
            a_tag.replace_with(p_tag)
    return soup


# 获取网页内容
async def get_md_from_url(url: str) -> str:
    """获取网页内容"""
    header = HEADERS
    header.update({"User-Agent": random.choice(USER_AGENTS)})
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(url, headers=header, timeout=20) as response:
            html = await response.text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            main_content = soup.find("div", class_="mw-parser-output")
            # 删除不必要内容
            for navbox in main_content.find_all('table', class_="navbox"):
                navbox.decompose()
            for notice_dablink in main_content.find_all("div", class_="notice dablink"):
                notice_dablink.decompose()
            for infoBox in main_content.find_all("div", class_="infobox"):
                infoBox.decompose()
            for menu in main_content.find_all("div", id="toc"):
                menu.decompose()
            # 去除内部链接
            main_content = convert_internal_links(main_content)

            # markdown = html2text.html2text(main_content.prettify(), baseurl=url)

            converter = html2text.HTML2Text()
            # converter.ignore_links = True  # 设置忽略链接
            converter.ignore_images = True  # 设置忽略图片
            # converter.ignore_mailto_links = True  # 设置忽略邮件链接

            # 转换 HTML 为纯文本
            markdown = converter.handle(main_content.prettify())

    return await _tidy_text(markdown)


# 在wiki中搜索
async def search_wiki_url(query: str) -> dict[str, str] | None:
    PARAMS = {
        "action": "opensearch",
        "namespace": "0",
        "search": query,
        "limit": "1",
        "format": "json"
    }
    wiki_res = requests.get(url="https://zh.moegirl.org.cn/api.php", params=PARAMS)
    wiki_res = wiki_res.json()
    # print(wiki_res)
    if len(wiki_res[3]) > 0 and len(wiki_res[1]) > 0:
        return {wiki_res[3][0]: wiki_res[1][0]}
    else:
        return None


# 在萌娘百科中直接搜索
async def search_moegirl_url(query: str) -> dict[str, str]:
    """获取网页内容"""
    url = f"https://mzh.moegirl.org.cn/index.php?search={query}&title=Special:%E6%90%9C%E7%B4%A2"
    header = HEADERS
    header.update({"User-Agent": random.choice(USER_AGENTS)})
    res = {}
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(url, headers=header, timeout=20) as response:
            html = await response.text(encoding="utf-8")
            # print(html)
            soup = BeautifulSoup(html, "html.parser")
            searchresults = soup.find_all('div', class_="searchresults")[0]
            for a in searchresults.find_all('a'):
                if len(res) >= 3:
                    break
                href = "https://mzh.moegirl.org.cn" + a.attrs.get('href')
                href = href.split("#")[0]  # 去除定位
                title = BeautifulSoup(a.prettify(), "html.parser").get_text().replace("\n", "").strip()
                if href in res:
                    res[href] += f"({title})"
                else:
                    res[href] = title

    return res


# 从萌娘百科中搜索
async def search_moegirl(query: str) -> tuple[dict[str, str], dict[str, str]]:
    data_urls = {}
    for q in query.split():
        wiki_res = await search_wiki_url(q)
        if wiki_res is not None:
            data_urls.update(wiki_res)
        time.sleep(0.5)

    data_urls.update(await search_moegirl_url(query))

    contents = {}
    if len(data_urls) > 0:
        for data_url, data_title in data_urls.items():
            content = await get_md_from_url(url=data_url)
            contents[data_title] = content
            time.sleep(0.5)

    data_urls = {data_title: data_url for data_url, data_title in data_urls.items()}
    return contents, data_urls


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    contents, url_data = loop.run_until_complete(search_moegirl("doro"))
    print(url_data)
    for k, v in contents.items():
        # with open(f"{k.replace('/', '')}.txt", "w", encoding='utf-8') as f:
        #     f.write(v)
        print(k, v[:100])
        print("-" * 60)
