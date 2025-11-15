from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
import asyncio
from typing import Set

@register("blacklist_manager", "rpg636zjhi", "黑名单管理插件", "1.0.0")
class BlacklistManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化黑名单集合
        self.user_blacklist: Set[str] = set()
        self.group_blacklist: Set[str] = set()
        
        # 加载黑名单数据
        self._load_blacklists()
        
        logger.info(f"黑名单插件已加载，用户黑名单: {len(self.user_blacklist)} 个，群黑名单: {len(self.group_blacklist)} 个")

    def _get_data_dir(self) -> str:
        """获取数据目录"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(current_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _load_blacklists(self):
        """加载黑名单数据"""
        data_dir = self._get_data_dir()
        
        # 加载用户黑名单
        user_file = os.path.join(data_dir, "user_blacklist.json")
        if os.path.exists(user_file):
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.user_blacklist = set(data)
            except Exception as e:
                logger.error(f"加载用户黑名单失败: {e}")
        
        # 加载群黑名单
        group_file = os.path.join(data_dir, "group_blacklist.json")
        if os.path.exists(group_file):
            try:
                with open(group_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.group_blacklist = set(data)
            except Exception as e:
                logger.error(f"加载群黑名单失败: {e}")

    def _save_blacklist(self, blacklist: Set[str], filename: str):
        """保存黑名单数据"""
        try:
            data_dir = self._get_data_dir()
            filepath = os.path.join(data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(list(blacklist), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存黑名单文件 {filename} 失败: {e}")

    @filter.command_group("黑名单")
    def blacklist_group(self):
        '''黑名单管理'''
        pass

    @blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_user_blacklist(self, event: AstrMessageEvent, qq_number: str):
        '''添加用户到黑名单'''
        if not qq_number.isdigit():
            yield event.plain_result("QQ号必须为纯数字")
            return

        self.user_blacklist.add(qq_number)
        self._save_blacklist(self.user_blacklist, "user_blacklist.json")
        
        logger.info(f"已将用户 {qq_number} 加入黑名单")
        yield event.plain_result(f"已成功将用户 {qq_number} 加入黑名单")

    @blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_user_blacklist(self, event: AstrMessageEvent, qq_number: str):
        '''从黑名单移除用户'''
        if not qq_number.isdigit():
            yield event.plain_result("QQ号必须为纯数字")
            return
            
        if qq_number in self.user_blacklist:
            self.user_blacklist.remove(qq_number)
            self._save_blacklist(self.user_blacklist, "user_blacklist.json")
            yield event.plain_result(f"已成功将用户 {qq_number} 移出黑名单")
        else:
            yield event.plain_result(f"用户 {qq_number} 不在黑名单中")

    @blacklist_group.command("list")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_user_blacklist(self, event: AstrMessageEvent):
        '''查看用户黑名单列表'''
        if not self.user_blacklist:
            yield event.plain_result("用户黑名单为空")
        else:
            sorted_list = sorted(self.user_blacklist)
            blacklist_str = "\n".join(sorted_list)
            yield event.plain_result(f"用户黑名单列表 ({len(sorted_list)} 个):\n{blacklist_str}")

    @filter.command_group("群黑名单")
    def group_blacklist_group(self):
        '''群黑名单管理'''
        pass

    @group_blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''添加群到黑名单'''
        if not group_number.isdigit():
            yield event.plain_result("群号必须为纯数字")
            return

        self.group_blacklist.add(group_number)
        self._save_blacklist(self.group_blacklist, "group_blacklist.json")
        
        logger.info(f"已将群 {group_number} 加入黑名单")
        yield event.plain_result(f"已成功将群 {group_number} 加入黑名单")
        
        # 如果当前就在这个群中，自动退群
        if not event.is_private_chat():
            current_group = event.get_group_id()
            if current_group == group_number:
                # 创建退群任务
                asyncio.create_task(self._perform_leave_group(event, group_number))

    @group_blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''从群黑名单移除群'''
        if not group_number.isdigit():
            yield event.plain_result("群号必须为纯数字")
            return
            
        if group_number in self.group_blacklist:
            self.group_blacklist.remove(group_number)
            self._save_blacklist(self.group_blacklist, "group_blacklist.json")
            yield event.plain_result(f"已成功将群 {group_number} 移出黑名单")
        else:
            yield event.plain_result(f"群 {group_number} 不在黑名单中")

    @group_blacklist_group.command("list")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_group_blacklist(self, event: AstrMessageEvent):
        '''查看群黑名单列表'''
        if not self.group_blacklist:
            yield event.plain_result("群黑名单为空")
        else:
            sorted_list = sorted(self.group_blacklist)
            blacklist_str = "\n".join(sorted_list)
            yield event.plain_result(f"群黑名单列表 ({len(sorted_list)} 个):\n{blacklist_str}")

    async def _perform_leave_group(self, event: AstrMessageEvent, group_id: str):
        """执行退群操作 - 这是一个普通的异步函数，不是生成器"""
        try:
            # 发送退群通知
            await event.send(event.plain_result("该群已被管理员拉黑，机器人将自动退出。"))
            
            # 等待一下确保消息发送成功
            await asyncio.sleep(1)
            
            # 执行退群操作
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    await client.api.call_action('set_group_leave', group_id=int(group_id))
                    logger.info(f"已自动退出黑名单群: {group_id}")
        except Exception as e:
            logger.error(f"退出群 {group_id} 失败: {e}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        '''监听群消息，检查黑名单用户和群'''
        try:
            # 检查是否为群聊消息
            if event.is_private_chat():
                return
                
            group_id = event.get_group_id()
            sender_id = event.get_sender_id()
            
            # 检查当前群是否在黑名单中
            if group_id and group_id in self.group_blacklist:
                logger.info(f"检测到在黑名单群 {group_id} 中，准备退群")
                # 创建退群任务
                asyncio.create_task(self._perform_leave_group(event, group_id))
                event.stop_event()
                return

            # 检查发送者是否在用户黑名单中
            if sender_id and sender_id in self.user_blacklist:
                # 在黑名单中，发送警告消息
                import astrbot.api.message_components as Comp
                warning_msg = [
                    Comp.At(qq=sender_id),
                    Comp.Plain("，该用户已被【蛙蛙Bot】管理员加入黑名单，请谨慎对待！")
                ]
                yield event.chain_result(warning_msg)
                event.stop_event()
                
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        '''监听私聊消息，检查黑名单用户'''
        try:
            sender_id = event.get_sender_id()
            if sender_id and sender_id in self.user_blacklist:
                # 在黑名单中，不回复并停止事件传播
                logger.info(f"拦截黑名单用户 {sender_id} 的私聊消息")
                event.stop_event()
        except Exception as e:
            logger.error(f"处理私聊消息时出错: {e}")

    @filter.command("测试退群")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def test_leave(self, event: AstrMessageEvent):
        '''测试退群功能（仅在当前群中有效）'''
        # 检查是否为群聊
        if event.is_private_chat():
            yield event.plain_result("此命令仅在群聊中有效")
            return
            
        group_id = event.get_group_id()
        if group_id:
            yield event.plain_result(f"正在测试退群功能，将在3秒后退出群 {group_id}...")
            
            # 等待3秒
            await asyncio.sleep(3)
            
            # 发送测试退群通知
            yield event.plain_result("这是测试退群功能，机器人将退出此群")
            
            # 等待一下确保消息发送成功
            await asyncio.sleep(1)
            
            # 创建退群任务
            asyncio.create_task(self._perform_leave_group(event, group_id))
        else:
            yield event.plain_result("无法获取群号")

    async def terminate(self):
        '''插件卸载时的清理工作'''
        logger.info("黑名单插件已卸载")