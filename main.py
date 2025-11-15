from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
from typing import Set

@register("auto_leave_blacklist", "rpg636zjhi", "自动退群插件", "1.0.0")
class AutoLeaveBlacklist(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化黑名单集合
        self.group_blacklist: Set[str] = set()
        
        # 加载黑名单数据
        self._load_blacklist()
        
        logger.info(f"自动退群插件已加载，群黑名单: {len(self.group_blacklist)} 个")

    def _get_data_dir(self) -> str:
        """获取数据目录"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(current_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _load_blacklist(self):
        """加载黑名单数据"""
        data_dir = self._get_data_dir()
        
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

    def _save_blacklist(self):
        """保存黑名单数据"""
        try:
            data_dir = self._get_data_dir()
            filepath = os.path.join(data_dir, "group_blacklist.json")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(list(self.group_blacklist), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存群黑名单失败: {e}")

    @filter.command_group("群黑名单")
    def group_blacklist_group(self):
        '''群黑名单管理'''
        pass

    @group_blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''添加群到黑名单'''
        if not group_number or not group_number.isdigit():
            yield event.plain_result("群号必须为纯数字")
            return

        self.group_blacklist.add(group_number)
        self._save_blacklist()
        
        logger.info(f"已将群 {group_number} 加入黑名单")
        yield event.plain_result(f"已成功将群 {group_number} 加入黑名单")
        
        # 如果当前就在这个群中，自动退群
        current_group = event.get_group_id()
        if current_group and current_group == group_number:
            await self._leave_group_with_notice(event, group_number)

    @group_blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''从群黑名单移除群'''
        if not group_number or not group_number.isdigit():
            yield event.plain_result("群号必须为纯数字")
            return
            
        if group_number in self.group_blacklist:
            self.group_blacklist.remove(group_number)
            self._save_blacklist()
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

    async def _leave_group_with_notice(self, event: AstrMessageEvent, group_id: str):
        """发送合并转发消息并退群"""
        try:
            # 发送合并转发消息
            from astrbot.api.message_components import Node, Plain
            node = Node(
                uin=event.get_self_id(),  # 使用机器人自己的QQ号
                name="蛙蛙Bot管理团队",
                content=[
                    Plain("该群聊已被拉黑，机器人将自动退出。"),
                    Plain("如有疑问，请联系管理员。")
                ]
            )
            
            # 发送合并转发消息
            yield event.chain_result([node])
            
            # 等待一下确保消息发送成功
            import asyncio
            await asyncio.sleep(1)
            
            # 执行退群操作
            await self._leave_group(event, group_id)
            
        except Exception as e:
            logger.error(f"发送退群通知失败: {e}")
            # 即使发送通知失败，也要尝试退群
            await self._leave_group(event, group_id)

    async def _leave_group(self, event: AstrMessageEvent, group_id: str):
        """执行退群操作"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    await client.api.call_action('set_group_leave', group_id=int(group_id))
                    logger.info(f"已自动退出黑名单群: {group_id}")
                    
        except Exception as e:
            logger.error(f"退出群 {group_id} 失败: {e}")
            yield event.plain_result("退出群失败")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        '''监听群消息，检查是否在黑名单群中'''
        try:
            # 使用正确的方法获取群组ID
            group_id = event.get_group_id()
            
            # 检查是否为群聊消息（group_id不为None）
            if group_id is not None:
                # 检查当前群是否在黑名单中
                if group_id in self.group_blacklist:
                    logger.info(f"检测到在黑名单群 {group_id} 中，准备退群")
                    await self._leave_group_with_notice(event, group_id)
                    event.stop_event()
                    
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")

    @filter.command("test_leave")
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
            import asyncio
            await asyncio.sleep(3)
            
            # 发送测试退群通知
            from astrbot.api.message_components import Node, Plain
            node = Node(
                uin=event.get_self_id(),
                name="蛙蛙Bot",
                content=[
                    Plain("这是测试退群功能"),
                    Plain("机器人将退出此群"),
                    Plain("这只是一个测试")
                ]
            )
            
            yield event.chain_result([node])
            
            # 等待一下确保消息发送成功
            await asyncio.sleep(1)
            
            # 执行退群
            await self._leave_group(event, group_id)
        else:
            yield event.plain_result("无法获取群号")

    async def terminate(self):
        '''插件卸载时的清理工作'''
        logger.info("自动退群插件已卸载")