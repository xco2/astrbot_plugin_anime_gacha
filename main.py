from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
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
                /* 改为auto-fit自动填充可用空间，缩小最小列宽 */
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                /* 缩小间距和边距 */
                gap: 1px;
                padding: 1px;
                max-width: 1500px;
                margin: 0 auto;
            }
        
            .item {
                position: relative;
                border-radius: 6px;  /* 减小圆角 */
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);  /* 减小阴影 */
                transition: transform 0.2s ease;  /* 加快过渡速度 */
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
                color: white;
                /* 减小内边距和字号 */
                padding: 10px;
                font-size: 20px;
                text-align: center;
                font-weight: bold;
                /* 简化文字阴影 */
                text-shadow: 2px 0 #3e3e3e, -2px 0 #3e3e3e, 0 2px #3e3e3e, 0 -2px #3e3e3e;
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
        choices = random.choices(list(recommend_data.keys()), k=12)
        boxs = [box_temp.format(src=recommend_data[k]['image_url'], name=k) for k in choices]
        url = await self.html_render(TMPL, {"boxs": boxs})
        text_result = "以下是今日推荐的番剧：\n"
        temp = "{index}. {name}\n"
        for i, k in enumerate(choices):
            text_result += temp.format(index=i + 1, name=k)

        chain = [
            Comp.Plain(text_result),
            Comp.Image.fromURL(url),  # 从 URL 发送图片
        ]
        yield event.chain_result(chain)

    @filter.command("今日新番")
    async def today_update_anime(self, event: AstrMessageEvent):
        """
        获取今日更新番剧
        """
        today_data = await self.data_holder.get_today_update_animes()
        temp = """{index}.《{anime_name}》- {state}\n"""
        result_str = ""
        for i, (anime_name, value) in enumerate(today_data.items()):
            result_str += temp.format(index=i + 1, anime_name=anime_name, state="|".join(value['state'])).replace("~",
                                                                                                                  r"\~")
        yield event.plain_result(result_str)

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
        pass
