from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
import asyncio
from typing import Dict, Set

@register("auto_accept_invite", "rpg636zjhi", "QQ群邀请自动同意和主动入群管理", "1.1.1")
class Main(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_path = "data/plugins/auto_accept_invite"
        self.blacklist_file = os.path.join(self.data_path, "blacklist.json")
        self.blacklist: Dict[str, Set[str]] = {"users": set(), "groups": set()}
        self.load_blacklist()
        
        # 启动定时任务检查已加入的群是否在黑名单中
        asyncio.create_task(self.check_group_blacklist())

    def load_blacklist(self):
        """加载黑名单数据"""
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.blacklist = {
                        "users": set(data.get("users", [])),
                        "groups": set(data.get("groups", []))
                    }
                logger.info("黑名单数据加载成功")
        except Exception as e:
            logger.error(f"加载黑名单数据失败: {e}")

    def save_blacklist(self):
        """保存黑名单数据"""
        try:
            os.makedirs(self.data_path, exist_ok=True)
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "users": list(self.blacklist["users"]),
                    "groups": list(self.blacklist["groups"])
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存黑名单数据失败: {e}")

    def is_in_blacklist(self, user_id: str = None, group_id: str = None) -> bool:
        """检查是否在黑名单中"""
        if user_id and user_id in self.blacklist["users"]:
            return True
        if group_id and group_id in self.blacklist["groups"]:
            return True
        return False

    async def check_group_blacklist(self):
        """定期检查并退出黑名单群"""
        await asyncio.sleep(10)  # 等待系统启动完成
        while True:
            try:
                # 获取所有平台
                platforms = self.context.platform_manager.get_insts()
                for platform in platforms:
                    # 只检查aiocqhttp平台
                    if platform.name == "aiocqhttp":
                        # 尝试获取群列表
                        try:
                            # 注意：这里需要根据实际API调整
                            # 不同协议端获取群列表的方法可能不同
                            if hasattr(platform, 'get_group_list'):
                                group_list = await platform.get_group_list()
                                for group in group_list:
                                    group_id = str(group.get('group_id'))
                                    if self.is_in_blacklist(group_id=group_id):
                                        logger.info(f"检测到在黑名单中的群 {group_id}，正在退出...")
                                        await self.leave_group(platform, group_id)
                        except Exception as e:
                            logger.error(f"获取群列表失败: {e}")
                
                # 每5分钟检查一次
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"检查群黑名单时出错: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟再重试

    async def leave_group(self, platform, group_id: str):
        """退出群"""
        try:
            if hasattr(platform, 'call_action'):
                await platform.call_action('set_group_leave', group_id=group_id, is_dismiss=False)
                logger.info(f"已退出黑名单群 {group_id}")
            elif hasattr(platform, 'client'):
                client = platform.client
                await client.api.call_action('set_group_leave', group_id=group_id, is_dismiss=False)
                logger.info(f"已退出黑名单群 {group_id}")
        except Exception as e:
            logger.error(f"退出群 {group_id} 失败: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_group_invite(self, event: AstrMessageEvent):
        """处理群邀请事件"""
        try:
            if event.get_platform_name() != "aiocqhttp":
                return

            raw_msg = event.message_obj.raw_message
            post_type = raw_msg.get('post_type')
            
            if post_type == 'request' and raw_msg.get('request_type') == 'group':
                sub_type = raw_msg.get('sub_type')
                if sub_type == 'invite':
                    user_id = str(raw_msg.get('user_id'))
                    group_id = str(raw_msg.get('group_id'))
                    
                    if self.is_in_blacklist(user_id=user_id, group_id=group_id):
                        logger.info(f"拦截黑名单邀请: 用户{user_id} 邀请加入群{group_id}")
                        await self.reject_group_invite(event, raw_msg.get('flag'))
                        return
                    
                    logger.info(f"自动同意群邀请: 用户{user_id} 邀请加入群{group_id}")
                    await self.accept_group_invite(event, raw_msg.get('flag'))
                    
        except Exception as e:
            logger.error(f"处理群邀请时出错: {e}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_group_message(self, event: AstrMessageEvent):
        """处理群消息，检查是否在黑名单群中"""
        try:
            if event.get_platform_name() != "aiocqhttp":
                return
            
            group_id = event.get_group_id()
            if group_id and self.is_in_blacklist(group_id=group_id):
                logger.info(f"检测到在黑名单群 {group_id} 中，正在退出...")
                await self.leave_group_from_event(event, group_id)
                
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")

    async def leave_group_from_event(self, event: AstrMessageEvent, group_id: str):
        """通过事件退出群"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    await client.api.call_action('set_group_leave', group_id=group_id, is_dismiss=False)
                    logger.info(f"已退出黑名单群 {group_id}")
        except Exception as e:
            logger.error(f"退出群 {group_id} 失败: {e}")

    async def accept_group_invite(self, event: AstrMessageEvent, flag: str):
        """同意群邀请"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    await client.api.call_action('set_group_add_request', flag=flag, sub_type='invite', approve=True)
        except Exception as e:
            logger.error(f"同意群邀请失败: {e}")

    async def reject_group_invite(self, event: AstrMessageEvent, flag: str):
        """拒绝群邀请"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    await client.api.call_action('set_group_add_request', flag=flag, sub_type='invite', approve=False)
        except Exception as e:
            logger.error(f"拒绝群邀请失败: {e}")

    @filter.command_group("黑名单")
    def blacklist_group(self):
        pass

    @blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_add(self, event: AstrMessageEvent, target: str):
        """添加黑名单"""
        try:
            if not target.isdigit():
                yield event.plain_result("请输入有效的QQ号或QQ群号")
                return
            
            if len(target) <= 10:
                self.blacklist["users"].add(target)
                yield event.plain_result(f"已添加用户 {target} 到黑名单")
            else:
                self.blacklist["groups"].add(target)
                yield event.plain_result(f"已添加群 {target} 到黑名单")
            
            self.save_blacklist()
            
        except Exception as e:
            logger.error(f"添加黑名单失败: {e}")
            yield event.plain_result("添加黑名单失败")

    @blacklist_group.command("list")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_list(self, event: AstrMessageEvent):
        """查看黑名单列表"""
        try:
            user_count = len(self.blacklist["users"])
            group_count = len(self.blacklist["groups"])
            
            if user_count == 0 and group_count == 0:
                yield event.plain_result("黑名单为空")
                return
            
            result = "黑名单列表:\n"
            
            if self.blacklist["users"]:
                result += f"用户黑名单({user_count}个):\n" + ", ".join(sorted(self.blacklist["users"])) + "\n"
            
            if self.blacklist["groups"]:
                result += f"群黑名单({group_count}个):\n" + ", ".join(sorted(self.blacklist["groups"]))
            
            yield event.plain_result(result)
            
        except Exception as e:
            logger.error(f"查看黑名单失败: {e}")
            yield event.plain_result("查看黑名单失败")

    @blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_remove(self, event: AstrMessageEvent, target: str):
        """移除黑名单"""
        try:
            removed = False
            if target in self.blacklist["users"]:
                self.blacklist["users"].remove(target)
                removed = True
                yield event.plain_result(f"已从用户黑名单移除 {target}")
            
            if target in self.blacklist["groups"]:
                self.blacklist["groups"].remove(target)
                removed = True
                yield event.plain_result(f"已从群黑名单移除 {target}")
            
            if not removed:
                yield event.plain_result(f"未找到 {target} 在黑名单中")
            else:
                self.save_blacklist()
                
        except Exception as e:
            logger.error(f"移除黑名单失败: {e}")
            yield event.plain_result("移除黑名单失败")

    @filter.command("退出黑名单群")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def leave_blacklist_groups(self, event: AstrMessageEvent):
        """手动触发退出所有黑名单群"""
        try:
            yield event.plain_result("正在检查并退出黑名单群...")
            
            # 获取所有平台
            platforms = self.context.platform_manager.get_insts()
            left_groups = []
            
            for platform in platforms:
                # 只检查aiocqhttp平台
                if platform.name == "aiocqhttp":
                    # 尝试获取群列表
                    try:
                        # 注意：这里需要根据实际API调整
                        # 不同协议端获取群列表的方法可能不同
                        if hasattr(platform, 'get_group_list'):
                            group_list = await platform.get_group_list()
                            for group in group_list:
                                group_id = str(group.get('group_id'))
                                if self.is_in_blacklist(group_id=group_id):
                                    logger.info(f"检测到在黑名单中的群 {group_id}，正在退出...")
                                    await self.leave_group(platform, group_id)
                                    left_groups.append(group_id)
                    except Exception as e:
                        logger.error(f"获取群列表失败: {e}")
            
            if left_groups:
                yield event.plain_result(f"已退出以下黑名单群: {', '.join(left_groups)}")
            else:
                yield event.plain_result("未在黑名单群中")
                
        except Exception as e:
            logger.error(f"退出黑名单群时出错: {e}")
            yield event.plain_result("退出黑名单群时出错")

    async def terminate(self):
        self.save_blacklist()