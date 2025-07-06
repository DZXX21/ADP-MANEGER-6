#!/usr/bin/env python3
"""
Enhanced Lapsus Database Manager Bot with Complete Service Management
Professional Telegram Bot for Database Analytics and System Service Management

Author: Lapsus Team
Version: 2.1.0 - Complete Edition (Fixed)
License: MIT
"""

import os
import sys
import asyncio
import logging
import subprocess
import psutil
import json
import re
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager
import platform
import schedule
import time
from threading import Thread

import pymysql
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes, 
    Application
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# =====================================
# CONFIGURATION & CONSTANTS
# =====================================

@dataclass
class BotConfig:
    """Bot configuration class"""
    bot_token: str
    secret_token: str
    db_host: str
    db_user: str
    db_password: str
    db_name: str
    db_port: int = 3306
    max_retry_attempts: int = 3
    connection_timeout: int = 30
    log_level: str = "INFO"
    service_check_interval: int = 30
    auto_restart_failed_services: bool = False
    service_notification_enabled: bool = True

class Config:
    """Configuration manager with secure defaults"""
    
    @staticmethod
    def load_from_env() -> BotConfig:
        """Load configuration from environment variables"""
        return BotConfig(
            bot_token=os.getenv("BOT_TOKEN", "8073854606:AAELoXcJd5nU6trI6JCeIALBt1gDFcwyAk8"),
            secret_token=os.getenv("SECRET_TOKEN", "lapsus123"),
            db_host=os.getenv("DB_HOST", "192.168.70.70"),
            db_user=os.getenv("DB_USER", "root"),
            db_password=os.getenv("DB_PASSWORD", "daaqwWdas21as"),
            db_name=os.getenv("DB_NAME", "lapsusacc"),
            db_port=int(os.getenv("DB_PORT", "3306")),
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            connection_timeout=int(os.getenv("CONNECTION_TIMEOUT", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            service_check_interval=int(os.getenv("SERVICE_CHECK_INTERVAL", "30")),
            auto_restart_failed_services=os.getenv("AUTO_RESTART_SERVICES", "false").lower() == "true",
            service_notification_enabled=os.getenv("SERVICE_NOTIFICATIONS", "true").lower() == "true"
        )

# =====================================
# SERVICE MANAGER
# =====================================

@dataclass
class ServiceInfo:
    """Service information dataclass"""
    name: str
    display_name: str
    description: str
    status: str
    active: bool
    enabled: bool
    uptime: Optional[str] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    pid: Optional[int] = None
    last_restart: Optional[datetime] = None

class SystemServiceManager:
    """System service management class"""
    
    def __init__(self):
        self.monitored_services = [
            "flaskapi.service",
            "flaskapp.service", 
            "telegrambot.service",
            "ubu-monitor.service"
        ]
        self.service_display_names = {
            "flaskapi.service": "Flask API",
            "flaskapp.service": "Flask App",
            "telegrambot.service": "Telegram Bot",
            "ubu-monitor.service": "Ubuntu Monitor"
        }
        self.service_descriptions = {
            "flaskapi.service": "REST API Service for data access",
            "flaskapp.service": "Main web application interface",
            "telegrambot.service": "Telegram bot service",
            "ubu-monitor.service": "System monitoring service"
        }
        self.previous_status = {}
    
    async def get_service_status(self, service_name: str) -> ServiceInfo:
        """Get detailed service status"""
        try:
            # Get systemctl status
            result = await asyncio.create_subprocess_exec(
                'systemctl', 'show', service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return ServiceInfo(
                    name=service_name,
                    display_name=self.service_display_names.get(service_name, service_name),
                    description=self.service_descriptions.get(service_name, "Unknown service"),
                    status="not-found",
                    active=False,
                    enabled=False
                )
            
            # Parse systemctl output
            status_data = {}
            for line in stdout.decode().strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    status_data[key] = value
            
            # Get process info if active
            pid = None
            memory_usage = None
            cpu_usage = None
            
            if status_data.get('MainPID', '0') != '0':
                try:
                    pid = int(status_data['MainPID'])
                    process = psutil.Process(pid)
                    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                    cpu_usage = process.cpu_percent()
                except (psutil.NoSuchProcess, ValueError):
                    pass
            
            # Calculate uptime
            uptime = None
            if status_data.get('ActiveEnterTimestamp'):
                try:
                    start_time = datetime.fromtimestamp(int(status_data['ActiveEnterTimestamp']) / 1000000)
                    uptime_delta = datetime.now() - start_time
                    uptime = self._format_uptime(uptime_delta)
                except (ValueError, TypeError):
                    pass
            
            return ServiceInfo(
                name=service_name,
                display_name=self.service_display_names.get(service_name, service_name),
                description=self.service_descriptions.get(service_name, "Unknown service"),
                status=status_data.get('ActiveState', 'unknown'),
                active=status_data.get('ActiveState') == 'active',
                enabled=status_data.get('UnitFileState') == 'enabled',
                uptime=uptime,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                pid=pid
            )
            
        except Exception as e:
            logging.error(f"Error getting service status for {service_name}: {e}")
            return ServiceInfo(
                name=service_name,
                display_name=self.service_display_names.get(service_name, service_name),
                description=self.service_descriptions.get(service_name, "Unknown service"),
                status="error",
                active=False,
                enabled=False
            )
    
    async def get_all_services_status(self) -> List[ServiceInfo]:
        """Get status of all monitored services"""
        tasks = [self.get_service_status(service) for service in self.monitored_services]
        return await asyncio.gather(*tasks)
    
    async def control_service(self, service_name: str, action: str) -> Dict[str, Any]:
        """Control service (start, stop, restart, enable, disable)"""
        if service_name not in self.monitored_services:
            return {"success": False, "message": "Service not in monitored list"}
        
        if action not in ['start', 'stop', 'restart', 'enable', 'disable']:
            return {"success": False, "message": "Invalid action"}
        
        try:
            # Execute systemctl command
            result = await asyncio.create_subprocess_exec(
                'sudo', 'systemctl', action, service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                logging.info(f"Service {service_name} {action} completed successfully")
                return {
                    "success": True, 
                    "message": f"Service {action} completed successfully",
                    "output": stdout.decode().strip()
                }
            else:
                error_msg = stderr.decode().strip()
                logging.error(f"Service {service_name} {action} failed: {error_msg}")
                return {
                    "success": False, 
                    "message": f"Service {action} failed: {error_msg}",
                    "error": error_msg
                }
                
        except Exception as e:
            logging.error(f"Exception during service {action} for {service_name}: {e}")
            return {"success": False, "message": f"Exception: {str(e)}"}
    
    async def get_service_logs(self, service_name: str, lines: int = 20) -> str:
        """Get service logs"""
        try:
            result = await asyncio.create_subprocess_exec(
                'journalctl', '-u', service_name, '-n', str(lines), '--no-pager',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return stdout.decode()
            else:
                return f"Error getting logs: {stderr.decode()}"
                
        except Exception as e:
            return f"Exception getting logs: {str(e)}"
    
    def _format_uptime(self, uptime_delta: timedelta) -> str:
        """Format uptime for display"""
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def detect_status_changes(self, current_services: List[ServiceInfo]) -> List[Dict[str, Any]]:
        """Detect service status changes"""
        changes = []
        
        for service in current_services:
            service_name = service.name
            current_status = service.status
            previous_status = self.previous_status.get(service_name)
            
            if previous_status and previous_status != current_status:
                changes.append({
                    "service": service.display_name,
                    "service_name": service_name,
                    "previous_status": previous_status,
                    "current_status": current_status,
                    "timestamp": datetime.now()
                })
            
            self.previous_status[service_name] = current_status
        
        return changes

# =====================================
# DATABASE MANAGER
# =====================================

class DatabaseManager:
    """Professional database connection and query manager"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self._connection_pool = []
        
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with proper cleanup"""
        connection = None
        try:
            connection = await asyncio.get_event_loop().run_in_executor(
                None, self._create_connection
            )
            yield connection
        except pymysql.Error as e:
            logging.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def _create_connection(self) -> pymysql.Connection:
        """Create new database connection"""
        return pymysql.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            database=self.config.db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=self.config.connection_timeout,
            read_timeout=self.config.connection_timeout,
            write_timeout=self.config.connection_timeout
        )
    
    async def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """Execute database query with error handling and retries"""
        for attempt in range(self.config.max_retry_attempts):
            try:
                async with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(query, params)
                        return cursor.fetchall()
            except pymysql.Error as e:
                logging.error(f"Database query error (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retry_attempts - 1:
                    raise
                await asyncio.sleep(1)
        return None
    
    async def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            async with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result is not None
        except Exception as e:
            logging.error(f"Database connection test failed: {e}")
            return False

# =====================================
# AUTHORIZATION MANAGER
# =====================================

class AuthManager:
    """User authorization and session management"""
    
    def __init__(self):
        self.authorized_users: set = set()
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.admin_users: set = set()
    
    def authorize_user(self, user_id: int, username: str = "Unknown", is_admin: bool = False) -> bool:
        """Authorize user and create session"""
        self.authorized_users.add(user_id)
        if is_admin:
            self.admin_users.add(user_id)
        
        self.user_sessions[user_id] = {
            'username': username,
            'login_time': datetime.now(),
            'last_activity': datetime.now(),
            'command_count': 0,
            'is_admin': is_admin
        }
        logging.info(f"User authorized: {username} (ID: {user_id}) {'[ADMIN]' if is_admin else ''}")
        return True
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_users
    
    def update_activity(self, user_id: int, command: str):
        """Update user activity"""
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['last_activity'] = datetime.now()
            self.user_sessions[user_id]['command_count'] += 1
            logging.debug(f"User {user_id} executed command: {command}")
    
    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user session statistics"""
        return self.user_sessions.get(user_id)
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active user sessions"""
        return [
            {
                'user_id': user_id,
                **session_data
            }
            for user_id, session_data in self.user_sessions.items()
        ]

# =====================================
# MESSAGE FORMATTER
# =====================================

class MessageFormatter:
    """Professional message formatting utilities"""
    
    @staticmethod
    def format_number(number: Union[int, float]) -> str:
        """Format numbers with thousands separators"""
        return f"{number:,}"
    
    @staticmethod
    def format_percentage(value: float, total: float) -> str:
        """Format percentage with 2 decimal places"""
        if total == 0:
            return "0.00%"
        return f"{(value / total * 100):.2f}%"
    
    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime for display"""
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def format_service_status(service: ServiceInfo) -> str:
        """Format service status for display"""
        status_emoji = {
            'active': '🟢',
            'inactive': '🔴', 
            'failed': '❌',
            'activating': '🟡',
            'deactivating': '🟡',
            'not-found': '⚫',
            'error': '💥'
        }
        
        emoji = status_emoji.get(service.status, '❓')
        status_text = f"{emoji} **{service.display_name}**\n"
        status_text += f"   Status: `{service.status}`\n"
        
        if service.uptime:
            status_text += f"   Uptime: `{service.uptime}`\n"
        
        if service.memory_usage:
            status_text += f"   Memory: `{service.memory_usage:.1f} MB`\n"
            
        if service.cpu_usage:
            status_text += f"   CPU: `{service.cpu_usage:.1f}%`\n"
            
        if service.pid:
            status_text += f"   PID: `{service.pid}`\n"
        
        return status_text
    
    @staticmethod
    def get_region_flag(region: str) -> str:
        """Get flag emoji for region"""
        region_flags = {
            'US': '🇺🇸', 'USA': '🇺🇸', 'United States': '🇺🇸',
            'TR': '🇹🇷', 'Turkey': '🇹🇷', 'Türkiye': '🇹🇷',
            'DE': '🇩🇪', 'Germany': '🇩🇪',
            'FR': '🇫🇷', 'France': '🇫🇷',
            'UK': '🇬🇧', 'United Kingdom': '🇬🇧',
            'CN': '🇨🇳', 'China': '🇨🇳',
            'RU': '🇷🇺', 'Russia': '🇷🇺',
            'CA': '🇨🇦', 'Canada': '🇨🇦',
            'AU': '🇦🇺', 'Australia': '🇦🇺',
            'JP': '🇯🇵', 'Japan': '🇯🇵',
            'Unspecified': '🌍'
        }
        return region_flags.get(region, '🌎')
    
    @staticmethod
    def get_domain_emoji(domain: str) -> str:
        """Get emoji for domain type"""
        if not domain:
            return '🌍'
        domain = domain.lower()
        if any(x in domain for x in ['gmail', 'google']):
            return '📧'
        elif any(x in domain for x in ['yahoo', 'ymail']):
            return '💌'
        elif any(x in domain for x in ['outlook', 'hotmail', 'live', 'msn']):
            return '📨'
        elif any(x in domain for x in ['icloud', 'me.com', 'mac.com']):
            return '☁️'
        elif any(x in domain for x in ['protonmail', 'tutanota']):
            return '🔐'
        else:
            return '🌍'

# =====================================
# ENHANCED BOT HANDLER
# =====================================

class LapsusBotHandler:
    """Enhanced bot command handler with complete functionality"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.auth_manager = AuthManager()
        self.formatter = MessageFormatter()
        self.service_manager = SystemServiceManager()
        self.daily_report_enabled = True
        self.report_chat_ids = set()
        self.service_monitor_enabled = True
        self.service_monitor_chats = set()
        self.application = None
    
    async def initialize(self) -> bool:
        """Initialize bot and test connections"""
        logging.info("Initializing Enhanced Lapsus Bot...")
        
        # Validate configuration
        if not self.config.bot_token:
            logging.error("BOT_TOKEN not provided")
            return False
        
        if not self.config.secret_token:
            logging.error("SECRET_TOKEN not provided")
            return False
        
        # Test database connection
        if not await self.db_manager.test_connection():
            logging.error("Database connection failed during initialization")
            return False
        
        logging.info("✅ Database connection successful")
        
        # Initialize service monitoring
        try:
            services = await self.service_manager.get_all_services_status()
            logging.info(f"✅ Service monitoring initialized - {len(services)} services detected")
        except Exception as e:
            logging.warning(f"Service monitoring initialization failed: {e}")
        
        return True
    
    # =====================================
    # AUTHENTICATION COMMANDS
    # =====================================
    
    async def cmd_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User authentication command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name or "Unknown"
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔐 **Authentication Required**\n\n"
                "Usage: `/giris <token>`\n"
                "Please provide your access token.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        provided_token = context.args[0]
        
        if provided_token == self.config.secret_token:
            # Check if user should be admin (first user or specific logic)
            is_admin = len(self.auth_manager.authorized_users) == 0  # First user is admin
            
            self.auth_manager.authorize_user(user_id, username, is_admin)
            
            welcome_msg = (
                "✅ **Authentication Successful!**\n\n"
                f"Welcome, **{username}**!\n"
                f"Login time: `{self.formatter.format_datetime(datetime.now())}`\n"
                f"Access level: `{'Admin' if is_admin else 'User'}`\n\n"
                "🎯 You can now access all bot commands.\n"
                "📋 Type `/help` to see available commands."
            )
            
            await update.message.reply_text(welcome_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            logging.warning(f"Failed login attempt: {username} (ID: {user_id})")
            await update.message.reply_text(
                "❌ **Authentication Failed**\n\n"
                "Invalid access token provided.\n"
                "Please contact administrator for valid token.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def _check_auth(self, user_id: int) -> bool:
        """Check user authorization"""
        return self.auth_manager.is_authorized(user_id)
    
    def _check_admin(self, user_id: int) -> bool:
        """Check admin authorization"""
        return self.auth_manager.is_admin(user_id)
    
    async def _unauthorized_response(self, update: Update):
        """Send unauthorized access message"""
        await update.message.reply_text(
            "🚫 **Access Denied**\n\n"
            "Please authenticate first using:\n"
            "`/giris <your_token>`\n\n"
            "Contact administrator if you need access.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def _admin_only_response(self, update: Update):
        """Send admin only access message"""
        await update.message.reply_text(
            "🔒 **Admin Access Required**\n\n"
            "This command requires administrator privileges.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def _track_command_usage(self, update: Update, command: str):
        """Track command usage for analytics"""
        user_id = update.effective_user.id
        self.auth_manager.update_activity(user_id, command)
    
    # =====================================
    # DATABASE COMMANDS
    # =====================================
    
    async def cmd_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced database statistics"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "statistics")
        
        try:
            loading_msg = await update.message.reply_text(
                "📊 **Loading statistics...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Multiple queries for comprehensive stats
            queries = {
                'total': "SELECT COUNT(*) as total FROM accs",
                'today': "SELECT COUNT(*) as today_total FROM accs WHERE DATE(date) = CURDATE()",
                'week': "SELECT COUNT(*) as week_total FROM accs WHERE DATE(date) >= CURDATE() - INTERVAL 7 DAY",
                'month': "SELECT COUNT(*) as month_total FROM accs WHERE DATE(date) >= CURDATE() - INTERVAL 30 DAY",
                'regions': "SELECT COUNT(DISTINCT region) as region_count FROM accs WHERE region IS NOT NULL",
                'domains': "SELECT COUNT(DISTINCT domain) as domain_count FROM accs WHERE domain IS NOT NULL"
            }
            
            results = {}
            for key, query in queries.items():
                result = await self.db_manager.execute_query(query)
                results[key] = result[0] if result else {f"{key}_total" if key != 'total' else key: 0}
            
            # Calculate growth rates
            yesterday_query = "SELECT COUNT(*) as yesterday_total FROM accs WHERE DATE(date) = CURDATE() - INTERVAL 1 DAY"
            yesterday_result = await self.db_manager.execute_query(yesterday_query)
            yesterday_count = yesterday_result[0]['yesterday_total'] if yesterday_result else 0
            
            today_count = results['today']['today_total']
            growth_rate = ((today_count - yesterday_count) / max(yesterday_count, 1)) * 100
            
            stats_msg = f"""
📊 **Comprehensive Database Analytics**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **Record Statistics:**
• Total Records: **{self.formatter.format_number(results['total']['total'])}**
• Today: **{self.formatter.format_number(today_count)}** ({growth_rate:+.1f}% vs yesterday)
• This Week: **{self.formatter.format_number(results['week']['week_total'])}**
• This Month: **{self.formatter.format_number(results['month']['month_total'])}**

🌍 **Diversity Metrics:**
• Unique Regions: **{results['regions']['region_count']}**
• Unique Domains: **{results['domains']['domain_count']}**

🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Use other commands for detailed analysis:
• `/bolgeler` - Regional distribution
• `/enpopulerdomain` - Popular domains
• `/son7gun` - Weekly trend analysis
            """
            
            await loading_msg.delete()
            await update.message.reply_text(stats_msg, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Statistics command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve statistics. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_regions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Regional distribution analysis with enhanced visualization"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "regions")
        
        try:
            loading_msg = await update.message.reply_text(
                "🌍 **Loading regional analysis...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            query = """
                SELECT 
                    COALESCE(NULLIF(region, ''), 'Unspecified') as region, 
                    COUNT(*) AS count,
                    ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accs)), 2) as percentage
                FROM accs 
                GROUP BY region 
                ORDER BY count DESC 
                LIMIT 15
            """
            
            result = await self.db_manager.execute_query(query)
            
            if not result:
                await loading_msg.delete()
                await update.message.reply_text(
                    "🌍 **Regional Analysis**\n\nNo regional data found.", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            total_records = sum(row['count'] for row in result)
            
            regions_text = "🌍 **Regional Distribution Analysis**\n\n"
            regions_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, row in enumerate(result, 1):
                region = row['region']
                count = row['count']
                percentage = row['percentage']
                flag = self.formatter.get_region_flag(region)
                
                # Create visual bar
                bar_length = int((count / result[0]['count']) * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                
                regions_text += f"{i:2d}. {flag} **{region}**\n"
                regions_text += f"    `{bar}` {self.formatter.format_number(count)} ({percentage}%)\n\n"
            
            regions_text += f"📊 **Total Analyzed:** {self.formatter.format_number(total_records)}\n"
            regions_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await loading_msg.delete()
            await update.message.reply_text(regions_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Regions command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve regional data.", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_popular_domains(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Most popular domains analysis"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "popular_domains")
        
        try:
            loading_msg = await update.message.reply_text(
                "📧 **Loading domain analysis...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            query = """
                SELECT 
                    domain, 
                    COUNT(*) AS count,
                    ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accs WHERE domain IS NOT NULL AND domain != '')), 2) as percentage
                FROM accs 
                WHERE domain IS NOT NULL AND domain != ''
                GROUP BY domain 
                ORDER BY count DESC 
                LIMIT 15
            """
            
            result = await self.db_manager.execute_query(query)
            
            if not result:
                await loading_msg.delete()
                await update.message.reply_text(
                    "📧 **Domain Analysis**\n\nNo domain data found.", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            total_domains = sum(row['count'] for row in result)
            
            domains_text = "📧 **Popular Email Domains Analysis**\n\n"
            domains_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, row in enumerate(result, 1):
                domain = row['domain']
                count = row['count']
                percentage = row['percentage']
                emoji = self.formatter.get_domain_emoji(domain)
                
                # Create visual bar
                bar_length = int((count / result[0]['count']) * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                
                domains_text += f"{i:2d}. {emoji} **{domain}**\n"
                domains_text += f"    `{bar}` {self.formatter.format_number(count)} ({percentage}%)\n\n"
            
            domains_text += f"📊 **Total Analyzed:** {self.formatter.format_number(total_domains)}\n"
            domains_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await loading_msg.delete()
            await update.message.reply_text(domains_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Popular domains command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve domain data.", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_last_7_days(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Last 7 days activity analysis"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "last_7_days")
        
        try:
            loading_msg = await update.message.reply_text(
                "📈 **Loading 7-day trend analysis...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            query = """
                SELECT 
                    DATE(date) as day,
                    COUNT(*) as count,
                    DAYNAME(date) as day_name
                FROM accs 
                WHERE DATE(date) >= CURDATE() - INTERVAL 7 DAY
                GROUP BY DATE(date), DAYNAME(date)
                ORDER BY day DESC
            """
            
            result = await self.db_manager.execute_query(query)
            
            if not result:
                await loading_msg.delete()
                await update.message.reply_text(
                    "📈 **7-Day Analysis**\n\nNo data found for the last 7 days.", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            total_week = sum(row['count'] for row in result)
            avg_daily = total_week / len(result) if result else 0
            max_count = max(row['count'] for row in result) if result else 0
            
            trend_text = "📈 **Last 7 Days Activity Analysis**\n\n"
            trend_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, row in enumerate(reversed(result), 1):  # Show oldest to newest
                day = row['day']
                count = row['count']
                day_name = row['day_name']
                
                # Create visual bar
                bar_length = int((count / max_count) * 15) if max_count > 0 else 0
                bar = "█" * bar_length + "░" * (15 - bar_length)
                
                # Trend indicator
                if count > avg_daily * 1.2:
                    trend = "📈"
                elif count < avg_daily * 0.8:
                    trend = "📉"
                else:
                    trend = "➡️"
                
                trend_text += f"**{day}** ({day_name[:3]})\n"
                trend_text += f"{trend} `{bar}` **{self.formatter.format_number(count)}**\n\n"
            
            trend_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            trend_text += f"📊 **Week Total:** {self.formatter.format_number(total_week)}\n"
            trend_text += f"📊 **Daily Average:** {self.formatter.format_number(int(avg_daily))}\n"
            trend_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await loading_msg.delete()
            await update.message.reply_text(trend_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Last 7 days command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve 7-day data.", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Source-based categorization analysis"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "sources")
        
        try:
            loading_msg = await update.message.reply_text(
                "🔗 **Loading source analysis...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            query = """
                SELECT 
                    COALESCE(NULLIF(source, ''), 'Unspecified') as source,
                    COUNT(*) as count,
                    ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM accs)), 2) as percentage
                FROM accs 
                GROUP BY source 
                ORDER BY count DESC 
                LIMIT 10
            """
            
            result = await self.db_manager.execute_query(query)
            
            if not result:
                await loading_msg.delete()
                await update.message.reply_text(
                    "🔗 **Source Analysis**\n\nNo source data found.", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            total_sources = sum(row['count'] for row in result)
            
            sources_text = "🔗 **Data Source Analysis**\n\n"
            sources_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            source_emojis = {
                'api': '🔌', 'import': '📦', 'manual': '👤', 'auto': '🤖',
                'web': '🌐', 'form': '📝', 'migration': '🔄', 'unspecified': '❓'
            }
            
            for i, row in enumerate(result, 1):
                source = row['source']
                count = row['count']
                percentage = row['percentage']
                
                # Get appropriate emoji
                emoji = '📂'
                for key, emoji_val in source_emojis.items():
                    if key.lower() in source.lower():
                        emoji = emoji_val
                        break
                
                # Create visual bar
                bar_length = int((count / result[0]['count']) * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                
                sources_text += f"{i:2d}. {emoji} **{source}**\n"
                sources_text += f"    `{bar}` {self.formatter.format_number(count)} ({percentage}%)\n\n"
            
            sources_text += f"📊 **Total Analyzed:** {self.formatter.format_number(total_sources)}\n"
            sources_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await loading_msg.delete()
            await update.message.reply_text(sources_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Sources command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve source data.", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_search_spid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search by specific SPID"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "search_spid")
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **SPID Search**\n\n"
                "Usage: `/spidsorgu <spid>`\n"
                "Example: `/spidsorgu 12345`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            spid = context.args[0]
            
            # Validate SPID (should be numeric)
            if not spid.isdigit():
                await update.message.reply_text(
                    "❌ **Invalid SPID**\n\nSPID must be a number.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            loading_msg = await update.message.reply_text(
                f"🔍 **Searching for SPID: {spid}...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            query = "SELECT * FROM accs WHERE id = %s"
            result = await self.db_manager.execute_query(query, (spid,))
            
            await loading_msg.delete()
            
            if not result:
                await update.message.reply_text(
                    f"❌ **SPID Not Found**\n\nNo record found with SPID: `{spid}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            record = result[0]
            
            # Format the record information
            record_text = f"🔍 **SPID Search Result**\n\n"
            record_text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            record_text += f"🆔 **SPID:** `{record.get('id', 'N/A')}`\n"
            record_text += f"📧 **Email:** `{record.get('email', 'N/A')}`\n"
            record_text += f"🔑 **Password:** `{record.get('password', 'N/A')}`\n"
            record_text += f"🌍 **Domain:** `{record.get('domain', 'N/A')}`\n"
            record_text += f"🌎 **Region:** `{record.get('region', 'N/A')}`\n"
            record_text += f"🔗 **Source:** `{record.get('source', 'N/A')}`\n"
            record_text += f"📅 **Date:** `{record.get('date', 'N/A')}`\n"
            record_text += f"\n🕒 **Retrieved:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await update.message.reply_text(record_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"SPID search command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to search SPID. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_search_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Domain keyword search"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "search_keyword")
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **Keyword Search**\n\n"
                "Usage: `/ara <keyword>`\n"
                "Example: `/ara gmail`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            keyword = context.args[0].lower()
            
            # Validate keyword
            if len(keyword) < 2:
                await update.message.reply_text(
                    "❌ **Invalid Keyword**\n\nKeyword must be at least 2 characters long.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            loading_msg = await update.message.reply_text(
                f"🔍 **Searching for keyword: {keyword}...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Search in domain and email fields
            query = """
                SELECT domain, COUNT(*) as count 
                FROM accs 
                WHERE (LOWER(domain) LIKE %s OR LOWER(email) LIKE %s) 
                AND domain IS NOT NULL AND domain != ''
                GROUP BY domain 
                ORDER BY count DESC 
                LIMIT 10
            """
            
            search_term = f"%{keyword}%"
            result = await self.db_manager.execute_query(query, (search_term, search_term))
            
            await loading_msg.delete()
            
            if not result:
                await update.message.reply_text(
                    f"❌ **No Results**\n\nNo domains found containing: `{keyword}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            total_matches = sum(row['count'] for row in result)
            
            search_text = f"🔍 **Search Results for: `{keyword}`**\n\n"
            search_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, row in enumerate(result, 1):
                domain = row['domain']
                count = row['count']
                emoji = self.formatter.get_domain_emoji(domain)
                
                search_text += f"{i:2d}. {emoji} **{domain}**\n"
                search_text += f"    📊 {self.formatter.format_number(count)} records\n\n"
            
            search_text += f"📊 **Total Matches:** {self.formatter.format_number(total_matches)}\n"
            search_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await update.message.reply_text(search_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Keyword search command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to perform search. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_date_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Date-based queries"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "date_query")
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "📅 **Date Query**\n\n"
                "Usage: `/tarihsorgu <YYYY-MM-DD>`\n"
                "Example: `/tarihsorgu 2023-12-25`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            date_str = context.args[0]
            
            # Validate date format
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                await update.message.reply_text(
                    "❌ **Invalid Date Format**\n\nUse format: YYYY-MM-DD\nExample: 2023-12-25",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            loading_msg = await update.message.reply_text(
                f"📅 **Querying data for: {date_str}...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Get records for specific date
            queries = {
                'total': "SELECT COUNT(*) as count FROM accs WHERE DATE(date) = %s",
                'domains': """
                    SELECT domain, COUNT(*) as count 
                    FROM accs 
                    WHERE DATE(date) = %s AND domain IS NOT NULL AND domain != ''
                    GROUP BY domain 
                    ORDER BY count DESC 
                    LIMIT 5
                """,
                'regions': """
                    SELECT region, COUNT(*) as count 
                    FROM accs 
                    WHERE DATE(date) = %s AND region IS NOT NULL AND region != ''
                    GROUP BY region 
                    ORDER BY count DESC 
                    LIMIT 5
                """,
                'hourly': """
                    SELECT HOUR(date) as hour, COUNT(*) as count 
                    FROM accs 
                    WHERE DATE(date) = %s
                    GROUP BY HOUR(date)
                    ORDER BY hour
                """
            }
            
            results = {}
            for key, query in queries.items():
                result = await self.db_manager.execute_query(query, (date_str,))
                results[key] = result if result else []
            
            await loading_msg.delete()
            
            total_count = results['total'][0]['count'] if results['total'] else 0
            
            if total_count == 0:
                await update.message.reply_text(
                    f"📅 **No Data Found**\n\nNo records found for date: `{date_str}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            date_text = f"📅 **Date Query Results: {date_str}**\n\n"
            date_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            date_text += f"📊 **Total Records:** {self.formatter.format_number(total_count)}\n\n"
            
            # Top domains for the date
            if results['domains']:
                date_text += "🌐 **Top Domains:**\n"
                for i, row in enumerate(results['domains'], 1):
                    emoji = self.formatter.get_domain_emoji(row['domain'])
                    date_text += f"{i}. {emoji} {row['domain']}: {row['count']}\n"
                date_text += "\n"
            
            # Top regions for the date
            if results['regions']:
                date_text += "🌍 **Top Regions:**\n"
                for i, row in enumerate(results['regions'], 1):
                    flag = self.formatter.get_region_flag(row['region'])
                    date_text += f"{i}. {flag} {row['region']}: {row['count']}\n"
                date_text += "\n"
            
            # Hourly distribution
            if results['hourly']:
                peak_hour = max(results['hourly'], key=lambda x: x['count'])
                date_text += f"⏰ **Peak Activity:** {peak_hour['hour']:02d}:00 ({peak_hour['count']} records)\n\n"
            
            date_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await update.message.reply_text(date_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Date query command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to query date. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_domain_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Exact domain match control"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "domain_control")
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🌐 **Domain Control**\n\n"
                "Usage: `/domainkontrol <domain>`\n"
                "Example: `/domainkontrol gmail.com`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            domain = context.args[0].lower()
            
            loading_msg = await update.message.reply_text(
                f"🌐 **Checking domain: {domain}...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Get detailed domain information
            queries = {
                'total': "SELECT COUNT(*) as count FROM accs WHERE LOWER(domain) = %s",
                'recent': """
                    SELECT COUNT(*) as count 
                    FROM accs 
                    WHERE LOWER(domain) = %s AND DATE(date) >= CURDATE() - INTERVAL 7 DAY
                """,
                'regions': """
                    SELECT region, COUNT(*) as count 
                    FROM accs 
                    WHERE LOWER(domain) = %s AND region IS NOT NULL AND region != ''
                    GROUP BY region 
                    ORDER BY count DESC 
                    LIMIT 5
                """,
                'first_seen': """
                    SELECT MIN(date) as first_date 
                    FROM accs 
                    WHERE LOWER(domain) = %s
                """,
                'last_seen': """
                    SELECT MAX(date) as last_date 
                    FROM accs 
                    WHERE LOWER(domain) = %s
                """
            }
            
            results = {}
            for key, query in queries.items():
                result = await self.db_manager.execute_query(query, (domain,))
                results[key] = result[0] if result else {}
            
            await loading_msg.delete()
            
            total_count = results['total'].get('count', 0)
            
            if total_count == 0:
                await update.message.reply_text(
                    f"🌐 **Domain Not Found**\n\nNo records found for domain: `{domain}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            recent_count = results['recent'].get('count', 0)
            first_seen = results['first_seen'].get('first_date')
            last_seen = results['last_seen'].get('last_date')
            
            domain_text = f"🌐 **Domain Analysis: {domain}**\n\n"
            domain_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            domain_text += f"📊 **Total Records:** {self.formatter.format_number(total_count)}\n"
            domain_text += f"🔄 **Recent (7 days):** {self.formatter.format_number(recent_count)}\n"
            
            if first_seen:
                domain_text += f"👀 **First Seen:** `{first_seen}`\n"
            if last_seen:
                domain_text += f"👁️ **Last Seen:** `{last_seen}`\n"
            
            # Regional distribution
            if results['regions']:
                domain_text += "\n🌍 **Regional Distribution:**\n"
                for row in results['regions']:
                    flag = self.formatter.get_region_flag(row['region'])
                    percentage = (row['count'] / total_count) * 100
                    domain_text += f"{flag} {row['region']}: {row['count']} ({percentage:.1f}%)\n"
            
            domain_text += f"\n🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await update.message.reply_text(domain_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Domain control command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to check domain. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # =====================================
    # SERVICE MANAGEMENT COMMANDS
    # =====================================
    
    async def cmd_services(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all services status with interactive controls"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "services")
        
        try:
            loading_msg = await update.message.reply_text(
                "🔄 **Loading service status...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            services = await self.service_manager.get_all_services_status()
            
            services_text = "🛠️ **System Services Status**\n\n"
            services_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for service in services:
                services_text += self.formatter.format_service_status(service) + "\n"
            
            # Add system resources
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                services_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                services_text += "💻 **System Resources:**\n"
                services_text += f"   CPU: `{cpu_percent:.1f}%`\n"
                services_text += f"   Memory: `{memory.percent:.1f}%` ({memory.used // 1024 // 1024} MB / {memory.total // 1024 // 1024} MB)\n"
                services_text += f"   Disk: `{disk.percent:.1f}%` ({disk.used // 1024 // 1024 // 1024} GB / {disk.total // 1024 // 1024 // 1024} GB)\n"
            except Exception as e:
                logging.error(f"Error getting system resources: {e}")
            
            services_text += f"\n🕒 **Last Updated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            # Create inline keyboard for service actions
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="services_refresh"),
                    InlineKeyboardButton("🎛️ Control Panel", callback_data="services_control")
                ],
                [
                    InlineKeyboardButton("📊 Detailed View", callback_data="services_detailed"),
                    InlineKeyboardButton("📋 Logs", callback_data="services_logs")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.delete()
            await update.message.reply_text(
                services_text, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"Services command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve services status.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_service_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Service control command (admin only)"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        if not self._check_admin(update.effective_user.id):
            return await self._admin_only_response(update)
        
        await self._track_command_usage(update, "service_control")
        
        if len(context.args) < 2:
            # Show service control menu
            keyboard = []
            for service in self.service_manager.monitored_services:
                service_name = self.service_manager.service_display_names.get(service, service)
                keyboard.append([
                    InlineKeyboardButton(
                        f"🎛️ {service_name}", 
                        callback_data=f"control_{service}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎛️ **Service Control Panel** (Admin Only)\n\n"
                "Select a service to control:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        # Direct service control
        action = context.args[0].lower()
        service_name = context.args[1]
        
        if action not in ['start', 'stop', 'restart', 'enable', 'disable']:
            await update.message.reply_text(
                "❌ **Invalid Action**\n\n"
                "Valid actions: start, stop, restart, enable, disable\n"
                "Usage: `/servisyonet <action> <service_name>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if service_name not in self.service_manager.monitored_services:
            await update.message.reply_text(
                "❌ **Service Not Found**\n\n"
                f"Available services: {', '.join(self.service_manager.monitored_services)}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Execute service control
        loading_msg = await update.message.reply_text(
            f"🔄 **{action.title()}ing {service_name}...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        result = await self.service_manager.control_service(service_name, action)
        
        await loading_msg.delete()
        
        if result["success"]:
            await update.message.reply_text(
                f"✅ **Service {action.title()} Successful**\n\n"
                f"Service: `{service_name}`\n"
                f"Action: `{action}`\n"
                f"Result: {result['message']}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ **Service {action.title()} Failed**\n\n"
                f"Service: `{service_name}`\n"
                f"Action: `{action}`\n"
                f"Error: {result['message']}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_service_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get service logs"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "service_logs")
        
        if len(context.args) == 0:
            # Show service selection
            keyboard = []
            for service in self.service_manager.monitored_services:
                service_name = self.service_manager.service_display_names.get(service, service)
                keyboard.append([
                    InlineKeyboardButton(
                        f"📋 {service_name}", 
                        callback_data=f"logs_{service}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📋 **Service Logs**\n\n"
                "Select a service to view logs:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        service_name = context.args[0]
        lines = int(context.args[1]) if len(context.args) > 1 else 20
        
        if service_name not in self.service_manager.monitored_services:
            await update.message.reply_text(
                "❌ **Service Not Found**\n\n"
                f"Available services: {', '.join(self.service_manager.monitored_services)}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        loading_msg = await update.message.reply_text(
            f"📋 **Loading logs for {service_name}...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logs = await self.service_manager.get_service_logs(service_name, lines)
        
        await loading_msg.delete()
        
        # Split logs if too long
        if len(logs) > 4000:
            logs = logs[-4000:]
            logs = "...(truncated)\n" + logs
        
        await update.message.reply_text(
            f"📋 **Logs for {service_name}** (last {lines} lines)\n\n"
            f"```\n{logs}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cmd_service_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle service monitoring for this chat"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "service_monitor")
        
        chat_id = update.effective_chat.id
        
        if chat_id in self.service_monitor_chats:
            self.service_monitor_chats.remove(chat_id)
            await update.message.reply_text(
                "🔕 **Service Monitoring Disabled**\n\n"
                "This chat will no longer receive service status notifications.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            self.service_monitor_chats.add(chat_id)
            await update.message.reply_text(
                "🔔 **Service Monitoring Enabled**\n\n"
                "This chat will now receive notifications when service status changes.\n\n"
                "Use `/servisizleme` again to disable.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # =====================================
    # DAILY REPORT SYSTEM
    # =====================================
    
    async def generate_daily_report(self) -> str:
        """Generate comprehensive daily report"""
        try:
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            
            # Get daily statistics
            daily_query = "SELECT COUNT(*) as daily_count FROM accs WHERE DATE(date) = %s"
            daily_result = await self.db_manager.execute_query(daily_query, (yesterday_str,))
            daily_count = daily_result[0]['daily_count'] if daily_result else 0
            
            # Get regional distribution
            regions_query = """
                SELECT 
                    COALESCE(region, 'Unspecified') as region, 
                    COUNT(*) as count,
                    ROUND((COUNT(*) * 100.0 / %s), 2) as percentage
                FROM accs 
                WHERE DATE(date) = %s
                GROUP BY region 
                ORDER BY count DESC 
                LIMIT 10
            """
            regions_result = await self.db_manager.execute_query(regions_query, (max(daily_count, 1), yesterday_str))
            
            # Get domain distribution
            domains_query = """
                SELECT 
                    domain, 
                    COUNT(*) as count,
                    ROUND((COUNT(*) * 100.0 / %s), 2) as percentage
                FROM accs 
                WHERE DATE(date) = %s AND domain IS NOT NULL AND domain != ''
                GROUP BY domain 
                ORDER BY count DESC 
                LIMIT 10
            """
            domains_result = await self.db_manager.execute_query(domains_query, (max(daily_count, 1), yesterday_str))
            
            # Get hourly distribution
            hourly_query = """
                SELECT 
                    HOUR(date) as hour,
                    COUNT(*) as count
                FROM accs 
                WHERE DATE(date) = %s
                GROUP BY HOUR(date)
                ORDER BY hour
            """
            hourly_result = await self.db_manager.execute_query(hourly_query, (yesterday_str,))
            
            # Get total statistics
            total_query = "SELECT COUNT(*) as total FROM accs"
            total_result = await self.db_manager.execute_query(total_query)
            total_count = total_result[0]['total'] if total_result else 0
            
            # Get week comparison
            week_comparison_query = """
                SELECT 
                    DATE(date) as date,
                    COUNT(*) as count
                FROM accs 
                WHERE DATE(date) >= %s - INTERVAL 6 DAY AND DATE(date) <= %s
                GROUP BY DATE(date)
                ORDER BY date DESC
            """
            week_result = await self.db_manager.execute_query(week_comparison_query, (yesterday_str, yesterday_str))
            
            # Generate report
            report = f"""
📊 **GÜNLÜK RAPOR - {yesterday_str}**
📅 **{yesterday.strftime('%A, %d %B %Y')}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **GENEL İSTATİSTİKLER:**
• Dün Eklenen: **{self.formatter.format_number(daily_count)}**
• Toplam Kayıt: **{self.formatter.format_number(total_count)}**
• Günlük Oran: **{self.formatter.format_percentage(daily_count, total_count)}**

"""
            
            if daily_count > 0:
                # Regional distribution
                if regions_result:
                    report += "🌍 **BÖLGESEL DAĞILIM:**\n"
                    for i, row in enumerate(regions_result[:5], 1):
                        region_flag = self.formatter.get_region_flag(row['region'])
                        report += f"{i}. {region_flag} **{row['region']}**: {self.formatter.format_number(row['count'])} ({row['percentage']}%)\n"
                    report += "\n"
                
                # Domain distribution
                if domains_result:
                    report += "🌐 **POPÜLER DOMAINLER:**\n"
                    for i, row in enumerate(domains_result[:5], 1):
                        domain_emoji = self.formatter.get_domain_emoji(row['domain'])
                        report += f"{i}. {domain_emoji} **{row['domain']}**: {self.formatter.format_number(row['count'])} ({row['percentage']}%)\n"
                    report += "\n"
                
                # Peak hours
                if hourly_result:
                    peak_hours = sorted(hourly_result, key=lambda x: x['count'], reverse=True)[:3]
                    if peak_hours:
                        report += "⏰ **EN AKTİF SAATLER:**\n"
                        for i, hour_data in enumerate(peak_hours, 1):
                            hour = hour_data['hour']
                            count = hour_data['count']
                            percentage = self.formatter.format_percentage(count, daily_count)
                            report += f"{i}. **{hour:02d}:00-{hour+1:02d}:00**: {self.formatter.format_number(count)} ({percentage})\n"
                        report += "\n"
            
            # Weekly trend
            if week_result and len(week_result) > 1:
                report += "📊 **7 GÜNLÜK TREND:**\n"
                week_total = sum(row['count'] for row in week_result)
                week_avg = week_total / len(week_result)
                
                for row in week_result:
                    date = row['date']
                    count = row['count']
                    day_name = date.strftime("%a")
                    
                    # Trend indicator
                    if count > week_avg * 1.2:
                        trend = "📈"
                    elif count < week_avg * 0.8:
                        trend = "📉"
                    else:
                        trend = "➡️"
                    
                    report += f"• {date} ({day_name}): {trend} **{self.formatter.format_number(count)}**\n"
                
                report += f"\nHaftalık Ortalama: **{self.formatter.format_number(int(week_avg))}**\n"
            
            # Performance assessment
            report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            if daily_count == 0:
                report += "⚠️ **UYARI**: Dün hiç kayıt eklenmedi!\n"
            elif week_result:
                week_avg = sum(row['count'] for row in week_result) / len(week_result)
                if daily_count > week_avg * 1.5:
                    report += "🚀 **MÜKEMMEL**: Haftalık ortalamanın üzerinde!\n"
                elif daily_count > week_avg:
                    report += "✅ **İYİ**: Ortalamanın üzerinde performans\n"
                elif daily_count < week_avg * 0.5:
                    report += "🔴 **DİKKAT**: Ortalamanın çok altında!\n"
                else:
                    report += "⚡ **NORMAL**: Haftalık ortalama seviyesinde\n"
            
            report += f"\n🕒 **Rapor Zamanı**: {self.formatter.format_datetime(datetime.now())}\n"
            report += "🤖 **Enhanced Lapsus Database Manager v2.1.0**"
            
            return report
            
        except Exception as e:
            logging.error(f"Daily report generation error: {e}")
            return f"❌ **Günlük Rapor Hatası**\n\nRapor oluşturulurken hata oluştu: {str(e)}"
    
    async def cmd_daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual daily report command"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "daily_report")
        
        try:
            loading_msg = await update.message.reply_text(
                "📊 **Günlük rapor hazırlanıyor...**", 
                parse_mode=ParseMode.MARKDOWN
            )
            
            report = await self.generate_daily_report()
            
            await loading_msg.delete()
            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Manual daily report error: {e}")
            await update.message.reply_text(
                "❌ **Hata**\n\nGünlük rapor oluşturulurken hata oluştu.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_report_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Subscribe to daily reports"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "report_subscribe")
        
        chat_id = update.effective_chat.id
        
        if chat_id in self.report_chat_ids:
            await update.message.reply_text(
                "✅ **Zaten Abonesinsiz**\n\nBu chat zaten günlük rapora abone.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            self.report_chat_ids.add(chat_id)
            await update.message.reply_text(
                "📔 **Abonelik Başarılı!**\n\n"
                "Bu chat artık her gece saat 00:00'da günlük rapor alacak.\n\n"
                "📋 Abonelikten çıkmak için: `/raporiptal`",
                parse_mode=ParseMode.MARKDOWN
            )
            logging.info(f"Chat {chat_id} subscribed to daily reports")
    
    async def cmd_report_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unsubscribe from daily reports"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "report_unsubscribe")
        
        chat_id = update.effective_chat.id
        
        if chat_id in self.report_chat_ids:
            self.report_chat_ids.remove(chat_id)
            await update.message.reply_text(
                "📕 **Abonelik İptal Edildi**\n\nBu chat artık günlük rapor almayacak.",
                parse_mode=ParseMode.MARKDOWN
            )
            logging.info(f"Chat {chat_id} unsubscribed from daily reports")
        else:
            await update.message.reply_text(
                "ℹ️ **Zaten Abone Değilsiniz**\n\nBu chat günlük rapora abone değil.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # =====================================
    # DEBUG AND ADMIN COMMANDS
    # =====================================
    
    async def cmd_debug(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """System diagnostics and data analysis"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "debug")
        
        try:
            loading_msg = await update.message.reply_text(
                "🔧 **Running system diagnostics...**",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Database diagnostics
            db_status = "✅ Connected" if await self.db_manager.test_connection() else "❌ Disconnected"
            
            # Get database info
            db_queries = {
                'table_count': "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = %s",
                'total_records': "SELECT COUNT(*) as count FROM accs",
                'table_size': "SELECT ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'size_mb' FROM information_schema.tables WHERE table_schema = %s AND table_name = 'accs'"
            }
            
            db_results = {}
            for key, query in db_queries.items():
                try:
                    if key in ['table_count', 'table_size']:
                        result = await self.db_manager.execute_query(query, (self.config.db_name,))
                    else:
                        result = await self.db_manager.execute_query(query)
                    db_results[key] = result[0] if result else {}
                except Exception as e:
                    db_results[key] = {'error': str(e)}
            
            # System diagnostics
            try:
                import platform
                
                system_info = {
                    'os': platform.system(),
                    'os_version': platform.release(),
                    'python_version': platform.python_version(),
                    'cpu_cores': psutil.cpu_count(),
                    'total_memory': psutil.virtual_memory().total // 1024 // 1024 // 1024,  # GB
                    'disk_space': psutil.disk_usage('/').total // 1024 // 1024 // 1024,  # GB
                    'boot_time': datetime.fromtimestamp(psutil.boot_time())
                }
            except Exception as e:
                system_info = {'error': str(e)}
            
            # Service diagnostics
            services = await self.service_manager.get_all_services_status()
            active_services = sum(1 for s in services if s.active)
            failed_services = sum(1 for s in services if s.status == 'failed')
            
            # Bot diagnostics
            bot_info = {
                'active_sessions': len(self.auth_manager.get_active_sessions()),
                'admin_users': len(self.auth_manager.admin_users),
                'report_subscribers': len(self.report_chat_ids),
                'monitor_subscribers': len(self.service_monitor_chats)
            }
            
            debug_text = "🔧 **System Diagnostics Report**\n\n"
            debug_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Database Status
            debug_text += f"🗄️ **Database Status:** {db_status}\n"
            if not db_results.get('total_records', {}).get('error'):
                debug_text += f"   Total Records: {self.formatter.format_number(db_results.get('total_records', {}).get('count', 0))}\n"
            if not db_results.get('table_size', {}).get('error'):
                debug_text += f"   Table Size: {db_results.get('table_size', {}).get('size_mb', 0)} MB\n"
            debug_text += "\n"
            
            # System Information
            if 'error' not in system_info:
                debug_text += "💻 **System Information:**\n"
                debug_text += f"   OS: {system_info['os']} {system_info['os_version']}\n"
                debug_text += f"   Python: {system_info['python_version']}\n"
                debug_text += f"   CPU Cores: {system_info['cpu_cores']}\n"
                debug_text += f"   Memory: {system_info['total_memory']} GB\n"
                debug_text += f"   Disk: {system_info['disk_space']} GB\n"
                debug_text += f"   Boot Time: {self.formatter.format_datetime(system_info['boot_time'])}\n\n"
            
            # Services Status
            debug_text += f"🛠️ **Services Status:**\n"
            debug_text += f"   Total Services: {len(services)}\n"
            debug_text += f"   Active Services: {active_services}\n"
            debug_text += f"   Failed Services: {failed_services}\n\n"
            
            # Bot Status
            debug_text += f"🤖 **Bot Status:**\n"
            debug_text += f"   Active Sessions: {bot_info['active_sessions']}\n"
            debug_text += f"   Admin Users: {bot_info['admin_users']}\n"
            debug_text += f"   Report Subscribers: {bot_info['report_subscribers']}\n"
            debug_text += f"   Monitor Subscribers: {bot_info['monitor_subscribers']}\n\n"
            
            debug_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await loading_msg.delete()
            await update.message.reply_text(debug_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Debug command error: {e}")
            await update.message.reply_text(
                "❌ **Debug Error**\n\nFailed to run diagnostics.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show active user sessions (admin only)"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        if not self._check_admin(update.effective_user.id):
            return await self._admin_only_response(update)
        
        await self._track_command_usage(update, "sessions")
        
        try:
            sessions = self.auth_manager.get_active_sessions()
            
            if not sessions:
                await update.message.reply_text(
                    "👥 **Active Sessions**\n\nNo active sessions found.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            sessions_text = "👥 **Active User Sessions**\n\n"
            sessions_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, session in enumerate(sessions, 1):
                username = session.get('username', 'Unknown')
                user_id = session.get('user_id', 'Unknown')
                login_time = session.get('login_time')
                last_activity = session.get('last_activity')
                command_count = session.get('command_count', 0)
                is_admin = session.get('is_admin', False)
                
                sessions_text += f"**{i}. {username}** {'👑' if is_admin else '👤'}\n"
                sessions_text += f"   ID: `{user_id}`\n"
                sessions_text += f"   Login: `{self.formatter.format_datetime(login_time) if login_time else 'Unknown'}`\n"
                sessions_text += f"   Last Activity: `{self.formatter.format_datetime(last_activity) if last_activity else 'Unknown'}`\n"
                sessions_text += f"   Commands: `{command_count}`\n\n"
            
            sessions_text += f"📊 **Total Active Sessions:** {len(sessions)}\n"
            sessions_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            await update.message.reply_text(sessions_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logging.error(f"Sessions command error: {e}")
            await update.message.reply_text(
                "❌ **Error**\n\nFailed to retrieve sessions.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced help menu with all commands"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "help")
        
        is_admin = self._check_admin(update.effective_user.id)
        
        help_text = """
🤖 **Enhanced Lapsus Database Manager v2.1.0**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Database Analytics:**
• `/istatistik` - Comprehensive database statistics
• `/bolgeler` - Regional distribution analysis
• `/enpopulerdomain` - Popular email domains
• `/son7gun` - Last 7 days activity report
• `/kaynaklar` - Source-based categorization

🔍 **Search & Query Commands:**
• `/spidsorgu <id>` - Search by specific SPID
• `/ara <keyword>` - Domain keyword search
• `/tarihsorgu <YYYY-MM-DD>` - Date-based queries
• `/domainkontrol <domain>` - Exact domain match

🛠️ **System Service Management:**
• `/servisler` - View all services status
• `/servisloglari <service>` - View service logs
• `/servisizleme` - Toggle service monitoring

📊 **Daily Report System:**
• `/gunlukrapor` - Get daily report manually
• `/raporabone` - Subscribe to daily reports (00:00)
• `/raporiptal` - Unsubscribe from reports

🛠️ **System Commands:**
• `/debug` - System diagnostics & analysis
• `/status` - Bot & database status
• `/help` - This help menu

"""
        
        if is_admin:
            help_text += """🔒 **Admin Commands:**
• `/servisyonet <action> <service>` - Control services
• `/sessions` - View active user sessions

"""
        
        help_text += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Enhanced Features:**
- ✅ Interactive service management
- ✅ Real-time status monitoring  
- ✅ System resource tracking
- ✅ Comprehensive search capabilities
- ✅ Advanced analytics & reporting
- ✅ Automated daily reports
- ✅ Admin privilege system
- ✅ Session management

🔒 **Your Access Level:** """ + ("**Admin** 👑" if is_admin else "**User** 👤") + """

🔧 **Tips:**
- All dates use YYYY-MM-DD format
- Commands are case-sensitive
- Use interactive buttons for easier navigation
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced bot and system status"""
        if not self._check_auth(update.effective_user.id):
            return await self._unauthorized_response(update)
        
        await self._track_command_usage(update, "status")
        
        # Test database connectivity
        db_status = "🟢 Connected" if await self.db_manager.test_connection() else "🔴 Disconnected"
        
        # Get system info
        active_sessions = len(self.auth_manager.get_active_sessions())
        admin_count = len(self.auth_manager.admin_users)
        current_time = self.formatter.format_datetime(datetime.now())
        
        # Get service summary
        try:
            services = await self.service_manager.get_all_services_status()
            active_services = sum(1 for s in services if s.active)
            total_services = len(services)
        except Exception:
            active_services = 0
            total_services = 0
        
        status_msg = f"""
🔧 **Enhanced System Status Report**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🗄️ **Database:** {db_status}
👥 **Active Sessions:** {active_sessions} ({admin_count} admins)
🛠️ **Services:** {active_services}/{total_services} active
🕒 **Current Time:** `{current_time}`
🤖 **Bot Version:** Enhanced v2.1.0
⚡ **Status:** Fully Operational

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 **Connection Details:**
• Host: `{self.config.db_host}:{self.config.db_port}`
• Database: `{self.config.db_name}`
• Timeout: {self.config.connection_timeout}s
• Max Retries: {self.config.max_retry_attempts}

📊 **Monitoring:**
• Report Subscribers: {len(self.report_chat_ids)}
• Service Monitors: {len(self.service_monitor_chats)}
• Check Interval: {self.config.service_check_interval}s

💡 **Features Active:**
• ✅ Database Analytics
• ✅ Service Management
• ✅ Daily Reports
• ✅ Real-time Monitoring
• ✅ Admin Controls
        """
        
        await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)
    
    # =====================================
    # CALLBACK QUERY HANDLERS
    # =====================================
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if not self._check_auth(query.from_user.id):
            await query.edit_message_text(
                "🚫 **Access Denied**\n\nYou are not authorized to use this bot.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        data = query.data
        
        # Services refresh
        if data == "services_refresh":
            await self._handle_services_refresh(query)
        elif data == "services_control":
            await self._handle_services_control_panel(query)
        elif data == "services_detailed":
            await self._handle_services_detailed(query)
        elif data == "services_logs":
            await self._handle_services_logs_menu(query)
        elif data.startswith("control_"):
            service_name = data.replace("control_", "")
            await self._handle_service_control_menu(query, service_name)
        elif data.startswith("action_"):
            parts = data.split("_", 2)
            action = parts[1]
            service_name = parts[2]
            await self._handle_service_action(query, action, service_name)
        elif data.startswith("logs_"):
            service_name = data.replace("logs_", "")
            await self._handle_service_logs(query, service_name)
    
    async def _handle_services_refresh(self, query):
        """Handle services refresh callback"""
        try:
            services = await self.service_manager.get_all_services_status()
            
            services_text = "🛠️ **System Services Status** (Refreshed)\n\n"
            services_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for service in services:
                services_text += self.formatter.format_service_status(service) + "\n"
            
            services_text += f"\n🕒 **Last Updated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="services_refresh"),
                    InlineKeyboardButton("🎛️ Control Panel", callback_data="services_control")
                ],
                [
                    InlineKeyboardButton("📊 Detailed View", callback_data="services_detailed"),
                    InlineKeyboardButton("📋 Logs", callback_data="services_logs")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                services_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"Services refresh error: {e}")
    
    async def _handle_services_control_panel(self, query):
        """Handle services control panel callback"""
        # Check admin permissions for control panel
        if not self._check_admin(query.from_user.id):
            await query.edit_message_text(
                "🔒 **Admin Access Required**\n\nService control requires administrator privileges.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        keyboard = []
        for service in self.service_manager.monitored_services:
            service_name = self.service_manager.service_display_names.get(service, service)
            keyboard.append([
                InlineKeyboardButton(
                    f"🎛️ {service_name}", 
                    callback_data=f"control_{service}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Services", callback_data="services_refresh")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎛️ **Service Control Panel** (Admin Only)\n\n"
            "Select a service to control:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_service_control_menu(self, query, service_name):
        """Handle individual service control menu"""
        if not self._check_admin(query.from_user.id):
            await query.edit_message_text(
                "🔒 **Admin Access Required**\n\nService control requires administrator privileges.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        service_display_name = self.service_manager.service_display_names.get(service_name, service_name)
        
        # Get current service status
        try:
            service_info = await self.service_manager.get_service_status(service_name)
            status_text = self.formatter.format_service_status(service_info)
        except Exception as e:
            status_text = f"❌ Error getting status: {e}"
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ Start", callback_data=f"action_start_{service_name}"),
                InlineKeyboardButton("⏹️ Stop", callback_data=f"action_stop_{service_name}")
            ],
            [
                InlineKeyboardButton("🔄 Restart", callback_data=f"action_restart_{service_name}"),
                InlineKeyboardButton("📋 Logs", callback_data=f"logs_{service_name}")
            ],
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"action_enable_{service_name}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"action_disable_{service_name}")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="services_control")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎛️ **Control: {service_display_name}**\n\n"
            f"{status_text}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select an action:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_service_action(self, query, action, service_name):
        """Handle service action execution"""
        if not self._check_admin(query.from_user.id):
            await query.edit_message_text(
                "🔒 **Admin Access Required**\n\nService control requires administrator privileges.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        service_display_name = self.service_manager.service_display_names.get(service_name, service_name)
        
        # Show loading message
        await query.edit_message_text(
            f"🔄 **{action.title()}ing {service_display_name}...**\n\n"
            "Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Execute action
        result = await self.service_manager.control_service(service_name, action)
        
        # Show result
        if result["success"]:
            message = (
                f"✅ **Action Successful**\n\n"
                f"Service: **{service_display_name}**\n"
                f"Action: **{action.title()}**\n"
                f"Result: {result['message']}"
            )
        else:
            message = (
                f"❌ **Action Failed**\n\n"
                f"Service: **{service_display_name}**\n"
                f"Action: **{action.title()}**\n"
                f"Error: {result['message']}"
            )
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data=f"control_{service_name}"),
                InlineKeyboardButton("⬅️ Back", callback_data="services_control")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_service_logs(self, query, service_name):
        """Handle service logs display"""
        service_display_name = self.service_manager.service_display_names.get(service_name, service_name)
        
        await query.edit_message_text(
            f"📋 **Loading logs for {service_display_name}...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logs = await self.service_manager.get_service_logs(service_name, 15)
        
        # Split logs if too long
        if len(logs) > 3500:
            logs = logs[-3500:]
            logs = "...(truncated)\n" + logs
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"logs_{service_name}"),
                InlineKeyboardButton("🎛️ Control", callback_data=f"control_{service_name}")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="services_logs")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📋 **Logs: {service_display_name}** (last 15 lines)\n\n"
            f"```\n{logs}\n```",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_services_logs_menu(self, query):
        """Handle services logs menu"""
        keyboard = []
        for service in self.service_manager.monitored_services:
            service_name = self.service_manager.service_display_names.get(service, service)
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {service_name}", 
                    callback_data=f"logs_{service}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Services", callback_data="services_refresh")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 **Service Logs**\n\n"
            "Select a service to view logs:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_services_detailed(self, query):
        """Handle detailed services view"""
        try:
            services = await self.service_manager.get_all_services_status()
            
            detailed_text = "📊 **Detailed System Status**\n\n"
            detailed_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # System overview
            try:
                cpu_count = psutil.cpu_count()
                cpu_freq = psutil.cpu_freq()
                boot_time = datetime.fromtimestamp(psutil.boot_time())
                system_uptime = datetime.now() - boot_time
                
                detailed_text += "💻 **System Information:**\n"
                detailed_text += f"   CPU Cores: `{cpu_count}`\n"
                if cpu_freq:
                    detailed_text += f"   CPU Frequency: `{cpu_freq.current:.0f} MHz`\n"
                detailed_text += f"   System Uptime: `{self.service_manager._format_uptime(system_uptime)}`\n"
                detailed_text += f"   Boot Time: `{self.formatter.format_datetime(boot_time)}`\n\n"
            except Exception as e:
                logging.error(f"Error getting system info: {e}")
            
            # Services details
            active_services = sum(1 for s in services if s.active)
            failed_services = sum(1 for s in services if s.status == 'failed')
            
            detailed_text += f"🛠️ **Services Summary:**\n"
            detailed_text += f"   Total Services: `{len(services)}`\n"
            detailed_text += f"   Active Services: `{active_services}`\n"
            detailed_text += f"   Failed Services: `{failed_services}`\n\n"
            
            # Individual service details
            for service in services:
                detailed_text += f"**{service.display_name}:**\n"
                detailed_text += f"   Status: `{service.status}` {'✅' if service.active else '❌'}\n"
                detailed_text += f"   Enabled: `{'Yes' if service.enabled else 'No'}`\n"
                
                if service.uptime:
                    detailed_text += f"   Uptime: `{service.uptime}`\n"
                if service.memory_usage:
                    detailed_text += f"   Memory: `{service.memory_usage:.1f} MB`\n"
                if service.cpu_usage is not None:
                    detailed_text += f"   CPU: `{service.cpu_usage:.1f}%`\n"
                if service.pid:
                    detailed_text += f"   PID: `{service.pid}`\n"
                
                detailed_text += "\n"
            
            detailed_text += f"🕒 **Generated:** `{self.formatter.format_datetime(datetime.now())}`"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="services_detailed"),
                    InlineKeyboardButton("⬅️ Back", callback_data="services_refresh")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                detailed_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"Detailed services view error: {e}")
            await query.edit_message_text(
                "❌ **Error loading detailed view**",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # =====================================
    # SERVICE MONITORING
    # =====================================
    
    async def start_service_monitoring(self):
        """Start background service monitoring"""
        if not self.service_monitor_enabled:
            return
        
        logging.info("Starting service monitoring background task...")
        
        while self.service_monitor_enabled:
            try:
                services = await self.service_manager.get_all_services_status()
                changes = self.service_manager.detect_status_changes(services)
                
                if changes and self.service_monitor_chats:
                    await self._send_service_notifications(changes)
                
                await asyncio.sleep(self.config.service_check_interval)
                
            except Exception as e:
                logging.error(f"Service monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _send_service_notifications(self, changes: List[Dict[str, Any]]):
        """Send service status change notifications"""
        for change in changes:
            notification = (
                f"🔔 **Service Status Change**\n\n"
                f"Service: **{change['service']}**\n"
                f"Previous: `{change['previous_status']}`\n"
                f"Current: `{change['current_status']}`\n"
                f"Time: `{self.formatter.format_datetime(change['timestamp'])}`"
            )
            
            # Add status emoji
            if change['current_status'] == 'active':
                notification = "✅ " + notification
            elif change['current_status'] == 'failed':
                notification = "❌ " + notification
            elif change['current_status'] == 'inactive':
                notification = "🔴 " + notification
            
            # Send to all monitoring chats
            for chat_id in self.service_monitor_chats.copy():
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=notification,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logging.error(f"Failed to send notification to {chat_id}: {e}")
                    # Remove problematic chat
                    self.service_monitor_chats.discard(chat_id)

# =====================================
# ENHANCED APPLICATION CLASS
# =====================================

class LapsusBotApplication:
    """Enhanced bot application with complete functionality"""
    
    def __init__(self):
        self.config = Config.load_from_env()
        self.handler = LapsusBotHandler(self.config)
        self.application: Optional[Application] = None
        self.scheduler_thread = None
        self.scheduler_running = False
        self.monitoring_task = None
    
    def setup_handlers(self):
        """Setup all command handlers"""
        handlers = [
            # Authentication
            ("giris", self.handler.cmd_login),
            ("login", self.handler.cmd_login),
            
            # Information
            ("help", self.handler.cmd_help),
            ("start", self.handler.cmd_help),
            ("status", self.handler.cmd_status),
            
            # Database Analytics
            ("istatistik", self.handler.cmd_statistics),
            ("bolgeler", self.handler.cmd_regions),
            ("enpopulerdomain", self.handler.cmd_popular_domains),
            ("son7gun", self.handler.cmd_last_7_days),
            ("kaynaklar", self.handler.cmd_sources),
            
            # Search Commands
            ("spidsorgu", self.handler.cmd_search_spid),
            ("ara", self.handler.cmd_search_keyword),
            ("tarihsorgu", self.handler.cmd_date_query),
            ("domainkontrol", self.handler.cmd_domain_control),
            
            # Service Management
            ("servisler", self.handler.cmd_services),
            ("servisyonet", self.handler.cmd_service_control),
            ("servisloglari", self.handler.cmd_service_logs),
            ("servisizleme", self.handler.cmd_service_monitor),
            
            # Daily Reports
            ("gunlukrapor", self.handler.cmd_daily_report),
            ("raporabone", self.handler.cmd_report_subscribe),
            ("raporiptal", self.handler.cmd_report_unsubscribe),
            
            # Debug & Admin
            ("debug", self.handler.cmd_debug),
            ("sessions", self.handler.cmd_sessions),
        ]
        
        for command, handler in handlers:
            self.application.add_handler(CommandHandler(command, handler))
        
        # Add callback query handler
        self.application.add_handler(CallbackQueryHandler(self.handler.handle_callback_query))
        
        logging.info(f"✅ Registered {len(handlers)} command handlers + callback handler")
    
    async def start_background_tasks(self):
        """Start background monitoring tasks"""
        # Start service monitoring
        if self.handler.service_monitor_enabled:
            self.monitoring_task = asyncio.create_task(self.handler.start_service_monitoring())
            logging.info("✅ Service monitoring task started")
    
    def run_sync(self):
        """Synchronous run method"""
        try:
            # Validate required environment variables
            if not self.config.bot_token:
                logging.error("❌ BOT_TOKEN environment variable is required")
                return False
            
            if not self.config.secret_token:
                logging.error("❌ SECRET_TOKEN environment variable is required")
                return False
            
            # Initialize bot handler
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            init_success = loop.run_until_complete(self.handler.initialize())
            if not init_success:
                logging.error("❌ Bot initialization failed")
                return False
            
            # Create application
            self.application = ApplicationBuilder().token(self.config.bot_token).build()
            self.handler.application = self.application
            
            # Setup handlers
            self.setup_handlers()
            
            logging.info("🚀 Enhanced Lapsus Bot initialized successfully")
            logging.info("🤖 Starting Enhanced Lapsus Database Manager Bot...")
            
            # Start background tasks
            loop.run_until_complete(self.start_background_tasks())
            
            # Start bot polling
            self.application.run_polling(drop_pending_updates=True)
            
        except KeyboardInterrupt:
            logging.info("🛑 Bot stopped by user")
        except Exception as e:
            logging.error(f"❌ Bot runtime error: {e}")
            return False
        finally:
            logging.info("🔄 Cleaning up resources...")
            if self.monitoring_task:
                self.monitoring_task.cancel()
        
        return True

# =====================================
# LOGGING SETUP
# =====================================

def setup_logging(config: BotConfig):
    """Setup comprehensive logging"""
    log_format = "%(asctime)s | %(levelname)8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    os.makedirs("logs", exist_ok=True)
    
    file_handler = logging.FileHandler(
        filename=f"logs/enhanced_lapsus_bot_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level.upper()))
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler],
        format=log_format,
        datefmt=date_format
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

# =====================================
# MAIN ENTRY POINT
# =====================================

def main():
    """Main application entry point"""
    print("""
    ╔══════════════════════════════════════════╗
    ║      ENHANCED LAPSUS DATABASE MANAGER    ║
    ║           Complete Edition v2.1.0        ║
    ║     With Full Service Management         ║
    ╚══════════════════════════════════════════╝
    """)
    
    config = Config.load_from_env()
    setup_logging(config)
    
    # Validate critical environment variables
    if not config.bot_token:
        print("❌ ERROR: BOT_TOKEN environment variable is required!")
        print("Set it with: export BOT_TOKEN='your_bot_token_here'")
        sys.exit(1)
    
    if not config.secret_token:
        print("❌ ERROR: SECRET_TOKEN environment variable is required!")
        print("Set it with: export SECRET_TOKEN='your_secret_token_here'")
        sys.exit(1)
    
    if not config.db_password:
        print("❌ ERROR: DB_PASSWORD environment variable is required!")
        print("Set it with: export DB_PASSWORD='your_db_password_here'")
        sys.exit(1)
    
    logging.info("🔧 Enhanced configuration loaded successfully")
    logging.info(f"   Database: {config.db_host}:{config.db_port}/{config.db_name}")
    logging.info(f"   Service monitoring: {config.service_check_interval}s interval")
    logging.info(f"   Log level: {config.log_level}")
    
    bot_app = LapsusBotApplication()
    success = bot_app.run_sync()
    
    if not success:
        print("\n💥 Bot failed to start properly")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Enhanced bot stopped gracefully")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        logging.error(f"Fatal error in main: {e}")
        sys.exit(1)