from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import Optional
import os
import json
import re

# 默认配置Schema（自动创建）
DEFAULT_CONF_SCHEMA = {
    "blacklist": {
        "description": "黑名单配置",
        "type": "object",
        "items": {
            "group_ids": {
                "description": "黑名单群号列表",
                "type": "list",
                "hint": "填写群号（字符串格式），多个群号用逗号分隔",
                "default": []
            },
            "user_ids": {
                "description": "黑名单邀请者QQ列表",
                "type": "list",
                "hint": "填写QQ号（字符串格式），多个QQ用逗号分隔",
                "default": []
            }
        }
    }
}

@register(
    "astrbot_plugin_auto_accept_invite",
    "rpg636zjhi",
    "QQ群邀请自动同意（有黑名单拦截）和主动入群。",
    "1.1.0",
    "https://github.com/rpg636zjhi/astrbot_plugin_auto_accept_invite"
)
class AutoAcceptInvitePlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self._auto_create_conf_schema()
        self.config = config or {
            "blacklist": {
                "group_ids": [],
                "user_ids": []
            }
        }
        # 缓存QQ平台客户端
        self.qq_client = None
        logger.info("插件加载成功：支持Bot管理员在群内管理黑名单")

    # 自动创建配置文件
    def _auto_create_conf_schema(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        conf_schema_path = os.path.join(plugin_dir, "_conf_schema.json")
        if not os.path.exists(conf_schema_path):
            try:
                with open(conf_schema_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONF_SCHEMA, f, ensure_ascii=False, indent=2)
                logger.info(f"自动创建配置文件：{conf_schema_path}")
            except Exception as e:
                logger.error(f"创建配置文件失败：{str(e)}")

    # 获取QQ平台客户端
    async def _get_qq_client(self):
        if self.qq_client:
            return self.qq_client
        
        try:
            # 方式1：尝试从platform_manager获取（新版）
            platforms = self.context.platform_manager.get_insts()
            for platform in platforms:
                # 判断是否是QQ个人号平台（aiocqhttp）
                if platform.get_platform_name() == "aiocqhttp":
                    self.qq_client = platform.get_client()
                    return self.qq_client
        except Exception:
            pass

        try:
            # 方式2：尝试兼容旧版导入（备用）
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import AiocqhttpPlatformAdapter
            platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
            if isinstance(platform, AiocqhttpPlatformAdapter):
                self.qq_client = platform.get_client()
                return self.qq_client
        except Exception:
            pass

        logger.error("无法获取QQ平台客户端，入群相关功能失效")
        return None

    # 1. 处理被邀请入群事件（自动同意/拦截）
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_INVITE)
    async def handle_group_invite(self, event: AstrMessageEvent):
        invite_user_id = event.get_sender_id()
        group_id = event.message_obj.group_id
        invite_user_name = event.get_sender_name()
        invite_flag = event.message_obj.raw_message.get("flag")

        if not invite_flag:
            logger.error("未获取到邀请标识，无法处理")
            return

        # 黑名单校验
        if group_id in self.config["blacklist"]["group_ids"]:
            logger.info(f"拒绝加入黑名单群 {group_id}（邀请者：{invite_user_id}）")
            await self.reject_invite(invite_flag)
            yield event.plain_result(f"已拒绝加入黑名单群 {group_id}")
            return
        
        if invite_user_id in self.config["blacklist"]["user_ids"]:
            logger.info(f"拒绝黑名单用户 {invite_user_id} 的邀请")
            await self.reject_invite(invite_flag)
            yield event.plain_result(f"已拒绝黑名单用户 {invite_user_name} 的邀请")
            return

        # 自动同意
        logger.info(f"自动同意加入群 {group_id}（邀请者：{invite_user_name}）")
        await self.accept_invite(invite_flag)
        yield event.plain_result(f"已自动同意加入群 {group_id}，欢迎交流！")

    # 2. 主动入群指令（仅Bot管理员可用）
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.is_admin()
    @filter.command("入群", aliases=["加群"], usage="入群 [QQ群号] - Bot管理员指令，发送入群申请")
    async def handle_join_group_command(self, event: AstrMessageEvent):
        message_text = event.get_plain_text().strip()
        match = re.search(r"入群\s*(\d+)", message_text)
        
        if not match:
            yield event.plain_result("指令格式错误，请使用：入群 [QQ群号]\n例如：入群 123456789")
            return

        target_group_id = match.group(1)
        if not (5 <= len(target_group_id) <= 13 and target_group_id.isdigit()):
            yield event.plain_result("群号格式错误，请输入5-13位数字的有效QQ群号")
            return

        client = await self._get_qq_client()
        if not client:
            yield event.plain_result("获取QQ客户端失败，无法发送入群申请")
            return

        try:
            await client.api.call_action(
                "set_group_add_request",
                group_id=int(target_group_id),
                sub_type="add",
                approve=True
            )
            logger.info(f"Bot管理员触发入群申请：{target_group_id}")
            yield event.plain_result(f"已向群 {target_group_id} 发送入群申请，请等待同意")
        except Exception as e:
            logger.error(f"入群申请失败：{str(e)}")
            yield event.plain_result(f"申请失败：{str(e)}")

    # 3. 黑名单管理指令（仅Bot管理员可用）
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.is_admin()
    @filter.command("添加黑名单群", usage="添加黑名单群 [群号] - 阻止Bot加入该群")
    async def add_blacklist_group(self, event: AstrMessageEvent):
        group_id = self._extract_number_param(event.get_plain_text(), "添加黑名单群")
        if not group_id:
            yield event.plain_result("格式错误：添加黑名单群 [群号]\n例如：添加黑名单群 123456789")
            return
        
        if group_id in self.config["blacklist"]["group_ids"]:
            yield event.plain_result(f"群 {group_id} 已在黑名单中")
            return
        
        self.config["blacklist"]["group_ids"].append(group_id)
        await self._save_config()
        logger.info(f"Bot管理员添加黑名单群：{group_id}")
        yield event.plain_result(f"已将群 {group_id} 加入黑名单")

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.is_admin()
    @filter.command("移除黑名单群", usage="移除黑名单群 [群号] - 允许Bot加入该群")
    async def remove_blacklist_group(self, event: AstrMessageEvent):
        group_id = self._extract_number_param(event.get_plain_text(), "移除黑名单群")
        if not group_id:
            yield event.plain_result("格式错误：移除黑名单群 [群号]\n例如：移除黑名单群 123456789")
            return
        
        if group_id not in self.config["blacklist"]["group_ids"]:
            yield event.plain_result(f"群 {group_id} 不在黑名单中")
            return
        
        self.config["blacklist"]["group_ids"].remove(group_id)
        await self._save_config()
        logger.info(f"Bot管理员移除黑名单群：{group_id}")
        yield event.plain_result(f"已将群 {group_id} 移出黑名单")

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.is_admin()
    @filter.command("添加黑名单用户", usage="添加黑名单用户 [QQ号] - 阻止该用户邀请Bot入群")
    async def add_blacklist_user(self, event: AstrMessageEvent):
        user_id = self._extract_number_param(event.get_plain_text(), "添加黑名单用户")
        if not user_id:
            yield event.plain_result("格式错误：添加黑名单用户 [QQ号]\n例如：添加黑名单用户 123456789")
            return
        
        if user_id in self.config["blacklist"]["user_ids"]:
            yield event.plain_result(f"用户 {user_id} 已在黑名单中")
            return
        
        self.config["blacklist"]["user_ids"].append(user_id)
        await self._save_config()
        logger.info(f"Bot管理员添加黑名单用户：{user_id}")
        yield event.plain_result(f"已将用户 {user_id} 加入黑名单")

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.is_admin()
    @filter.command("移除黑名单用户", usage="移除黑名单用户 [QQ号] - 允许该用户邀请Bot入群")
    async def remove_blacklist_user(self, event: AstrMessageEvent):
        user_id = self._extract_number_param(event.get_plain_text(), "移除黑名单用户")
        if not user_id:
            yield event.plain_result("格式错误：移除黑名单用户 [QQ号]\n例如：移除黑名单用户 123456789")
            return
        
        if user_id not in self.config["blacklist"]["user_ids"]:
            yield event.plain_result(f"用户 {user_id} 不在黑名单中")
            return
        
        self.config["blacklist"]["user_ids"].remove(user_id)
        await self._save_config()
        logger.info(f"Bot管理员移除黑名单用户：{user_id}")
        yield event.plain_result(f"已将用户 {user_id} 移出黑名单")

    # 辅助方法：提取指令中的数字参数
    def _extract_number_param(self, text: str, command: str) -> Optional[str]:
        match = re.search(f"{command}\\s*(\\d+)", text.strip())
        if match:
            param = match.group(1)
            if 5 <= len(param) <= 13:
                return param
        return None

    # 保存配置到文件
    async def _save_config(self):
        try:
            await self.context.update_plugin_config(
                plugin_name="astrbot_plugin_auto_accept_invite",
                config=self.config
            )
            logger.info("黑名单配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败：{str(e)}")

    # 同意邀请
    async def accept_invite(self, invite_flag: str):
        client = await self._get_qq_client()
        if not client:
            return
        try:
            await client.api.call_action(
                "set_group_add_request",
                flag=invite_flag,
                sub_type="invite",
                approve=True
            )
        except Exception as e:
            logger.error(f"同意入群失败：{str(e)}")

    # 拒绝邀请
    async def reject_invite(self, invite_flag: str):
        client = await self._get_qq_client()
        if not client:
            return
        try:
            await client.api.call_action(
                "set_group_add_request",
                flag=invite_flag,
                sub_type="invite",
                approve=False,
                reason="该群/邀请者已被Bot管理员列入黑名单"
            )
        except Exception as e:
            logger.error(f"拒绝入群失败：{str(e)}")

    async def terminate(self):
        logger.info("插件已卸载")
