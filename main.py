from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import random
import time

from .data_holder import DataHolder, utc8_2_utc9

@register("anime-gacha",
          "xco2",
          "抽番",
          "0.5.0",
          "https://github.com/xco2/astrbot_plugin_anime_gacha")
class AnimeGacha(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_holder = DataHolder(logger)
        logger.info("加载AnimeGacha完毕")

        self.last_update_anime_data_time = 0

        self.message_tail = ("\n" + "=" * 15 + "\n数据来源:長門有C[http://yuc.wiki/]\n" + "=" * 15)

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
        随机发现一系列番剧
        """
        try:
            recommend_data = await self.data_holder.get_today_recommend_animes()
        except Exception as e:
            logger.error(f"获取今日番剧数据失败: {e}")
            yield event.plain_result("获取今日番剧数据失败")
            return
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
        try:
            if (time.time() - self.last_update_anime_data_time) > 12 * 60 * 60:  # 至少经过12个钟才联网更新
                update_now = True
            else:
                update_now = False
            today_data = await self.data_holder.get_today_update_animes(update_now)
            self.last_update_anime_data_time = time.time()
        except Exception as e:
            logger.error(f"获取今日更新番剧数据失败: {e}")
            yield event.plain_result("获取今日更新番剧数据失败")
            return

        temp = """{index}.《{anime_name}》\n{state}\n"""
        result_str = f"==={today_data.pop('现在时间')}===\n"
        for line_index, (anime_name, value) in enumerate(today_data.items()):
            state = value['state']
            for i in range(len(state)):
                if ':' in state[i]:
                    state[i] = state[i].replace("~", "")
                    # 获得这个时间的
                    utc9_time = utc8_2_utc9(state[i])
                    state[i] = "更新时间:" + state[i] + "(UTC+8); " + utc9_time + "(UTC+9)"
                elif '/' in state[i]:
                    state[i] = "更新日期:" + state[i]

            result_str += temp.format(index=line_index + 1, anime_name=anime_name,
                                      state="\n - ".join(value['state'])).replace("~", r"\~")
            result_str += "-" * 15 + "\n"
        result_str += self.message_tail
        yield event.plain_result(result_str)

    @filter.command("更新番剧数据")
    async def update_anime_data(self, event: AstrMessageEvent, schedule_time: int = None):
        """
        更新番剧数据
        args:
            schedule_time: 番剧档期，格式为 "YYYYMM" 如 202501
        """
        if not isinstance(schedule_time, int):
            yield event.plain_result("参数错误，请输入正确的季度描述，格式为 YYYYMM，如 202501")
            return
        if int(schedule_time) < 201910:
            yield event.plain_result("找不到201910之前的番剧数据")
            return
        schedule_time = str(schedule_time)
        if len(schedule_time) != 6:
            yield event.plain_result("参数错误，请输入正确的季度描述，格式为 YYYYMM，如 202501")

        year = schedule_time[:4]
        month = int(schedule_time[4:])
        if month < 4:
            schedule_time = year + '01'
        elif month < 7:
            schedule_time = year + '04'
        elif month < 10:
            schedule_time = year + '07'
        else:
            schedule_time = year + '10'

        try:
            await self.data_holder.update_anime_datas(schedule_time)
            yield event.plain_result(f"已更新{schedule_time}季度番剧数据")
        except Exception as e:
            logger.error(f"获取{schedule_time}季度番剧数据失败: {e}")
            yield event.plain_result(f"获取{schedule_time}季度番剧数据失败")
            return

    @filter.command("查番")
    async def anime_detail(self, event: AstrMessageEvent, anime_name: str):
        """
        查询番剧详情
        args:
            anime_name: 番剧名称
        """
        try:
            anime_datas = await self.data_holder.get_anime_detail(anime_name)
        except Exception as e:
            logger.error(f"获取{anime_name}番剧数据失败: {e}")
            yield event.plain_result(f"获取{anime_name}番剧数据失败")
            return

        # 详细输出第一个
        anime_data = anime_datas[0]
        if "no_result" in anime_data:
            yield event.plain_result(anime_data['no_result'])
            return

        # staff
        staffs = anime_data.get('staff', {})
        staff_str = ""
        for k, name in staffs.items():
            staff_str += f"{k}: {name}\n"

        # 更新时间
        update_time = anime_data.get('更新时间')
        if update_time:
            update_time = update_time.replace("~", "")
            utc9_update_time = utc8_2_utc9(update_time)
            update_time_str = f"{anime_data.get('update', '')} {update_time} (UTC+8); {utc9_update_time} (UTC+9)"
        else:
            update_time_str = f"{anime_data.get('update', '')}"
        temp = (f"=={anime_data['anime_name']}==\n"
                f"日文名: {anime_data['title_jp']}\n"
                f"档期: {anime_data.get('档期', '-')}\n"
                f"更新时间: {update_time_str}\n"
                f"总集数: {anime_data.get('总集数', '-')}\n"
                f"番剧类型: {anime_data.get('番剧类型', '-')}\n"
                f"cv: {'、'.join(anime_data['cv']) if len(anime_data['cv']) > 0 else '-'}\n"
                f"tags: {'、'.join(anime_data['tags'] if len(anime_data['tags']) > 0 else '-')}\n"
                f"staff: \n"
                f"{staff_str}"
                f"PV: {anime_data.get('PV', '-')}\n"
                f"官方网站: {anime_data.get('官方网站', '-')}\n")

        if len(anime_datas) > 1:
            temp += "=" * 15 + "\n"
            temp += "以下是其他相似的番名:\n"
            for anime_data in anime_datas[1:]:
                temp += f"{anime_data['anime_name']}\n"

        temp += self.message_tail

        yield event.plain_result(temp)

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
        pass
