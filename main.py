from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import Set, Optional
import json
import os

@register("blacklist_manager", "rpg636zjhi", "黑名单管理插件", "1.1.0")
class BlacklistManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 加载配置
        self.config = self.load_config()
        
        # 初始化黑名单数据
        self.user_blacklist: Set[str] = set()
        self.group_blacklist: Set[str] = set()
        self.data_file = os.path.join("data", "blacklist_data.json")
        self.load_blacklist()

    def load_config(self):
        """加载插件配置"""
        default_config = {
            "enable_interception": True,  # 是否启用黑名单拦截
            "notify_on_intercept": True,  # 拦截时是否通知
            "auto_save_interval": 300,    # 自动保存间隔（秒），0表示禁用自动保存
            "max_blacklist_size": 1000,   # 最大黑名单数量
            "intercept_message": "❌ 您已被加入黑名单，消息无法送达",  # 拦截时发送的消息
            "admin_roles": ["ADMIN"]      # 有权限管理黑名单的角色
        }
        
        # 从配置文件加载或使用默认配置
        config = self.context.config.load_config("blacklist_config", default_config)
        
        # 验证配置值
        if config["auto_save_interval"] < 0:
            config["auto_save_interval"] = 0
            logger.warning("自动保存间隔不能为负数，已设置为0（禁用）")
            
        if config["max_blacklist_size"] < 1:
            config["max_blacklist_size"] = 1000
            logger.warning("最大黑名单数量不能小于1，已设置为1000")
        
        logger.info("黑名单插件配置加载完成")
        return config

    def save_config(self):
        """保存插件配置"""
        self.context.config.save_config("blacklist_config", self.config)
        logger.info("黑名单插件配置已保存")

    def load_blacklist(self):
        """从文件加载黑名单数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_blacklist = set(data.get("user_blacklist", []))
                    self.group_blacklist = set(data.get("group_blacklist", []))
                logger.info("黑名单数据加载成功")
                
                # 检查是否超过最大限制
                if len(self.user_blacklist) > self.config["max_blacklist_size"]:
                    logger.warning(f"用户黑名单数量超过限制，当前: {len(self.user_blacklist)}，限制: {self.config['max_blacklist_size']}")
                
                if len(self.group_blacklist) > self.config["max_blacklist_size"]:
                    logger.warning(f"群组黑名单数量超过限制，当前: {len(self.group_blacklist)}，限制: {self.config['max_blacklist_size']}")
                    
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

    def check_blacklist_limit(self, blacklist_type: str) -> bool:
        """检查黑名单数量是否达到上限"""
        if blacklist_type == "user":
            current_size = len(self.user_blacklist)
        else:
            current_size = len(self.group_blacklist)
            
        if current_size >= self.config["max_blacklist_size"]:
            logger.warning(f"{blacklist_type}黑名单已达到上限 {current_size}/{self.config['max_blacklist_size']}")
            return False
        return True

    @filter.command_group("黑名单")
    @filter.permission_type(filter.PermissionType.ADMIN)
    def blacklist_group(self):
        '''用户黑名单管理'''
        pass

    @blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_add_user(self, event: AstrMessageEvent, qq_number: str):
        '''添加用户到黑名单
        
        Args:
            qq_number(string): 要添加到黑名单的QQ号
        '''
        if not qq_number.isdigit():
            yield event.plain_result("❌ QQ号必须为纯数字")
            return
        
        if qq_number in self.user_blacklist:
            yield event.plain_result(f"❌ QQ号 {qq_number} 已在黑名单中")
            return
        
        # 检查数量限制
        if not self.check_blacklist_limit("user"):
            yield event.plain_result(f"❌ 用户黑名单数量已达到上限 {len(self.user_blacklist)}/{self.config['max_blacklist_size']}")
            return
        
        self.user_blacklist.add(qq_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将用户 {qq_number} 添加到黑名单")

    @blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
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

    @blacklist_group.command("list")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_list_users(self, event: AstrMessageEvent):
        '''查看用户黑名单列表'''
        if not self.user_blacklist:
            yield event.plain_result("📝 用户黑名单为空")
            return
        
        blacklist_str = "\n".join([f"• {qq}" for qq in sorted(self.user_blacklist)[:50]])  # 只显示前50个
        more_info = ""
        if len(self.user_blacklist) > 50:
            more_info = f"\n... 还有 {len(self.user_blacklist) - 50} 个用户未显示"
            
        yield event.plain_result(f"📋 用户黑名单列表 ({len(self.user_blacklist)}/{self.config['max_blacklist_size']}):\n{blacklist_str}{more_info}")

    @filter.command_group("群黑名单")
    @filter.permission_type(filter.PermissionType.ADMIN)
    def group_blacklist_group(self):
        '''群组黑名单管理'''
        pass

    @group_blacklist_group.command("add")
    @filter.permission_type(filter.PermissionType.ADMIN)
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
        
        # 检查数量限制
        if not self.check_blacklist_limit("group"):
            yield event.plain_result(f"❌ 群组黑名单数量已达到上限 {len(self.group_blacklist)}/{self.config['max_blacklist_size']}")
            return
        
        self.group_blacklist.add(group_number)
        self.save_blacklist()
        yield event.plain_result(f"✅ 已成功将群组 {group_number} 添加到黑名单")

    @group_blacklist_group.command("remove")
    @filter.permission_type(filter.PermissionType.ADMIN)
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

    @group_blacklist_group.command("list")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def group_blacklist_list(self, event: AstrMessageEvent):
        '''查看群组黑名单列表'''
        if not self.group_blacklist:
            yield event.plain_result("📝 群组黑名单为空")
            return
        
        blacklist_str = "\n".join([f"• {group}" for group in sorted(self.group_blacklist)[:50]])  # 只显示前50个
        more_info = ""
        if len(self.group_blacklist) > 50:
            more_info = f"\n... 还有 {len(self.group_blacklist) - 50} 个群组未显示"
            
        yield event.plain_result(f"📋 群组黑名单列表 ({len(self.group_blacklist)}/{self.config['max_blacklist_size']}):\n{blacklist_str}{more_info}")

    @filter.command("黑名单状态")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def blacklist_status(self, event: AstrMessageEvent):
        '''查看黑名单统计信息'''
        user_count = len(self.user_blacklist)
        group_count = len(self.group_blacklist)
        user_percent = (user_count / self.config["max_blacklist_size"]) * 100
        group_percent = (group_count / self.config["max_blacklist_size"]) * 100
        
        status_msg = (
            "📊 黑名单统计:\n"
            f"• 用户黑名单: {user_count}/{self.config['max_blacklist_size']} ({user_percent:.1f}%)\n"
            f"• 群组黑名单: {group_count}/{self.config['max_blacklist_size']} ({group_percent:.1f}%)\n"
            f"• 拦截功能: {'✅ 已启用' if self.config['enable_interception'] else '❌ 已禁用'}\n"
            f"• 拦截通知: {'✅ 开启' if self.config['notify_on_intercept'] else '❌ 关闭'}"
        )
        yield event.plain_result(status_msg)

    # 配置管理命令
    @filter.command_group("黑名单配置")
    @filter.permission_type(filter.PermissionType.ADMIN)
    def config_group(self):
        '''黑名单插件配置管理'''
        pass

    @config_group.command("查看")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def config_show(self, event: AstrMessageEvent):
        '''查看当前配置'''
        config_msg = (
            "⚙️ 黑名单插件配置:\n"
            f"• 拦截功能: {'✅ 启用' if self.config['enable_interception'] else '❌ 禁用'}\n"
            f"• 拦截通知: {'✅ 开启' if self.config['notify_on_intercept'] else '❌ 关闭'}\n"
            f"• 自动保存: {f'{self.config["auto_save_interval"]}秒' if self.config['auto_save_interval'] > 0 else '❌ 禁用'}\n"
            f"• 最大数量: {self.config['max_blacklist_size']}\n"
            f"• 拦截消息: {self.config['intercept_message']}"
        )
        yield event.plain_result(config_msg)

    @config_group.command("开关拦截")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def toggle_interception(self, event: AstrMessageEvent):
        '''开启/关闭黑名单拦截功能'''
        self.config["enable_interception"] = not self.config["enable_interception"]
        self.save_config()
        status = "启用" if self.config["enable_interception"] else "禁用"
        yield event.plain_result(f"✅ 已{status}黑名单拦截功能")

    @config_group.command("开关通知")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def toggle_notify(self, event: AstrMessageEvent):
        '''开启/关闭拦截通知'''
        self.config["notify_on_intercept"] = not self.config["notify_on_intercept"]
        self.save_config()
        status = "开启" if self.config["notify_on_intercept"] else "关闭"
        yield event.plain_result(f"✅ 已{status}拦截通知")

    @config_group.command("设置最大数量")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_max_size(self, event: AstrMessageEvent, size: str):
        '''设置黑名单最大数量
        
        Args:
            size(string): 最大数量
        '''
        if not size.isdigit():
            yield event.plain_result("❌ 数量必须为正整数")
            return
            
        new_size = int(size)
        if new_size < 1:
            yield event.plain_result("❌ 数量必须大于0")
            return
            
        self.config["max_blacklist_size"] = new_size
        self.save_config()
        yield event.plain_result(f"✅ 已设置黑名单最大数量为 {new_size}")

    @config_group.command("设置拦截消息")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_intercept_message(self, event: AstrMessageEvent, *, message: str):
        '''设置拦截时发送的消息
        
        Args:
            message(string): 拦截消息内容
        '''
        if not message.strip():
            yield event.plain_result("❌ 消息内容不能为空")
            return
            
        self.config["intercept_message"] = message.strip()
        self.save_config()
        yield event.plain_result(f"✅ 已设置拦截消息为: {message}")

    @config_group.command("重置配置")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reset_config(self, event: AstrMessageEvent):
        '''恢复默认配置'''
        default_config = {
            "enable_interception": True,
            "notify_on_intercept": True,
            "auto_save_interval": 300,
            "max_blacklist_size": 1000,
            "intercept_message": "❌ 您已被加入黑名单，消息无法送达",
            "admin_roles": ["ADMIN"]
        }
        self.config = default_config
        self.save_config()
        yield event.plain_result("✅ 已恢复默认配置")

    # 黑名单检查 - 拦截黑名单用户或群组的消息
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def check_blacklist(self, event: AstrMessageEvent):
        '''检查消息是否来自黑名单用户或群组'''
        # 检查是否启用拦截功能
        if not self.config["enable_interception"]:
            return
            
        sender_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        # 检查用户是否在黑名单中
        if sender_id in self.user_blacklist:
            logger.info(f"拦截黑名单用户 {sender_id} 的消息")
            
            # 如果启用了拦截通知，发送提示消息
            if self.config["notify_on_intercept"] and self.config["intercept_message"]:
                try:
                    yield event.plain_result(self.config["intercept_message"])
                except Exception as e:
                    logger.error(f"发送拦截通知失败: {e}")
            
            event.stop_event()  # 停止事件传播
            return
        
        # 检查群组是否在黑名单中（如果是群消息）
        if group_id and group_id in self.group_blacklist:
            logger.info(f"拦截黑名单群组 {group_id} 的消息")
            
            # 如果启用了拦截通知，发送提示消息
            if self.config["notify_on_intercept"] and self.config["intercept_message"]:
                try:
                    yield event.plain_result(self.config["intercept_message"])
                except Exception as e:
                    logger.error(f"发送拦截通知失败: {e}")
            
            event.stop_event()  # 停止事件传播
            return

    async def terminate(self):
        '''插件卸载时保存数据'''
        self.save_blacklist()
        self.save_config()
        logger.info("黑名单管理器已卸载")