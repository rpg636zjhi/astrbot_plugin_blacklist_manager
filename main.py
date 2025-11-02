from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import Set
import json
import os

@register("blacklist_manager", "rpg636zjhi", "黑名单管理插件", "1.0.0")
class BlacklistManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_blacklist: Set[str] = set()
        self.group_blacklist: Set[str] = set()
        self.data_file = os.path.join("data", "blacklist_data.json")
        self.load_blacklist()

    def load_blacklist(self):
        """从文件加载黑名单数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_blacklist = set(data.get("user_blacklist", []))
                    self.group_blacklist = set(data.get("group_blacklist", []))
                logger.info("黑名单数据加载成功")
        except Exception as e:
            logger.error(f"加载黑名单数据失败: {e}")

    def save_blacklist(self):
        """保存黑名单数据到文件"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            data = {
                "user_blacklist": list(self.user_blacklist),
                "group_blacklist": list(self.group_blacklist)
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("黑名单数据保存成功")
        except Exception as e:
            logger.error(f"保存黑名单数据失败: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command_group("黑名单")
    def blacklist_group(self):
        '''用户黑名单管理'''
        pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @blacklist_group.command("add")
    async def blacklist_add_user(self, event: AstrMessageEvent, qq_number: str):
        '''
            添加用户到黑名单
        
        Args:
            qq_number(string): 要添加到黑名单的QQ号
        '''

        if not qq_number.isdigit():
            yield event.plain_result("❌ QQ号必须为纯数字")
            return
        
        if qq_number in self.user_blacklist:
            yield event.plain_result(f"❌ QQ号 {qq_number} 已在黑名单中")
            return
        
        self.user_blacklist.add(qq_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将用户 {qq_number} 添加到黑名单")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @blacklist_group.command("remove")
    async def blacklist_remove_user(self, event: AstrMessageEvent, qq_number: str):
        '''从黑名单移除用户
        
        Args:
            qq_number(string): 要从黑名单移除的QQ号
        '''
        if qq_number not in self.user_blacklist:
            yield event.plain_result(f"❌ QQ号 {qq_number} 不在黑名单中")
            return
        
        self.user_blacklist.remove(qq_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将用户 {qq_number} 从黑名单移除")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @blacklist_group.command("list")
    async def blacklist_list_users(self, event: AstrMessageEvent):
        '''查看用户黑名单列表'''
        if not self.user_blacklist:
            yield event.plain_result("📝 用户黑名单为空")
            return
        
        blacklist_str = "\n".join([f"• {qq}" for qq in sorted(self.user_blacklist)])
        yield event.plain_result(f"📋 用户黑名单列表:\n{blacklist_str}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command_group("群黑名单")
    def group_blacklist_group(self):
        '''群组黑名单管理'''
        pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @group_blacklist_group.command("add")
    async def group_blacklist_add(self, event: AstrMessageEvent, group_number: str):
        '''添加群组到黑名单
        
        Args:
            group_number(string): 要添加到黑名单的群号
        '''
        if not group_number.isdigit():
            yield event.plain_result("❌ 群号必须为纯数字")
            return
        
        if group_number in self.group_blacklist:
            yield event.plain_result(f"❌ 群号 {group_number} 已在黑名单中")
            return
        
        self.group_blacklist.add(group_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将群组 {group_number} 添加到黑名单")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @group_blacklist_group.command("remove")
    async def group_blacklist_remove(self, event: AstrMessageEvent, group_number: str):
        '''从黑名单移除群组
        
        Args:
            group_number(string): 要从黑名单移除的群号
        '''
        if group_number not in self.group_blacklist:
            yield event.plain_result(f"❌ 群号 {group_number} 不在黑名单中")
            return
        
        self.group_blacklist.remove(group_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将群组 {group_number} 从黑名单移除")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @group_blacklist_group.command("list")
    async def group_blacklist_list(self, event: AstrMessageEvent):
        '''查看群组黑名单列表'''
        if not self.group_blacklist:
            yield event.plain_result("📝 群组黑名单为空")
            return
        
        blacklist_str = "\n".join([f"• {group}" for group in sorted(self.group_blacklist)])
        yield event.plain_result(f"📋 群组黑名单列表:\n{blacklist_str}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("黑名单状态")
    async def blacklist_status(self, event: AstrMessageEvent):
        '''查看黑名单统计信息'''
        user_count = len(self.user_blacklist)
        group_count = len(self.group_blacklist)
        
        status_msg = (
            "📊 黑名单统计:\n"
            f"• 用户黑名单: {user_count} 个用户\n"
            f"• 群组黑名单: {group_count} 个群组"
        )
        yield event.plain_result(status_msg)

    # 黑名单检查 - 拦截黑名单用户或群组的消息
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def check_blacklist(self, event: AstrMessageEvent):
        '''检查消息是否来自黑名单用户或群组'''
        sender_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        # 检查用户是否在黑名单中
        if sender_id in self.user_blacklist:
            logger.info(f"拦截黑名单用户 {sender_id} 的消息")
            event.stop_event()  # 停止事件传播
            return
        
        # 检查群组是否在黑名单中（如果是群消息）
        if group_id and group_id in self.group_blacklist:
            logger.info(f"拦截黑名单群组 {group_id} 的消息")
            event.stop_event()  # 停止事件传播
            return

    async def terminate(self):
        '''插件卸载时保存数据'''
        self.save_blacklist()
        logger.info("黑名单管理器已卸载")