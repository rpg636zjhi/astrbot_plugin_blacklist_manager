from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
from typing import Dict, List, Set

@register("astrbot_plugin_auto_accept_invite", "rpg636zjhi", "QQ群邀请自动同意和主动入群管理", "1.1.0")
class QQGroupManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_path = self.context.get_data_path(self)
        self.blacklist_file = os.path.join(self.data_path, "blacklist.json")
        self.blacklist: Dict[str, Set[str]] = {
            "users": set(),  # 用户黑名单
            "groups": set()  # 群黑名单
        }
        self.load_blacklist()

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
            logger.info("黑名单数据保存成功")
        except Exception as e:
            logger.error(f"保存黑名单数据失败: {e}")

    def is_in_blacklist(self, user_id: str = None, group_id: str = None) -> bool:
        """检查是否在黑名单中"""
        if user_id and user_id in self.blacklist["users"]:
            return True
        if group_id and group_id in self.blacklist["groups"]:
            return True
        return False

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_group_invite(self, event: AstrMessageEvent):
        """处理群邀请事件"""
        try:
            # 检查是否是QQ平台
            if event.get_platform_name() != "aiocqhttp":
                return

            raw_event = event.raw_message
            post_type = raw_event.get('post_type')
            
            # 处理群邀请请求
            if post_type == 'request' and raw_event.get('request_type') == 'group':
                sub_type = raw_event.get('sub_type')
                if sub_type == 'invite':  # 群邀请
                    user_id = str(raw_event.get('user_id'))
                    group_id = str(raw_event.get('group_id'))
                    
                    # 检查黑名单
                    if self.is_in_blacklist(user_id=user_id, group_id=group_id):
                        logger.info(f"拦截黑名单邀请: 用户{user_id} 邀请加入群{group_id}")
                        await self.reject_group_invite(event, raw_event.get('flag'))
                        return
                    
                    # 自动同意
                    logger.info(f"自动同意群邀请: 用户{user_id} 邀请加入群{group_id}")
                    await self.accept_group_invite(event, raw_event.get('flag'))
                    
        except Exception as e:
            logger.error(f"处理群邀请时出错: {e}")

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

    async def join_group(self, event: AstrMessageEvent, group_id: str):
        """主动加入群"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    # 注意：主动加群功能可能需要特定协议端支持
                    await client.api.call_action('_set_group_join', group_id=group_id, approve=True)
                    return True
            return False
        except Exception as e:
            logger.error(f"主动加入群失败: {e}")
            return False

    @filter.command_group("黑名单")
    def blacklist_group(self):
        """黑名单管理指令组"""
        pass

    @blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_add(self, event: AstrMessageEvent, target: str):
        """添加黑名单
        
        Args:
            target(string): QQ号或QQ群号
        """
        try:
            if not target.isdigit():
                yield event.plain_result("请输入有效的QQ号或QQ群号")
                return
            
            # 判断是用户还是群（这里简单判断，实际可能需要更复杂的逻辑）
            # 通常QQ号长度在5-10位，群号长度在6-11位，但这只是粗略判断
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
                result += f"用户黑名单({user_count}个):\n" + ", ".join(self.blacklist["users"]) + "\n"
            
            if self.blacklist["groups"]:
                result += f"群黑名单({group_count}个):\n" + ", ".join(self.blacklist["groups"])
            
            yield event.plain_result(result)
            
        except Exception as e:
            logger.error(f"查看黑名单失败: {e}")
            yield event.plain_result("查看黑名单失败")

    @blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_remove(self, event: AstrMessageEvent, target: str):
        """移除黑名单
        
        Args:
            target(string): QQ号或QQ群号
        """
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

    @filter.command("主动入群")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def join_group_command(self, event: AstrMessageEvent, group_id: str):
        """主动加入指定QQ群
        
        Args:
            group_id(string): 要加入的QQ群号
        """
        try:
            if not group_id.isdigit():
                yield event.plain_result("请输入有效的QQ群号")
                return
            
            if self.is_in_blacklist(group_id=group_id):
                yield event.plain_result(f"群 {group_id} 在黑名单中，无法加入")
                return
            
            yield event.plain_result(f"正在尝试加入群 {group_id}...")
            
            success = await self.join_group(event, group_id)
            if success:
                yield event.plain_result(f"已发送加入群 {group_id} 的请求")
            else:
                yield event.plain_result(f"加入群 {group_id} 失败，请检查协议端是否支持此功能")
                
        except Exception as e:
            logger.error(f"主动入群指令执行失败: {e}")
            yield event.plain_result("主动入群失败")

    async def terminate(self):
        """插件卸载时保存数据"""
        self.save_blacklist()