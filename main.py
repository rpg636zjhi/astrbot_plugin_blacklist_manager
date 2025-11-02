from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
from typing import Set

@register("blacklist_manager", "rpg636zjhi", "黑名单管理插件", "1.1.0")
class BlacklistManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_path = os.path.join(context.get_data_path(), "blacklist_data")
        os.makedirs(self.data_path, exist_ok=True)
        
        # 加载黑名单数据
        self.user_blacklist = self._load_blacklist("user_blacklist.json")
        self.group_blacklist = self._load_blacklist("group_blacklist.json")
        
        logger.info(f"黑名单插件已加载，用户黑名单: {len(self.user_blacklist)} 个，群黑名单: {len(self.group_blacklist)} 个")

    def _load_blacklist(self, filename: str) -> Set[str]:
        """加载黑名单数据"""
        filepath = os.path.join(self.data_path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"加载黑名单文件 {filename} 失败: {e}")
        return set()

    def _save_blacklist(self, blacklist: Set[str], filename: str):
        """保存黑名单数据"""
        filepath = os.path.join(self.data_path, filename)
        try:
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
        '''添加用户到黑名单
        
        Args:
            qq_number(string): 要加入黑名单的QQ号
        '''
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
        '''从黑名单移除用户
        
        Args:
            qq_number(string): 要从黑名单移除的QQ号
        '''
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
            blacklist_str = "\n".join(self.user_blacklist)
            yield event.plain_result(f"用户黑名单列表:\n{blacklist_str}")

    @filter.command_group("群黑名单")
    def group_blacklist_group(self):
        '''群黑名单管理'''
        pass

    @group_blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def add_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''添加群到黑名单
        
        Args:
            group_number(string): 要加入黑名单的群号
        '''
        if not group_number.isdigit():
            yield event.plain_result("群号必须为纯数字")
            return

        self.group_blacklist.add(group_number)
        self._save_blacklist(self.group_blacklist, "group_blacklist.json")
        
        logger.info(f"已将群 {group_number} 加入黑名单")
        yield event.plain_result(f"已成功将群 {group_number} 加入黑名单")

    @group_blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def remove_group_blacklist(self, event: AstrMessageEvent, group_number: str):
        '''从群黑名单移除群
        
        Args:
            group_number(string): 要从黑名单移除的群号
        '''
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
            blacklist_str = "\n".join(self.group_blacklist)
            yield event.plain_result(f"群黑名单列表:\n{blacklist_str}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        '''监听群消息，检查黑名单用户'''
        # 检查当前群是否在黑名单中
        group_id = event.get_group_id()
        if group_id and group_id in self.group_blacklist:
            # 如果在群黑名单中，自动退群
            try:
                if event.get_platform_name() == "aiocqhttp":
                    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                    if isinstance(event, AiocqhttpMessageEvent):
                        client = event.bot
                        await client.api.call_action('set_group_leave', group_id=int(group_id))
                        logger.info(f"已自动退出黑名单群: {group_id}")
            except Exception as e:
                logger.error(f"退出群 {group_id} 失败: {e}")
            return

        # 检查发送者是否在用户黑名单中
        sender_id = event.get_sender_id()
        if sender_id in self.user_blacklist:
            # 在黑名单中，发送警告消息
            import astrbot.api.message_components as Comp
            warning_msg = [
                Comp.At(qq=sender_id),
                Comp.Plain("，该用户已被【蛙蛙Bot】管理员加入黑名单，请谨慎对待！")
            ]
            yield event.chain_result(warning_msg)
            event.stop_event()  # 停止事件传播，防止其他插件处理

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        '''监听私聊消息，检查黑名单用户'''
        sender_id = event.get_sender_id()
        if sender_id in self.user_blacklist:
            # 在黑名单中，不回复并停止事件传播
            event.stop_event()

    async def terminate(self):
        '''插件卸载时的清理工作'''
        logger.info("黑名单插件已卸载")

# 创建配置文件 schema
_conf_schema = {
    "auto_leave_group": {
        "description": "是否自动退出黑名单群",
        "type": "bool",
        "default": True,
        "hint": "启用后，当Bot检测到自己在群黑名单的群时会自动退群"
    },
    "warn_message": {
        "description": "黑名单用户警告消息",
        "type": "string",
        "default": "，该用户已被【蛙蛙Bot】管理员加入黑名单，请谨慎对待！",
        "hint": "当检测到黑名单用户发言时发送的警告消息"
    }
}

# 将schema写入文件
if __name__ != "__main__":
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "_conf_schema.json")
    if not os.path.exists(schema_path):
        try:
            with open(schema_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(_conf_schema, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"创建配置文件schema失败: {e}")