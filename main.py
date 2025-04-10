from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, llm_tool
import astrbot.api.message_components as Comp
# from astrbot.core.provider.entities import (
#     ProviderRequest,
#     LLMResponse,
# )
import random
import time
import json

from .data_holder import DataHolder, utc8_2_utc9
from .anime_scraper.moegirl_scraper import search_moegirl
from .split_long_text import split_text


# 在url中添加字符防止被qq过滤
def make_unobstructed_url(url: str) -> str:
    url = url.replace("http", "ht删tp")
    url = url.replace("://", ":删//")
    url = url.replace("/", "/删")
    return url


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

        self.message_tail_yuc = ("\n" + "=" * 15 + "\n数据来源:長門有C[yuc点wiki]\n" + "=" * 15)
        self.message_tail_moegirl = ("\n" + "=" * 15 + "\n数据来源:{data}\n" + "=" * 15)

    # @filter.command("demo")
    # async def demo(self, event: AstrMessageEvent):
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
        for line_index, (anime_name, value) in enumerate(today_data.get("当前季度", {}).items()):
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

        if len(today_data.get("下一季度", {})) > 0:
            result_str += "===下一季度===\n"
            for line_index, (anime_name, value) in enumerate(today_data.get("下一季度", {}).items()):
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

        result_str += self.message_tail_yuc
        yield event.plain_result(result_str)

    @filter.command("更新番剧数据")
    async def update_anime_data(self, event: AstrMessageEvent, schedule_time: int):
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
                f"{staff_str}")

        if len(anime_datas) > 1:
            temp += "=" * 15 + "\n"
            temp += "以下是其他相似的番名:\n"
            for anime_data in anime_datas[1:]:
                temp += f"{anime_data['anime_name']}\n"

        temp += self.message_tail_yuc

        yield event.plain_result(temp)

    # =========================================================================
    # 根据wiki的标题进行过滤
    async def filter_wikis_by_title(self, wikis: dict, question: str, contexts: list) -> dict:
        titles = list(wikis.keys())
        titles_str = ""
        for i, t in enumerate(titles):
            titles_str += f"{i + 1}：{t}\n"
        prompt = f"""请分析以下文章标题，找出哪些与用户提问有关
提问：{question}
请用<think>标签包裹你的分析过程，用<answer>标签包裹最后答案，答案应仅包含标题序号，如果有多个，请用、分割：
{titles_str}"""

        # 调用 LLM 判断哪一片文章符合提问
        llm_response = await self.context.get_using_provider().text_chat(
            prompt=prompt,
            contexts=contexts,
            image_urls=[],
            system_prompt="",
        )
        # 截取<answer>内的内容
        logger.info("过滤部分/n" + llm_response.completion_text)
        answer_str = llm_response.completion_text.split("<answer>")[1].split("</answer>")[0]
        selected_titles = answer_str.split("、")
        if len(selected_titles) > 0:
            new_result = {}
            for t in selected_titles:
                try:
                    t = int(t) - 1
                    if titles[t] in wikis:
                        new_result[titles[t]] = wikis[titles[t]]
                except:
                    continue
            return new_result
        else:
            return wikis

    # ----------搜索萌娘百科------------
    # 作为工具
    @llm_tool(name="search_moegirl")
    async def search_moegirl(self, event: AstrMessageEvent, key_word: str):
        """当需要查询萌娘百科上的动画、游戏、声优、导演、游戏制作人等与动漫游戏相关的人物或作品信息时，可以使用这个工具。请确保输入为单个名词（如人名或作品名），避免输入句子或复杂描述。
        例子：用户输入：丰川祥子与三角初华是什么关系？key_word：丰川祥子 三角初华
        Args:
            key_word(string): 要查找的人名或作品名的关键词，如：ave mujica、丰川祥子、海猫络合物。
        """
        async for res in self.search_moegirl_by_key_word(event, key_word):
            yield res

    # 作为命令
    @filter.command("萌娘搜索")
    async def search_moegirl_by_command(self, event: AstrMessageEvent, query: str):
        # 获取对话id
        curr_cid = await self.context.conversation_manager.get_curr_conversation_id(event.unified_msg_origin)
        context = []

        if curr_cid:
            # 如果当前对话 ID 存在，获取对话对象
            conversation = await self.context.conversation_manager.get_conversation(event.unified_msg_origin, curr_cid)
            if conversation and conversation.history:
                context = json.loads(conversation.history)

        prompt = f"""请结合之前的对话内容，分析用户给出的查询，提取出搜索关键词。请确保输出单个名词（如人名或作品名），避免输入句子或复杂描述。
例子：
user：丰川祥子与三角初华是什么关系？
assistant：丰川祥子 三角初华
问题：
{query}
        """
        llm_response = await self.context.get_using_provider().text_chat(
            prompt=prompt,
            contexts=context,
            image_urls=[],
            system_prompt="",
        )
        key_word = llm_response.completion_text
        logger.info(f"搜索关键词：{key_word}")
        async for res in self.search_moegirl_by_key_word(event, key_word):
            yield res

    # 搜索的主要逻辑部分
    async def search_moegirl_by_key_word(self, event: AstrMessageEvent, key_word: str):
        # 获取对话id
        curr_cid = await self.context.conversation_manager.get_curr_conversation_id(event.unified_msg_origin)
        personality_name = "default"
        system_prompt = ""
        context = []

        if curr_cid:
            # 如果当前对话 ID 存在，获取对话对象
            conversation = await self.context.conversation_manager.get_conversation(event.unified_msg_origin, curr_cid)
            personality_name = conversation.persona_id

            for persona in self.context.provider_manager.personas:
                if persona.get('name') == personality_name:
                    system_prompt = persona.get("prompt", "")

            if conversation and conversation.history:
                context = json.loads(conversation.history)[-5:]

        # ---------------------------------------------------
        # 到萌娘百科搜索
        result, data_urls = await search_moegirl(key_word)
        logger.info(f"找到如下文章{data_urls}")
        question = event.message_str

        # 如果找到多篇文章
        if len(result) > 1:
            result = await self.filter_wikis_by_title(result, question, context)

        wiki_chunks = []
        for k, v in result.items():
            for chunk in split_text(v, 2500, 200):
                wiki_chunks.append([k, f"==文章标题：{k}==\n{chunk}"])

        # ------------------------------------------------------------------------
        # 根据段搜索结果生成回复
        llm_results = []
        quote_url = {}
        for title, wiki_chunk in wiki_chunks:
            # 让llm根据结果生成回复
            prompt = f"""请结合下面给出的资料回答问题，这些资料源于萌娘百科
回复要求：
1. 从给定资料中提取信息并回答问题。
2. 根据问题需求，提供简洁、准确、条理分明的回答，避免冗长或偏离主题。
3. 严格基于用户提供的资料内容回答，不进行主观推测或编造信息。
4. 若资料中未提及问题相关内容，则指输出：“资料中未找到相关信息”。
资料：
{wiki_chunk}
问题：
{question}
"""
            llm_response = await self.context.get_using_provider().text_chat(
                prompt=prompt,
                contexts=context,
                image_urls=[],
                system_prompt=system_prompt if len(wiki_chunks) == 1 else "",
            )
            res = llm_response.completion_text

            logger.info(f"对于文章'{title}'中一部分的回答：\n{res}")

            # 如果只有一个结果,则这一次的回答就是最终回答
            if len(wiki_chunks) == 1:
                quote_url[title] = data_urls[title]
                res = llm_response.completion_text + self.message_tail_moegirl.format(
                    data="\n".join([f"{k}:{make_unobstructed_url(v)}" for k, v in quote_url.items()]))
                await self._save_to_history(event, event.get_extra("provider_request"),
                                            llm_response.completion_text)  # 保存历史记录
                yield event.plain_result(res)
                return

            if "资料中未找到" not in res:
                llm_results.append(res)
                quote_url[title] = data_urls[title]

        # ------------------------------------------------------------------------
        # 总结所有生成的回复
        logger.info("正在总结所有生成的回复")
        if len(llm_results) == 0:
            res = f"在萌娘百科上没有找到相关信息。"
            await self._save_to_history(event, event.get_extra("provider_request"), res)
            yield event.plain_result(res)
            return
        elif len(llm_results) == 1:
            if personality_name != "default" and personality_name != "":  # 如果用户有自定义人设
                # 把回答修改为符合人设的
                prompt = (f"基于角色以合适的语气、称呼等，修改下面给出的回答，生成符合人设的回答。\n"
                          f"需要修改的回答：'{llm_results[0]}'")
                llm_response = await self.context.get_using_provider().text_chat(
                    prompt=prompt,
                    contexts=[],
                    image_urls=[],
                    system_prompt=system_prompt,
                )
                res = llm_response.completion_text
            else:
                res = llm_results[0]
            # 保存到历史记录
            await self._save_to_history(event, event.get_extra("provider_request"), res)
            # 添加引用尾巴
            res = res + self.message_tail_moegirl.format(
                data="\n".join([f"{k}:{make_unobstructed_url(v)}" for k, v in quote_url.items()]))
            yield event.plain_result(res)
            return
        else:
            llm_results_text = ""
            for i, res in enumerate(llm_results):
                llm_results_text += f"回答{i + 1}：{res}\n"
            # 总结多个回答
            prompt = f"""请结合下面给出的资料回答问题
背景：这些资料是基于萌娘百科搜索结果对问题的回答，因为有些搜索结果中没有问题的答案，可能会提到‘资料中未找到相关信息’，忽略这些无关回答
回复要求：
1. 从给定资料中提取有用的信息并回答问题。
2. 根据问题需求，提供简洁、准确、条理分明的回答，避免偏离主题。
3. 严格基于用户提供的资料内容回答，不进行主观推测或编造信息。
4. 若资料中未提及问题相关内容，需明确说明“资料中未找到相关信息”。
5. 基于角色以合适的语气、称呼等，生成符合人设的回答。
资料：
{llm_results_text}
问题：
{question}
"""
            llm_response = await self.context.get_using_provider().text_chat(
                prompt=prompt,
                contexts=context,
                image_urls=[],
                system_prompt=system_prompt,
            )
            # 保存到历史记录
            await self._save_to_history(event, event.get_extra("provider_request"), llm_response.completion_text)
            # 添加引用尾巴
            res = llm_response.completion_text + self.message_tail_moegirl.format(
                data="\n".join([f"{k}:{make_unobstructed_url(v)}" for k, v in quote_url.items()]))
            yield event.plain_result(res)
            return

    async def _save_to_history(
            self, event: AstrMessageEvent, req, llm_response: str
    ):
        if not req or not req.conversation or not llm_response:
            return

        elif isinstance(llm_response, str):  # 这里适配手动输入文本加入到历史记录
            content = llm_response
        else:
            return

        # 文本回复
        contexts = req.contexts
        contexts.append(await req.assemble_context())

        # tool calls result
        if req.tool_calls_result:
            contexts.extend(req.tool_calls_result.to_openai_messages())

        contexts.append(
            {"role": "assistant", "content": content}
        )
        contexts_to_save = [item for item in contexts if "_no_save" not in item]

        await self.context.conversation_manager.update_conversation(
            event.unified_msg_origin, req.conversation.cid, history=contexts_to_save
        )

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
        pass
