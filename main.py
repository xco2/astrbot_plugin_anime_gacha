from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import random

from .data_holder import DataHolder


@register("anime-gacha",
          "xco2",
          "抽番",
          "0.5.0",
          "https://github.com/xco2/astrbot_plugin_anime_gacha")
class AnimeGacha(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_holder = DataHolder()
        logger.info("加载AnimeGacha完毕")

    # @filter.command("今日番剧")
    # async def find_anime(self, event: AstrMessageEvent):
    #     """
    #     抽取一部番剧
    #     """
    #     user_name = event.get_sender_name()
    #     message_str = event.message_str  # 用户发的纯文本消息字符串
    #     message_chain = event.get_messages()  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
    #     logger.info(message_chain)
    #     logger.info(event.message_obj)
    #     yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")  # 发送一条纯文本消息

    @filter.command("抽番")
    async def today_recommend_anime(self, event: AstrMessageEvent):
        """
        获取今日推荐番剧
        """

        recommend_data = await self.data_holder.get_today_recommend_animes()
        TMPL = """
         <style>
            .container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 20px;
                padding: 20px;
                max-width: 1200px;
                margin: 0 auto;
            }
    
            .item {
                position: relative;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
    
            .item img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                aspect-ratio: 2/3;
                display: block;
            }
    
            .item figcaption {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                background: linear-gradient(transparent, rgba(0,0,0,0.7));
                color: white;
                padding: 15px;
                font-size: 20px;
                text-align: center;
                font-weight: bold;
                text-shadow: 2px 0 black, -2px 0 black, 0 2px black, 0 -2px black;
            }
        </style>
        <div class="container">
        {% for b in boxs %}
            {{b}}
        {% endfor %}
        </div>
        """
        box_temp = """
        <figure class="item">
            <img src={src}>
            <figcaption>{name}</figcaption>
        </figure>
        """
        boxs = [box_temp.format(src=v['image_url'], name=k) for k, v in recommend_data.items()]
        url = await self.html_render(TMPL, {"boxs": random.choices(boxs, k=10)})
        yield event.image_result(url)

    @filter.command("今日番剧")
    async def today_update_anime(self, event: AstrMessageEvent):
        """
        获取今日更新番剧
        """
        user_name = event.get_sender_name()
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = event.get_messages()  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        logger.info(event.message_obj)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")  # 发送一条纯文本消息

    @filter.command("新番")
    async def find_anime(self, event: AstrMessageEvent):
        """
        抽取一部番剧,如:'/新番 202501'代表查找2025年1月新番
        """
        user_name = event.get_sender_name()
        message_str = event.message_str  # 用户发的纯文本消息字符串

        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")  # 发送一条纯文本消息

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
        pass
