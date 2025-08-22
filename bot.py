import os
import re
import sqlite3
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

# 默认环境变量回退
BOT_TOKEN = os.getenv("BOT_TOKEN") or "REPLACE_ME"
DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL") or "-1000000000000"
DB_FILE = os.getenv("DB_FILE") or "channel_helper_pro.db"

# normalize_keyword 示例函数
def normalize_keyword(text: str) -> str:
    return re.sub(r"[^\w\d]", "", text.strip().lower())

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)



# -*- coding: utf-8 -*-
# Channel Navigator Bot · Combined Full Version (aiogram v3)
#
# ✅ 综合版：融合 UI/信息架构(ready_bot 样式)+ 广告管理与FSM(444.txt 样式)
# - 三行双列主菜单、国家大行 + A–Z 索引、工具合集、合作须知、客服直达
# - 广告管理：分类、分页列表、创建/编辑/启停/预览、图片+文案+按钮URL 全流程
# - 运维：面板发布/更新/删除、自定义按钮与链接、统计/导出/导入、健康检查
#
# 运行前：pip install -r requirements.txt，并配置 .env(或环境变量)
# 环境变量：BOT_TOKEN, DEFAULT_CHANNEL(可选), DB_FILE(可选)
#
# Author: Combined by ChatGPT

import os
import asyncio
import logging
import sqlite3
import datetime
import json
from typing import Dict, List, Tuple, Optional, Set

# --- auto-fallback for build_bank_detail_kb (injected) ---
try:
    build_bank_detail_kb  # type: ignore  # noqa: F821
except NameError:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    def build_bank_detail_kb(bank_name: str):
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ 返回", callback_data="go_home")]]
        )
# --- end fallback ---

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, CallbackQuery, Message, FSInputFile
)
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import types
import re, datetime, sqlite3
# ========== 日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

START_TIME = datetime.datetime.now()

# ========== 环境 ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Missing env BOT_TOKEN")
DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL", "").strip() or "-1001234567890"
DB_FILE = os.getenv("DB_FILE", "channel_helper_pro.db").strip()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ========== 数据库 ==========
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    c = db()
    cur = c.cursor()
    # 基础表
    cur.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS panels(
        chat_id INTEGER PRIMARY KEY,
        message_id INTEGER NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_meta(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_seen DATETIME
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS query_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        keyword TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    # 广告分类与广告
    cur.execute("""CREATE TABLE IF NOT EXISTS ad_categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sort INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        caption TEXT,
        url TEXT,
        photo_file_id TEXT,
        category_id INTEGER,
        active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME,
        FOREIGN KEY(category_id) REFERENCES ad_categories(id)
    )""")
    # 默认设置
    cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('default_channel', ?)", (DEFAULT_CHANNEL,))
    # 默认广告分类(如不存在)
    cur.execute("SELECT COUNT(*) AS c FROM ad_categories")
    if (cur.fetchone()["c"] or 0) == 0:
        cur.executemany("INSERT INTO ad_categories(name, sort) VALUES(?,?)",
                        [("默认", 0), ("活动", 10), ("教程", 20)])
    c.commit()
    c.close()
    logger.info("Database initialized")

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    c = db()
    try:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        c.close()

def set_setting(key: str, value: str) -> None:
    c = db()
    try:
        c.execute("""INSERT INTO settings(key, value) VALUES(?,?)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value))
        c.commit()
    finally:
        c.close()

def panel_get(chat_id: int) -> Optional[int]:
    c = db()
    try:
        row = c.execute("SELECT message_id FROM panels WHERE chat_id=?", (chat_id,)).fetchone()
        return row["message_id"] if row else None
    finally:
        c.close()

def panel_set(chat_id: int, message_id: int) -> None:
    c = db()
    try:
        c.execute("""INSERT INTO panels(chat_id, message_id) VALUES(?,?)
                     ON CONFLICT(chat_id) DO UPDATE SET message_id=excluded.message_id, updated_at=CURRENT_TIMESTAMP""",
                  (chat_id, message_id))
        c.commit()
    finally:
        c.close()

def panel_del(chat_id: int) -> None:
    c = db()
    try:
        c.execute("DELETE FROM panels WHERE chat_id=?", (chat_id,))
        c.commit()
    finally:
        c.close()

# ========== 权限 ==========
def owners_get() -> Set[int]:
    v = get_setting("owners", "") or ""
    return {int(x) for x in v.split(",") if x.strip().isdigit()}

def owners_set(s: Set[int]) -> None:
    set_setting("owners", ",".join(str(x) for x in sorted(s)))

def is_owner(uid: int) -> bool:
    s = owners_get()
    return (uid in s) or (not s)  # 首次未设置时允许添加

@dp.message(Command("owner_list"))
async def cmd_owner_list(m: Message):
    s = owners_get()
    msg = "\n".join(f"- <code>{x}</code>" for x in sorted(s)) if s else "(空)"
    await m.reply("OWNER 列表：\n" + msg)

@dp.message(Command("owner_add"))
async def cmd_owner_add(m: Message):
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await m.reply("用法：/owner_add 123456789")
    s = owners_get(); s.add(int(parts[1])); owners_set(s)
    await m.reply("✅ 已添加。")

@dp.message(Command("owner_del"))
async def cmd_owner_del(m: Message):
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await m.reply("用法：/owner_del 123456789")
    s = owners_get(); uid = int(parts[1])
    if uid in s: s.remove(uid); owners_set(s); await m.reply("✅ 已移除。")
    else: await m.reply("该用户不在 OWNER 列表。")

# ========== 默认按钮与链接 ==========
BUTTON_KEYS_DEFAULT: Dict[str, str] = {
    "btn_follow": "关注频道 · 自助验卡",
    "btn_index": "测卡索引 A-Z",
    "btn_tools": "发车工具合集",
    "btn_newcoin": "新币公群",
    "btn_coop": "合作须知",
    "btn_contact": "📞 汇赢客服直达",
}

LINK_KEYS_DEFAULT: Dict[str, str] = {
    "link_selfcheck": "https://t.me/Gymmmmm913bot?start=gate",
    "link_follow": "https://t.me/BLQnX6H5oBgyZjhl",
    "link_newcoin": "https://t.me/+nPePu1sWtx9hMzUx",
    "tool_ysf_query": "https://t.me/BLQnX6H5oBgyZjhl/72",
    "tool_aircharge_pic": "https://t.me/BLQnX6H5oBgyZjhl/702",
    "tool_nx_cert": "https://t.me/BLQnX6H5oBgyZjhl/75",
    "tool_nx_north": "https://t.me/BLQnX6H5oBgyZjhl/819",
    "flow_measure": "https://t.me/BLQnX6H5oBgyZjhl/700",
    "flow_depart": "https://t.me/BLQnX6H5oBgyZjhl/659",
    "guide_coop": "https://t.me/BLQnX6H5oBgyZjhl/886",
}

def get_setting_cached(key: str, default: Optional[str] = None) -> str:
    return get_setting(key, default)

def btn_text(key: str) -> str:
    return get_setting_cached(key, BUTTON_KEYS_DEFAULT.get(key, key))

def link_get(key: str) -> str:
    return get_setting_cached(key, LINK_KEYS_DEFAULT.get(key, ""))

# ========== 链接与索引 ==========
LINKS: Dict[str, str] = {
    "main_channel": "https://t.me/BLQnX6H5oBgyZjhl",
    "contact_cards": "https://t.me/HYZFzuanshi",
    "contact_fleet": "https://t.me/HUIYINGFUWA",
    "guide_coop": link_get("guide_coop"),
    "hub_baibao": "https://t.me/BLQnX6H5oBgyZjhl/738",
    "hub_course": "https://t.me/BLQnX6H5oBgyZjhl/133",
    "tpl_ag": "https://t.me/BLQnX6H5oBgyZjhl/138",
    "tpl_hz": "https://t.me/BLQnX6H5oBgyZjhl/139",
    "corp_standard": "https://t.me/BLQnX6H5oBgyZjhl/831",
    "tool_aircharge_pic": link_get("tool_aircharge_pic"),
    "tool_aircharge_video": link_get("tool_aircharge_pic"),
    "tool_ysf_query": link_get("tool_ysf_query"),
    "tool_nx_cert": link_get("tool_nx_cert"),
    "tool_nx_north": link_get("tool_nx_north"),
    "flow_measure": link_get("flow_measure"),
    "flow_depart": link_get("flow_depart"),
    "docking_newbie": "https://t.me/BLQnX6H5oBgyZjhl/125",
    "rule_settlement": "https://t.me/BLQnX6H5oBgyZjhl/124",
    "rule_fleet": "https://t.me/BLQnX6H5oBgyZjhl/871",
    "rule_common_material": "https://t.me/BLQnX6H5oBgyZjhl/186",
    "rule_half_insured_counter": "https://t.me/BLQnX6H5oBgyZjhl/143",
    "loan_hub": "https://t.me/BLQnX6H5oBgyZjhl/826",
    "loan_useful": "https://t.me/BLQnX6H5oBgyZjhl/63",
    "loan_monthly_formula": "https://t.me/BLQnX6H5oBgyZjhl/821",
    "apple_id_us": "https://t.me/BLQnX6H5oBgyZjhl/817",
    "apple_id_cn": "https://t.me/BLQnX6H5oBgyZjhl/816",
    "boc_topic": "https://t.me/BLQnX6H5oBgyZjhl/198", "boc_method": "https://t.me/BLQnX6H5oBgyZjhl/791",
    "ccb_topic": "https://t.me/BLQnX6H5oBgyZjhl/650", "ccb_star": "https://t.me/BLQnX6H5oBgyZjhl/651",
    "icbc_topic": "https://t.me/c/2025069980/780", "abc_topic": "https://t.me/c/2025069980/203",
    "abc_overseas_pos": "https://t.me/BLQnX6H5oBgyZjhl/671",
    "cmbc_topic": "https://t.me/c/2025069980/224", "cib_topic": "https://t.me/c/2025069980/242",
    "psbc_topic": "https://t.me/c/2025069980/802", "bcom_topic": "https://t.me/c/2025069980/215",
    "cgb_topic": "https://t.me/c/2025069980/237", "citic_topic": "https://t.me/c/2025069980/654",
    "spdb_topic": "https://t.me/BLQnX6H5oBgyZjhl/229", "cmb_topic": "https://t.me/BLQnX6H5oBgyZjhl/249",
    "cebb_topic": "https://t.me/BLQnX6H5oBgyZjhl/252", "pingan_topic": "https://t.me/BLQnX6H5oBgyZjhl/245",
    "hxb_topic": "https://t.me/BLQnX6H5oBgyZjhl/230",
    "anhui_nx": "https://t.me/BLQnX6H5oBgyZjhl/844",
    "bohai": "https://t.me/c/2025069980/766",
    "beijing_bank": "https://t.me/c/2025069980/391",
    "baoding_bank": "https://t.me/BLQnX6H5oBgyZjhl/809",
    "beibuwan_bank": "https://t.me/BLQnX6H5oBgyZjhl/691",
    "beijing_nsh": "https://t.me/c/2025069980/294",
    "chengdu_bank": "https://t.me/BLQnX6H5oBgyZjhl/641",
    "chengde_bank": "https://t.me/BLQnX6H5oBgyZjhl/622",
    "changsha_bank": "https://t.me/c/2025069980/787",
    "chongqing_bank": "https://t.me/c/2025069980/472",
    "chang_an_bank": "https://t.me/c/2025069980/538",
    "changcheng_huaxi": "https://t.me/BLQnX6H5oBgyZjhl/629",
    "chongqing_sanxia": "https://t.me/c/2025069980/460",
    "chongqing_nsh": "https://t.me/c/2025069980/182",
    "changshu_nsh": "https://t.me/c/2025069980/318",
    "dongguan_nsh": "https://t.me/c/2025069980/302",
    "dalian_bank": "https://t.me/c/2025069980/797",
    "dongguan_bank": "https://t.me/c/2025069980/558",
    "fujian_haixia": "https://t.me/c/2025069980/452",
    "fujian_rcc": "https://t.me/c/2025069980/364",
    "guizhou_bank": "https://t.me/c/2025069980/406",
    "guilin_bank": "https://t.me/c/2025069980/398",
    "gansu_bank": "https://t.me/c/2025069980/732",
    "guangdong_huaxing": "https://t.me/c/2025069980/444",
    "guangdong_nx": "https://t.me/c/2025069980/330",
    "guizhou_nx": "https://t.me/c/2025069980/340",
    "guangxi_nx": "https://t.me/c/2025069980/684",
    "gansu_nx": "https://t.me/c/2025069980/366",
    "huarun_bank": "https://t.me/BLQnX6H5oBgyZjhl/855",
    "hengshui_bank": "https://t.me/c/2025069980/435",
    "henan_nx": "https://t.me/c/2025069980/177",
    "hunan_nx": "https://t.me/c/2025069980/163",
    "hubei_nx": "https://t.me/c/2025069980/183",
    "huludao_bank": "https://t.me/BLQnX6H5oBgyZjhl/608",
    "hebei_nx": "https://t.me/BLQnX6H5oBgyZjhl/829",
    "haerbin_bank": "https://t.me/c/2025069980/409",
    "hankou_bank": "https://t.me/c/2025069980/457",
    "huishang_bank": "https://t.me/c/2025069980/755",
    "heilongjiang_nx": "https://t.me/c/2025069980/805",
    "jilin_bank": "https://t.me/c/2025069980/687",
    "jiangsu_bank": "https://t.me/c/2025069980/553",
    "jiangxi_bank": "https://t.me/c/2025069980/533",
    "jiangxi_nx_post": "https://t.me/c/2025069980/290",
    "jiangxi_nx": "https://t.me/c/2025069980/287",
    "jiangnan_nsh": "https://t.me/c/2025069980/417",
    "jinzhou_bank": "https://t.me/BLQnX6H5oBgyZjhl/853",
    "jinshang_bank": "https://t.me/BLQnX6H5oBgyZjhl/825",
    "jilin_nx": "https://t.me/c/2025069980/262",
    "kunlun_bank": "https://t.me/c/2025069980/375",
    "linshang_bank": "https://t.me/c/2025069980/388",
    "liaoning_nx": "https://t.me/c/2025069980/760",
    "lanzhou_bank": "https://t.me/c/2025069980/523",
    "langfang_bank": "https://t.me/BLQnX6H5oBgyZjhl/851",
    "nanjing_bank": "https://t.me/c/2025069980/379",
    "ningxia_bank": "https://t.me/BLQnX6H5oBgyZjhl/582",
    "ningbo_bank": "https://t.me/c/2025069980/426",
    "neimeng_nx": "https://t.me/c/2025069980/170",
    "panzhihua_nsh": "https://t.me/c/2025069980/310",
    "qingdao_bank": "https://t.me/c/2025069980/519",
    "qinghai_bank": "https://t.me/BLQnX6H5oBgyZjhl/837",
    "shaoxing_bank": "https://t.me/c/2025069980/400",
    "shanxi_bank": "https://t.me/c/2025069980/432",
    "shanghai_bank": "https://t.me/c/2025069980/513",
    "shanxi_nx": "https://t.me/c/2025069980/352",
    "shengjing_bank": "https://t.me/c/2025069980/694",
    "shandong_gaoqing_hj": "https://t.me/c/2025069980/467",
    "shandong_nx": "https://t.me/c/2025069980/359",
    "tailong_bank": "https://t.me/c/2025069980/384",
    "tianjin_nsh": "https://t.me/c/2025069980/255",
    "tianjin_binhai_nsh": "https://t.me/c/2025069980/278",
    "tangshan_bank": "https://t.me/BLQnX6H5oBgyZjhl/840",
    "wuhan_nsh": "https://t.me/c/2025069980/307",
    "wuxi_nsh": "https://t.me/c/2025069980/284",
    "xiamen_bank": "https://t.me/BLQnX6H5oBgyZjhl/635?single",
    "xinjiang_nx": "https://t.me/c/2025069980/260",
    "xian_changan_xinhua": "https://t.me/c/2025069980/545",
    "yunnan_nx": "https://t.me/c/2025069980/335",
    "yibin_bank": "https://t.me/c/2025069980/420",
    "zhejiang_nsh": "https://t.me/BLQnX6H5oBgyZjhl/638",
    "zhangjiakou_bank": "https://t.me/c/2025069980/414",
    "zhongyuan_bank": "https://t.me/c/2025069980/449",
}

INDEX_AZ: Dict[str, List[Tuple[str, str]]] = {
    "A": [("安徽农信", LINKS.get("anhui_nx", ""))],
    "B": [("渤海银行", LINKS.get("bohai", "")), ("北京银行", LINKS.get("beijing_bank", "")),
          ("保定银行", LINKS.get("baoding_bank", "")), ("北部湾银行", LINKS.get("beibuwan_bank", "")),
          ("北京农商", LINKS.get("beijing_nsh", ""))],
    "C": [("成都银行", LINKS.get("chengdu_bank", "")), ("承德银行", LINKS.get("chengde_bank", "")),
          ("长沙银行", LINKS.get("changsha_bank", "")), ("重庆银行", LINKS.get("chongqing_bank", "")),
          ("长安银行", LINKS.get("chang_an_bank", "")), ("长城华西银行", LINKS.get("changcheng_huaxi", "")),
          ("重庆三峡银行", LINKS.get("chongqing_sanxia", "")), ("重庆农商", LINKS.get("chongqing_nsh", "")),
          ("常熟农商", LINKS.get("changshu_nsh", ""))],
    "D": [("东莞农商", LINKS.get("dongguan_nsh", "")), ("大连银行", LINKS.get("dalian_bank", "")),
          ("东莞银行", LINKS.get("dongguan_bank", ""))],
    "F": [("福建海峡", LINKS.get("fujian_haixia", "")), ("福建农村信用社", LINKS.get("fujian_rcc", ""))],
    "G": [("贵州银行", LINKS.get("guizhou_bank", "")), ("桂林银行", LINKS.get("guilin_bank", "")),
          ("甘肃银行", LINKS.get("gansu_bank", "")), ("广东华兴银行", LINKS.get("guangdong_huaxing", "")),
          ("广东农信", LINKS.get("guangdong_nx", "")), ("贵州农信", LINKS.get("guizhou_nx", "")),
          ("广西农信", LINKS.get("guangxi_nx", "")), ("甘肃农信", LINKS.get("gansu_nx", ""))],
    "H": [("华润银行", LINKS.get("huarun_bank", "")), ("衡水银行", LINKS.get("hengshui_bank", "")),
          ("河南农信", LINKS.get("henan_nx", "")), ("湖南农信", LINKS.get("hunan_nx", "")),
          ("湖北农信", LINKS.get("hubei_nx", "")), ("葫芦岛银行", LINKS.get("huludao_bank", "")),
          ("河北农信", LINKS.get("hebei_nx", "")), ("哈尔滨银行", LINKS.get("haerbin_bank", "")),
          ("汉口银行", LINKS.get("hankou_bank", "")), ("徽商银行", LINKS.get("huishang_bank", "")),
          ("黑龙江农信", LINKS.get("heilongjiang_nx", ""))],
    "J": [("吉林银行", LINKS.get("jilin_bank", "")), ("江苏银行", LINKS.get("jiangsu_bank", "")),
          ("江西银行", LINKS.get("jiangxi_bank", "")), ("江西农信", LINKS.get("jiangxi_nx", "")),
          ("江南农商", LINKS.get("jiangnan_nsh", "")), ("锦州银行", LINKS.get("jinzhou_bank", "")),
          ("九江银行", LINKS.get("yibin_bank", "")), ("晋商银行", LINKS.get("jinshang_bank", ""))],
    "K": [("昆仑银行", LINKS.get("kunlun_bank", ""))],
    "L": [("临商银行", LINKS.get("linshang_bank", "")), ("辽宁农信", LINKS.get("liaoning_nx", "")),
          ("兰州银行", LINKS.get("lanzhou_bank", "")), ("廊坊银行", LINKS.get("langfang_bank", ""))],
    "N": [("南京银行", LINKS.get("nanjing_bank", "")), ("宁夏银行", LINKS.get("ningxia_bank", "")),
          ("宁波银行", LINKS.get("ningbo_bank", "")), ("内蒙古农信", LINKS.get("neimeng_nx", ""))],
    "P": [("攀枝花农商", LINKS.get("panzhihua_nsh", ""))],
    "Q": [("青岛银行", LINKS.get("qingdao_bank", "")), ("青海银行", LINKS.get("qinghai_bank", ""))],
    "S": [("绍兴银行", LINKS.get("shaoxing_bank", "")), ("山西银行", LINKS.get("shanxi_bank", "")),
          ("上海银行", LINKS.get("shanghai_bank", "")), ("山西农信", LINKS.get("shanxi_nx", "")),
          ("盛京银行", LINKS.get("shengjing_bank", "")), ("山东农信", LINKS.get("shandong_nx", ""))],
    "T": [("泰隆银行", LINKS.get("tailong_bank", "")), ("天津农商", LINKS.get("tianjin_nsh", "")),
          ("天津滨海农商", LINKS.get("tianjin_binhai_nsh", "")), ("唐山银行", LINKS.get("tangshan_bank", ""))],
    "W": [("武汉农商", LINKS.get("wuhan_nsh", "")), ("无锡农商", LINKS.get("wuxi_nsh", ""))],
    "X": [("厦门银行", LINKS.get("xiamen_bank", "")), ("新疆农信", LINKS.get("xinjiang_nx", "")),
          ("西安长安新华", LINKS.get("xian_changan_xinhua", ""))],
    "Y": [("云南农信", LINKS.get("yunnan_nx", "")), ("宜宾商业银行", LINKS.get("yibin_bank", ""))],
    "Z": [("张家口银行", LINKS.get("zhangjiakou_bank", "")), ("中原银行", LINKS.get("zhongyuan_bank", ""))],
}
BANK_DETAIL: Dict[str, List[Tuple[str, str]]] = {
    "中国银行": [("本行专题", LINKS.get("boc_topic", "")), ("测卡方式", LINKS.get("boc_method", ""))],
    "建设银行": [("本行专题", LINKS.get("ccb_topic", "")), ("星级查看方式", LINKS.get("ccb_star", ""))],
    "工商银行": [("本行专题", LINKS.get("icbc_topic", ""))],
    "农业银行": [("本行专题", LINKS.get("abc_topic", "")), ("境外POS额度", LINKS.get("abc_overseas_pos", ""))],
    "民生银行": [("本行专题", LINKS.get("cmbc_topic", ""))],
    "兴业银行": [("本行专题", LINKS.get("cib_topic", ""))],
    "邮政银行": [("本行专题", LINKS.get("psbc_topic", ""))],
    "交通银行": [("本行专题", LINKS.get("bcom_topic", ""))],
    "广发银行": [("本行专题", LINKS.get("cgb_topic", ""))],
    "中信银行": [("本行专题", LINKS.get("citic_topic", ""))],
    "浦发银行": [("本行专题", LINKS.get("spdb_topic", ""))],
    "招商银行": [("本行专题", LINKS.get("cmb_topic", ""))],
    "光大银行": [("本行专题", LINKS.get("cebb_topic", ""))],
    "平安银行": [("本行专题", LINKS.get("pingan_topic", ""))],
    "华夏银行": [("本行专题", LINKS.get("hxb_topic", ""))],
}

# ========== 内部工具 ==========
async def safe_edit(message, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

async def swap_view(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    # ACK 回调优先，避免 'query is too old'
    try:
        await cq.answer()
    except Exception:
        pass

    # 尝试编辑原消息；失败则发新消息兜底
    try:
        if cq.message:
            await safe_edit(cq.message, text, kb)
        else:
            try:
                await bot.edit_message_text(
                    text=text,
                    inline_message_id=cq.inline_message_id,
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except TelegramBadRequest:
                await bot.edit_message_caption(
                    caption=text,
                    inline_message_id=cq.inline_message_id,
                    reply_markup=kb,
                )
    except Exception:
        try:
            chat_id = cq.message.chat.id if (getattr(cq, "message", None) and cq.message.chat) else cq.from_user.id
        except Exception:
            chat_id = cq.from_user.id
        try:
            await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass


async def ensure_followed(user_id: int) -> bool:
    chan = get_setting("default_channel", DEFAULT_CHANNEL)
    try:
        member = await bot.get_chat_member(chan, user_id)
        st = getattr(member, "status", "")
        return st in ("member", "administrator", "creator")
    except TelegramNetworkError:
        return False
    except Exception:
        return False

def follow_gate_kb() -> InlineKeyboardMarkup:
    chan_url = link_get("link_follow") or LINKS.get("main_channel", "")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="去关注频道", url=chan_url)],
        [InlineKeyboardButton(text="我已关注，继续", callback_data="check_sub")],
        [InlineKeyboardButton(text="\U0001F3E0 返回首页", callback_data="go_home")],
    ])

# ========== 键盘 ==========

def shares_bank_menu() -> InlineKeyboardMarkup:
    names = ["招商银行","浦发银行","中信银行","民生银行","光大银行","华夏银行","广发银行","平安银行"]
    rows, row = [], []
    for n in names:
        row.append(InlineKeyboardButton(text=n, callback_data=f"bank:{n}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(text="\u2B05 返回索引", callback_data="idx_home"),
                 InlineKeyboardButton(text="\U0001F3E0 返回首页", callback_data="go_home")])
    rows.append([InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def city_index_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="拼音 A-G", callback_data="idx_range:AG"),
         InlineKeyboardButton(text="拼音 H-Z", callback_data="idx_range:HZ")],
        [InlineKeyboardButton(text="\u2B05 返回索引", callback_data="idx_home"),
         InlineKeyboardButton(text="\U0001F3E0 返回首页", callback_data="go_home")],
        [InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ])

def rcc_index_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="拼音 A-G", callback_data="idx_range:AG"),
         InlineKeyboardButton(text="拼音 H-Z", callback_data="idx_range:HZ")],
        [InlineKeyboardButton(text="\u2B05 返回索引", callback_data="idx_home"),
         InlineKeyboardButton(text="\U0001F3E0 返回首页", callback_data="go_home")],
        [InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ])


def main_menu() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=btn_text("btn_follow"), url=link_get("link_selfcheck")),
         InlineKeyboardButton(text=btn_text("btn_index"), callback_data="idx_home")],
        [InlineKeyboardButton(text=btn_text("btn_tools"), callback_data="tools_home"),
         InlineKeyboardButton(text=btn_text("btn_newcoin"), url=link_get("link_newcoin"))],
        [InlineKeyboardButton(text=btn_text("btn_coop"), callback_data="cooperation_info"),
         InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def idx_home_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="国家大行", callback_data="big_bank_list")],
        [InlineKeyboardButton(text="拼音 A-G", callback_data="idx_range:AG"),
         InlineKeyboardButton(text="拼音 H-Z", callback_data="idx_range:HZ")],
        [InlineKeyboardButton(text="\U0001F3E0 返回首页", callback_data="go_home")],
        [InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ])

def idx_page(range_key: str, letter: str) -> InlineKeyboardMarkup:
    items = INDEX_AZ.get(letter, [])
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for name, url in items:
        if url: row.append(InlineKeyboardButton(text=name, url=url))
        else: row.append(InlineKeyboardButton(text=name, callback_data=f"nolink:{name}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    letters = ["A","B","C","D","E","F","G"] if range_key=="AG" else ["H","J","K","L","N","P","Q","S","T","W","X","Y","Z"]
    nav: List[InlineKeyboardButton] = []
    for ch in letters:
        label = f"[{ch}]" if ch == letter else ch
        nav.append(InlineKeyboardButton(text=label, callback_data=f"idx:{range_key}:{ch}"))
        if len(nav) == 7: rows.append(nav); nav = []
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅ 返回索引", callback_data="idx_home"),
                 InlineKeyboardButton(text="🏠 返回首页", callback_data="go_home")])
    rows.append([InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def big_bank_menu() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    tmp: List[InlineKeyboardButton] = []
    for bank in BANK_DETAIL.keys():
        tmp.append(InlineKeyboardButton(text=bank, callback_data=f"bank:{bank}"))
        if len(tmp) == 2: rows.append(tmp); tmp = []
    if tmp: rows.append(tmp)
    rows.append([InlineKeyboardButton(text="⬅ 返回索引", callback_data="idx_home"),
                 InlineKeyboardButton(text="🏠 返回首页", callback_data="go_home")])
    rows.append([InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def bank_detail_menu(bank_name: str) -> InlineKeyboardMarkup:
    details = BANK_DETAIL.get(bank_name, [])
    rows: List[List[InlineKeyboardButton]] = [[InlineKeyboardButton(text=name, url=url)] for name, url in details]
    rows.append([InlineKeyboardButton(text="⬅ 返回国家大行", callback_data="big_bank_list"),
                 InlineKeyboardButton(text="🏠 返回首页", callback_data="go_home")])
    rows.append([InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def tools_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="空充图片演示", url=LINKS["tool_aircharge_pic"]),
         InlineKeyboardButton(text="空充视频演示", url=LINKS["tool_aircharge_video"])],
        [InlineKeyboardButton(text="云闪付一键查名下卡", url=LINKS["tool_ysf_query"]),
         InlineKeyboardButton(text="农信限额证书", url=LINKS["tool_nx_cert"])],
        [InlineKeyboardButton(text="北方农信说明", url=LINKS["tool_nx_north"]),
         InlineKeyboardButton(text="测卡流程", url=LINKS["flow_measure"])],
        [InlineKeyboardButton(text="发车准备", url=LINKS["flow_depart"]),
         InlineKeyboardButton(text="贷款资料汇总", url=LINKS["loan_hub"])],
        [InlineKeyboardButton(text="贷款·有用资料", url=LINKS["loan_useful"]),
         InlineKeyboardButton(text="线下新手对接", url=LINKS["docking_newbie"])],
        [InlineKeyboardButton(text="【新·结算规则】", url=LINKS["rule_settlement"]),
         InlineKeyboardButton(text="供卡供料规则", url=LINKS.get("rule_fleet", ""))],
        [InlineKeyboardButton(text="共享美区 Apple ID", url=LINKS["apple_id_us"]),
         InlineKeyboardButton(text="共享国区 Apple ID", url=LINKS["apple_id_cn"])],
        [InlineKeyboardButton(text="返回首页", callback_data="go_home"),
         InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ])

def cooperation_info_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="【新·结算规则】", url=LINKS.get("rule_settlement", ""))],
        [InlineKeyboardButton(text="【新·车队规则】", url=LINKS.get("rule_fleet", ""))],
        [InlineKeyboardButton(text="【新·常见问题】", url=LINKS.get("rule_common_material", "")),
         InlineKeyboardButton(text="【新·柜台规则】", url=LINKS.get("rule_half_insured_counter", ""))],
        [InlineKeyboardButton(text="【新·新手对接】", url=LINKS.get("docking_newbie", ""))],
        [InlineKeyboardButton(text="返回首页", callback_data="go_home")],
        [InlineKeyboardButton(text=btn_text("btn_contact"), callback_data="contact_menu")],
    ])

def contact_menu_kb() -> InlineKeyboardMarkup:
    defaults = [
        ("💳 阿宝(卡商)", "https://t.me/fyzf168858"),
        ("💎 钻石(柜台)", "https://t.me/HYZFzuanshi"),
        ("🚚 面条(直营车)", "https://t.me/ehk1722513463"),
        ("🛠 疑难杂症专线", "https://t.me/HYZFzuanshi"),
    ]
    rows: List[List[InlineKeyboardButton]] = []
    for i in range(1, 5):
        text = get_setting(f"contact{i}_text", defaults[i - 1][0])
        url = get_setting(f"contact{i}_url", defaults[i - 1][1])
        rows.append([InlineKeyboardButton(text=text, url=url)])
    rows.append([InlineKeyboardButton(text="返回首页", callback_data="go_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ========== 广告投放(快捷) ==========
def ad_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 联系客服", callback_data="ad_contact")],
        [InlineKeyboardButton(text="📢 关注频道", url=link_get("link_follow"))],
        [InlineKeyboardButton(text="❌ 关闭", callback_data="ad_close")],
    ])

# ========== 广告管理(分类/分页/FSM) ==========
class NewAd(StatesGroup):
    title = State()
    cat = State()
    photo = State()
    caption = State()
    url = State()
    confirm = State()

class EditAd(StatesGroup):
    field = State()
    value = State()
    cat = State()

def categories_list() -> List[sqlite3.Row]:
    c = db()
    try:
        return c.execute("SELECT id,name,sort FROM ad_categories ORDER BY sort ASC, id ASC").fetchall()
    finally:
        c.close()

def ad_count(cat_id: Optional[int] = None) -> int:
    c = db()
    try:
        if cat_id:
            row = c.execute("SELECT COUNT(*) AS c FROM ads WHERE category_id=?", (cat_id,)).fetchone()
        else:
            row = c.execute("SELECT COUNT(*) AS c FROM ads").fetchone()
        return row["c"] or 0
    finally:
        c.close()

def ads_page(page: int, per: int = 10, cat_id: Optional[int] = None) -> List[sqlite3.Row]:
    off = (max(page, 1) - 1) * per
    c = db()
    try:
        if cat_id:
            return c.execute("""SELECT a.*, coalesce(c.name,'未分类') as cat_name
                                FROM ads a LEFT JOIN ad_categories c ON a.category_id=c.id
                                WHERE a.category_id=? ORDER BY a.id DESC LIMIT ? OFFSET ?""",
                             (cat_id, per, off)).fetchall()
        return c.execute("""SELECT a.*, coalesce(c.name,'未分类') as cat_name
                            FROM ads a LEFT JOIN ad_categories c ON a.category_id=c.id
                            ORDER BY a.id DESC LIMIT ? OFFSET ?""", (per, off)).fetchall()
    finally:
        c.close()

def ad_add(title: str, caption: str, url: str, photo_file_id: str, category_id: Optional[int]) -> int:
    c = db()
    try:
        cur = c.cursor()
        cur.execute("""INSERT INTO ads(title, caption, url, photo_file_id, category_id, active)
                       VALUES(?,?,?,?,?,1)""", (title, caption, url, photo_file_id, category_id))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()

def ad_get(ad_id: int) -> Optional[sqlite3.Row]:
    c = db()
    try:
        return c.execute("""SELECT a.*, coalesce(c.name,'未分类') as cat_name
                            FROM ads a LEFT JOIN ad_categories c ON a.category_id=c.id
                            WHERE a.id=?""", (ad_id,)).fetchone()
    finally:
        c.close()

def ad_update(ad_id: int, **kwargs) -> None:
    if not kwargs: return
    cols = ", ".join(f"{k}=?" for k in kwargs.keys())
    vals = list(kwargs.values())
    vals.append(ad_id)
    c = db()
    try:
        c.execute(f"UPDATE ads SET {cols}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
        c.commit()
    finally:
        c.close()

def ad_del(ad_id: int) -> None:
    c = db()
    try:
        c.execute("DELETE FROM ads WHERE id=?", (ad_id,))
        c.commit()
    finally:
        c.close()

def kb_ad_list(page: int, total: int, cat_id: Optional[int]) -> InlineKeyboardMarkup:
    per = 10
    rows: List[List[InlineKeyboardButton]] = []
    # 行：每条广告一个“查看 #id”按钮(最多10条)
    data = ads_page(page, per, cat_id)
    for r in data:
        rows.append([InlineKeyboardButton(text=f"#{r['id']} {'✅' if r['active'] else '❌'} [{r['cat_name']}] {r['title'][:14]}",
                                          callback_data=f"ad:preview:{r['id']}")])
    # 分页与操作
    total_pages = (total + per - 1) // per if total else 1
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅ 上一页", callback_data=f"ad:list:{cat_id or 0}:{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="下一页 ➡", callback_data=f"ad:list:{cat_id or 0}:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="🆕 新建广告", callback_data="ad:new"),
                 InlineKeyboardButton(text="筛选分类", callback_data="ad:cats")])
    rows.append([InlineKeyboardButton(text="返回首页", callback_data="go_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_cats_for_pick(mode: str) -> InlineKeyboardMarkup:
    """mode=filter/pick"""
    rows: List[List[InlineKeyboardButton]] = []
    cats = categories_list()
    if mode == "filter":
        rows.append([InlineKeyboardButton(text="全部", callback_data="adcat:filter:0")])
    for r in cats:
        rows.append([InlineKeyboardButton(text=r["name"], callback_data=f"adcat:{mode}:{r['id']}")])
    rows.append([InlineKeyboardButton(text="⬅ 返回", callback_data="ad:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_ad_row(ad_id: int, active: int) -> InlineKeyboardMarkup:
    """
    生成广告管理行键盘，支持启停、编辑、删除、返回列表。
    active参数可用于后续扩展按钮状态。
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="启/停", callback_data=f"ad:toggle:{ad_id}"),
         InlineKeyboardButton(text="编辑", callback_data=f"ad:edit:{ad_id}")],
        [InlineKeyboardButton(text="删除", callback_data=f"ad:del:{ad_id}"),
         InlineKeyboardButton(text="⬅ 返回列表", callback_data="ad:home")],
    ])

def kb_back_home() -> InlineKeyboardMarkup:
    """
    生成返回管理和返回首页的键盘。
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ 返回管理", callback_data="ad:home")],
        [InlineKeyboardButton(text="🏠 返回首页", callback_data="go_home")],
    ])

def render_ad_cap(r: sqlite3.Row) -> str:
    """
    渲染广告标题和正文，自动去除多余空格。
    """
    head = f"<b>{r['title']}</b>\n"
    body = (r["caption"] or "").strip()
    return head + body

def get_cat_status(r: dict) -> str:
    """
    返回分类和状态字符串，兼容dict和Row类型。
    """
    cat = r.get('cat_name') if isinstance(r, dict) else r['cat_name']
    active = r.get('active') if isinstance(r, dict) else r['active']
    return f"分类:{cat}  状态:{'启用' if active else '停用'}"

def get_id(r):
    return f"#ID{r['id']}"

def build_text(head, body, tail):
    return head + (body if body else "") + tail

# ========== 命令 ==========
WELCOME_TEXT = (
    "<b>频道导航中心</b>\n"
    "关注频道即可解锁完整功能，核心资源一站直达。"
)

@dp.message(Command("start", "menu"))
async def cmd_start(m: Message):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().lower() == "gate":
        if await ensure_followed(m.from_user.id):
            await m.answer("已关注，功能已解锁。", reply_markup=main_menu(), disable_web_page_preview=True)
        else:
            await m.answer("请先关注频道后再继续：", reply_markup=follow_gate_kb(), disable_web_page_preview=True)
        return
    # 记录用户
    c = db()
    try:
        c.execute("INSERT OR IGNORE INTO user_meta(user_id, username, first_seen) VALUES(?,?,?)",
                  (m.from_user.id, (m.from_user.username or m.from_user.full_name), datetime.datetime.now()))
        c.commit()
    finally:
        c.close()
    await m.answer(WELCOME_TEXT, reply_markup=main_menu(), disable_web_page_preview=True)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    msg = (
        "<b>常用指令</b>\n"
        "/start /menu — 打开首页\n"
        "/owner_list | /owner_add 123 | /owner_del 123\n"
        "/set_btn 键 新文本(btn_follow/btn_index/btn_tools/btn_newcoin/btn_coop/btn_contact)\n"
        "/set_link 键 URL(link_selfcheck/link_follow/link_newcoin/tool_ysf_query 等)\n"
        "/set_channel @xxx 或 -100xxxx\n"
        "/post_panel | /update_panel | /del_panel\n"
        "/save_adpic(回复图片) | /set_adtext 文案 | /ad -100xxxx\n"
        "/admgr(广告管理) | /stats | /dump_settings | /load_settings(回复 JSON) | /export_db | /ping"
    )
    await m.reply(msg, disable_web_page_preview=True)

# 配置
@dp.message(Command("set_btn"))
async def cmd_set_btn(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        return await m.reply("用法:/set_btn 键 新文本\n键:btn_follow/btn_index/btn_tools/btn_newcoin/btn_coop/btn_contact")
    key, val = parts[1], parts[2].strip()
    if key not in BUTTON_KEYS_DEFAULT:
        return await m.reply("键无效。")
    if len(val) > 32 or "\n" in val:
        return await m.reply("建议<=32字且不含换行。")
    set_setting(key, val)
    await m.reply(f"✅ 已更新 {key} → {val}\n预览：", reply_markup=main_menu(), disable_web_page_preview=True)

@dp.message(Command("set_link"))
async def cmd_set_link(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(" ", 2)
    if len(parts) < 3: return await m.reply("用法:/set_link 键 URL")
    key, val = parts[1], parts[2].strip()
    set_setting(key, val)
    await m.reply(f"✅ 已更新 {key}")

@dp.message(Command("set_channel"))
async def cmd_set_channel(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(" ", 1)
    if len(parts) < 2: return await m.reply("用法:/set_channel @频道用户名 或 -100xxxx")
    set_setting("default_channel", parts[1].strip())
    await m.reply("✅ 已更新默认频道。")

# 放在其它 @dp.message(...) 之前更稳妥
from aiogram import F
import re, datetime, sqlite3

@dp.message(F.text.regexp(r"^(?:查询|查)\s*(.+)$"))
async def on_query_kw(m: types.Message):
    kw = re.search(r"^(?:查询|查)\s*(.+)$", m.text, re.I).group(1).strip()

    # 记查询日志(可选)
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute(
            "INSERT INTO query_log(user_id, keyword, created_at) VALUES(?,?,?)",
            (m.from_user.id, kw, datetime.datetime.now()),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 命中国家大行二级(支持简称)
    kw_norm = normalize_keyword(kw)
    for bank_name in BANK_DETAIL.keys():
        bn = bank_name.lower()
        if kw.lower() in bn or (kw_norm and kw_norm in bn):
            await m.reply(
                f"查询结果：<b>{bank_name}</b>\n请选择入口：",
                reply_markup=build_bank_detail_kb(bank_name),
                disable_web_page_preview=True,
            )
            return

    # A-Z 模糊(忽略“银行”二字)
    kw_s = kw.lower().replace("银行", "")
    hits = sorted({
        name for lst in INDEX_AZ.values()
        for name, _ in lst
        if kw_s in name.lower().replace("银行","")
    })

    if not hits:
        await m.reply("未找到相关条目。示例：<code>查询 中国银行</code> 或 <code>查询 成都</code>")
        return

    if len(hits) == 1 and hits[0] in BANK_DETAIL:
        await m.reply(
            f"查询结果：<b>{hits[0]}</b>\n请选择入口：",
            reply_markup=build_bank_detail_kb(hits[0]),
            disable_web_page_preview=True,
        )
        return

    await m.reply(
        "匹配到多项：\n" + "\n".join(f"- <code>{x}</code>" for x in hits[:20]),
        disable_web_page_preview=True,
    )

# 面板
@dp.message(Command("post_panel"))
async def cmd_post_panel(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    if not m.text:
        await m.reply("❌ 无效的命令输入，请直接发送 /post_panel")
        return
    parts = m.text.split(maxsplit=1)
    target = parts[1].strip() if len(parts) > 1 else get_setting("default_channel", DEFAULT_CHANNEL)
    try:
        sent = await bot.send_message(target, WELCOME_TEXT, reply_markup=main_menu(), disable_web_page_preview=True)
        chat = await bot.get_chat(target); panel_set(chat.id, sent.message_id)
        await m.reply(f"已发布到 {target} (msg_id={sent.message_id})，请去频道置顶。")
    except Exception as e:
        await m.reply(f"发布失败: {e}")

@dp.message(Command("update_panel"))
async def cmd_update_panel(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(maxsplit=1)
    target = parts[1].strip() if len(parts) > 1 else get_setting("default_channel", DEFAULT_CHANNEL)
    try:
        chat = await bot.get_chat(target); chat_id = chat.id
    except Exception:
        try: chat_id = int(target)
        except Exception: return await m.reply("目标无效。用法: /update_panel @channel 或 /update_panel -100xxx")
    msg_id = panel_get(chat_id)
    if not msg_id: return await m.reply("未找到面板记录，请先 /post_panel")
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=WELCOME_TEXT,
                                    reply_markup=main_menu(), disable_web_page_preview=True)
        await m.reply("已更新频道面板。")
    except Exception as e:
        await m.reply(f"更新失败: {e}")

@dp.message(Command("del_panel"))
async def cmd_del_panel(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(maxsplit=1)
    target = parts[1].strip() if len(parts) > 1 else get_setting("default_channel", DEFAULT_CHANNEL)
    try:
        chat = await bot.get_chat(target); chat_id = chat.id
    except Exception:
        try: chat_id = int(target)
        except Exception: return await m.reply("目标无效。用法: /del_panel @channel 或 /del_panel -100xxx")
    panel_del(chat_id); await m.reply("✅ 已删除面板记录。")

# 快捷广告投放
@dp.message(Command("save_adpic"))
async def cmd_save_adpic(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    if not m.reply_to_message or not (m.reply_to_message.photo or m.reply_to_message.document):
        return await m.reply("请“回复一张图片/海报”再发送 /save_adpic")
    file_id = (m.reply_to_message.photo[-1].file_id if m.reply_to_message.photo else m.reply_to_message.document.file_id)
    set_setting("ad_photo_file_id", file_id)
    await m.reply("✅ 已保存广告图片 file_id。之后可用 /ad -100xxxxxxxx 或 /ad @群用户名 发送。")

@dp.message(Command("set_adtext"))
async def cmd_set_adtext(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(" ", 1)
    if len(parts) < 2: return await m.reply("用法：/set_adtext 广告文案")
    set_setting("ad_text", parts[1].strip())
    await m.reply("✅ 已设置广告文案。")

@dp.message(Command("ad"))
async def cmd_send_ad(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2: return await m.reply("用法：/ad @群名 或 -100xxxx")
    target = parts[1].strip()
    file_id = get_setting("ad_photo_file_id")
    caption = get_setting("ad_text", "") or "供卡供料 · 柜台直招\n输入查询 + 关键词可模糊检索银行/城市/主题\n示例: 查询 中国银行 / 查询 成都"
    kb = ad_menu()
    # ...existing code...
    try:
        if file_id:
            await bot.send_photo(chat_id=target, photo=file_id, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(chat_id=target, text=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        await m.reply("✅ 已尝试发送广告。")
    except Exception as e:
        await m.reply(f"❌ 发送失败: {e}\n请确保机器人是该频道的管理员且有发帖权限。")

# 广告管理入口
@dp.message(Command("admgr"))
async def cmd_admgr(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    total = ad_count(None)
    await m.reply(f"广告管理(共 {total} 条)", reply_markup=kb_ad_list(1, total, None))

@dp.callback_query(F.data=="ad:home")
async def ad_home(cq: CallbackQuery):
    total=ad_count(None)
    await swap_view(cq, f"广告管理(共 {total} 条)", kb_ad_list(1,total,None))

@dp.callback_query(F.data.startswith("ad:list:"))
async def ad_list(cq: CallbackQuery):
    _,_,cat_raw,page_raw=cq.data.split(":")
    cat_id=int(cat_raw) if cat_raw!="0" else None
    page=max(1,int(page_raw)); total=ad_count(cat_id)
    await swap_view(cq, "广告列表：", kb_ad_list(page,total,cat_id))

@dp.callback_query(F.data=="ad:cats")
async def ad_choose_cat(cq: CallbackQuery):
    await swap_view(cq, "选择分类过滤：", kb_cats_for_pick("filter"))

@dp.callback_query(F.data.startswith("adcat:filter:"))
async def ad_filter(cq: CallbackQuery):
    cid=int(cq.data.split(":")[2]); total=ad_count(cid)
    await swap_view(cq, f"分类 {cid} 列表：", kb_ad_list(1,total,cid))

# 新建广告 FSM
@dp.callback_query(F.data=="ad:new")
async def ad_new_start(cq: CallbackQuery, state:FSMContext):
    await state.set_state(NewAd.title)
    await swap_view(cq, "发送广告标题：", kb_back_home())

@dp.message(NewAd.title)
async def ad_new_title(m: Message, state:FSMContext):
    await state.update_data(title=m.text.strip())
    await state.set_state(NewAd.cat)
    await m.reply("选择分类：", reply_markup=kb_cats_for_pick("pick"))

@dp.callback_query(F.data.startswith("adcat:pick:"), NewAd.cat)
async def ad_new_pick_cat(cq: CallbackQuery, state:FSMContext):
    cid=int(cq.data.split(":")[2]); await state.update_data(category_id=cid)
    await state.set_state(NewAd.photo)
    await swap_view(cq, "发送图片或 /skip 跳过：", kb_back_home())

@dp.message(NewAd.photo, F.text=="/skip")
async def ad_new_skip_photo(m: Message, state:FSMContext):
    await state.update_data(photo_file_id=""); await state.set_state(NewAd.caption)
    await m.reply("发送文案(HTML 可用)或 /skip：")

@dp.message(NewAd.photo, F.photo)
async def ad_new_photo(m: Message, state:FSMContext):
    await state.update_data(photo_file_id=m.photo[-1].file_id); await state.set_state(NewAd.caption)
    await m.reply("发送文案(HTML 可用)或 /skip：")

@dp.message(NewAd.caption, F.text=="/skip")
async def ad_new_skip_caption(m: Message, state:FSMContext):
    await state.update_data(caption=""); await state.set_state(NewAd.url)
    await m.reply("发送按钮 URL 或 /skip：")

@dp.message(NewAd.caption)
async def ad_new_caption(m: Message, state:FSMContext):
    await state.update_data(caption=m.html_text or m.text); await state.set_state(NewAd.url)
    await m.reply("发送按钮 URL 或 /skip：")

@dp.message(NewAd.url, F.text=="/skip")
async def ad_new_skip_url(m: Message, state:FSMContext):
    data=await state.get_data(); await state.set_state(NewAd.confirm)
    text = f"将创建广告：\n<b>{data.get('title','')}</b>\n分类ID: {data.get('category_id')}"
    if data.get("caption"):
        text += f"\n{data['caption']}"
    if data.get("url"):
        text += f"\n按钮URL: <code>{data['url']}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ 保存", callback_data="ad:save_new"),
                                                InlineKeyboardButton(text="❌ 取消", callback_data="ad:cancel_new")]])
    await m.reply(text, reply_markup=kb)

@dp.message(NewAd.url)
async def ad_new_url(m: Message, state:FSMContext):
    await state.update_data(url=m.text.strip()); data=await state.get_data()
    await state.set_state(NewAd.confirm)
    text = f"将创建广告：\n<b>{data.get('title','')}</b>\n分类ID: {data.get('category_id')}"
    if data.get("caption"):
        text += f"\n{data['caption']}"
    if data.get("url"):
        text += f"\n按钮URL: <code>{data['url']}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ 保存", callback_data="ad:save_new"),
                                                InlineKeyboardButton(text="❌ 取消", callback_data="ad:cancel_new")]])
    await m.reply(text, reply_markup=kb)

@dp.callback_query(F.data=="ad:save_new", NewAd.confirm)
async def ad_new_save(cq: CallbackQuery, state:FSMContext):
    d=await state.get_data()
    ad_id=ad_add(d.get("title",""), d.get("caption",""), d.get("url",""), d.get("photo_file_id",""), d.get("category_id"))
    await state.clear()
    r=ad_get(ad_id)
    await swap_view(cq, f"已创建 #{ad_id}", kb_ad_row(ad_id, r["active"]))

@dp.callback_query(F.data=="ad:cancel_new", NewAd.confirm)
async def ad_new_cancel(cq: CallbackQuery, state:FSMContext):
    await state.clear()
    await swap_view(cq, "已取消。", kb_ad_list(1,ad_count(None),None))

# 预览/启停/编辑/删除
@dp.callback_query(F.data.startswith("ad:preview:"))
async def ad_preview(cq: CallbackQuery):
    ad_id=int(cq.data.split(":")[2]); r=ad_get(ad_id)
    if not r: return await cq.answer("不存在", show_alert=True)
    try:
        if r["photo_file_id"]:
            await bot.send_photo(chat_id=cq.message.chat.id, photo=r["photo_file_id"],
                                 caption=render_ad_cap(r), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                     InlineKeyboardButton(text="👉 点此", url=r["url"] if r["url"] else "https://t.me")
                                 ], [InlineKeyboardButton(text="⬅ 返回管理", callback_data=f"ad:edit:{r['id']}")]]))
        else:
            await bot.send_message(chat_id=cq.message.chat.id, text=render_ad_cap(r),
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="👉 点此", url=r["url"] if r["url"] else "https://t.me")
                                   ], [InlineKeyboardButton(text="⬅ 返回管理", callback_data=f"ad:edit:{r['id']}")]]))
    except TelegramBadRequest:
        await cq.message.reply(render_ad_cap(r))
    await cq.answer()

@dp.callback_query(F.data.startswith("ad:toggle:"))
async def ad_toggle(cq: CallbackQuery):
    ad_id=int(cq.data.split(":")[2]); r=ad_get(ad_id)
    if not r: return await cq.answer("不存在", show_alert=True)
    ad_update(ad_id, active=0 if r["active"] else 1); r2=ad_get(ad_id)
    await swap_view(cq, render_ad_cap(r2), kb_ad_row(ad_id, r2["active"]))
    await cq.answer("已切换")

@dp.callback_query(F.data.startswith("ad:edit:"))
async def ad_edit_menu(cq: CallbackQuery, state:FSMContext):
    ad_id=int(cq.data.split(":")[2]); r=ad_get(ad_id)
    if not r: return await cq.answer("不存在", show_alert=True)
    await state.set_state(EditAd.field); await state.update_data(ad_id=ad_id)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="标题", callback_data="edit:title"),
         InlineKeyboardButton(text="文案", callback_data="edit:caption")],
        [InlineKeyboardButton(text="按钮URL", callback_data="edit:url"),
         InlineKeyboardButton(text="图片", callback_data="edit:photo")],
        [InlineKeyboardButton(text="分类", callback_data="edit:cat")],
        [InlineKeyboardButton(text="⬅ 返回", callback_data=f"ad:preview:{ad_id}")]
    ])
    await swap_view(cq, render_ad_cap(r), kb)

@dp.callback_query(F.data.startswith("edit:"), EditAd.field)
async def ad_edit_pick(cq: CallbackQuery, state:FSMContext):
    field=cq.data.split(":")[1]
    await state.update_data(field=field)
    if field=="title":
        await state.set_state(EditAd.value); await swap_view(cq, "发送新标题：", kb_back_home())
    elif field=="caption":
        await state.set_state(EditAd.value); await swap_view(cq, "发送新文案(HTML 可用)：", kb_back_home())
    elif field=="url":
        await state.set_state(EditAd.value); await swap_view(cq, "发送新按钮URL(留空则删除)：", kb_back_home())
    elif field=="photo":
        await state.set_state(EditAd.value); await swap_view(cq, "发送新图片，或发送 /clear 清空图片：", kb_back_home())
    elif field=="cat":
        await state.set_state(EditAd.cat); await swap_view(cq, "选择新分类：", kb_cats_for_pick("pick"))
    else:
        await cq.answer("无效字段", show_alert=True)

@dp.message(EditAd.value, F.text & ~F.text.in_({"/clear"}))
async def ad_edit_value_text(m: Message, state:FSMContext):
    d=await state.get_data(); field=d.get("field"); ad_id=d.get("ad_id")
    val=m.html_text or m.text
    if field in {"title","caption","url"}:
        ad_update(ad_id, **{field: val})
        await m.reply("✅ 已更新。", reply_markup=kb_ad_row(ad_id, ad_get(ad_id)["active"]))
        await state.clear()
    else:
        await m.reply("当前字段需要图片或 /clear 操作。")

@dp.message(EditAd.value, F.text == "/clear")
async def ad_edit_value_clear(m: Message, state:FSMContext):
    d=await state.get_data(); field=d.get("field"); ad_id=d.get("ad_id")
    if field=="photo":
        ad_update(ad_id, photo_file_id="")
        await m.reply("✅ 已清空图片。", reply_markup=kb_ad_row(ad_id, ad_get(ad_id)["active"]))
        await state.clear()
    else:
        await m.reply("只有图片字段支持 /clear。")

@dp.message(EditAd.value, F.photo)
async def ad_edit_value_photo(m: Message, state:FSMContext):
    d=await state.get_data(); field=d.get("field"); ad_id=d.get("ad_id")
    if field=="photo":
        ad_update(ad_id, photo_file_id=m.photo[-1].file_id)
        await m.reply("✅ 已更新图片。", reply_markup=kb_ad_row(ad_id, ad_get(ad_id)["active"]))
        await state.clear()
    else:
        await m.reply("请按提示选择字段后再发送。")

@dp.callback_query(EditAd.cat, F.data.startswith("adcat:pick:"))
async def ad_edit_value_cat(cq: CallbackQuery, state:FSMContext):
    ad_id=(await state.get_data()).get("ad_id")
    cid=int(cq.data.split(":")[2]); ad_update(ad_id, category_id=cid)
    await state.clear()
    await swap_view(cq, "✅ 分类已更新。", kb_ad_row(ad_id, ad_get(ad_id)["active"]))

@dp.callback_query(F.data.startswith("ad:del:"))
async def ad_del_one(cq: CallbackQuery):
    ad_id=int(cq.data.split(":")[2]); r=ad_get(ad_id)
    if not r: return await cq.answer("不存在", show_alert=True)
    ad_del(ad_id)
    await swap_view(cq, "✅ 已删除。", kb_ad_list(1, ad_count(None), None))

# 统计/导出/健康
@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    c=db()
    try:
        users = c.execute("SELECT COUNT(*) FROM user_meta").fetchone()[0]
        total_q = c.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        rows = c.execute("SELECT DATE(created_at) d, COUNT(*) c FROM query_log WHERE created_at>=DATE('now','-6 day') GROUP BY d ORDER BY d").fetchall()
        last7 = "\n".join(f"{r['d']}: {r['c']}" for r in rows)
        await m.reply(f"📈 统计\n用户数: {users}\n查询总量: {total_q}\n近7天:\n{last7}")
    except Exception as e:
        await m.reply(f"统计失败: {e}")
    finally:
        c.close()

@dp.message(Command("dump_settings"))
async def cmd_dump_settings(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    c=db()
    try:
        rows=c.execute("SELECT key,value FROM settings").fetchall()
        settings={r["key"]: r["value"] for r in rows}
        await m.reply(f"<pre>{json.dumps(settings, ensure_ascii=False, indent=2)}</pre>", parse_mode="HTML")
    finally:
        c.close()

@dp.message(Command("load_settings"))
async def cmd_load_settings(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    if not m.reply_to_message or not m.reply_to_message.text: return await m.reply("请在回复包含 JSON 的消息下使用 /load_settings")
    try:
        data=json.loads(m.reply_to_message.text)
        if not isinstance(data, dict): raise ValueError
    except Exception:
        return await m.reply("JSON 格式错误。")
    for k,v in data.items(): set_setting(k,v)
    await m.reply("✅ 已导入配置。")

@dp.message(Command("export_db"))
async def cmd_export_db(m: Message):
    if not is_owner(m.from_user.id): return await m.reply("无权限：仅 OWNER 可执行。")
    await m.answer_document(FSInputFile(DB_FILE), caption=f"DB 备份：{DB_FILE}")

@dp.message(Command("ping"))
async def cmd_ping(m: Message):
    uptime = datetime.datetime.now() - START_TIME
    await m.reply(f"pong! 运行时长：{uptime}")

# ========== 回调：普通 ==========
@dp.callback_query(F.data == "go_home")
async def cb_go_home(cq: CallbackQuery):
    await swap_view(cq, WELCOME_TEXT, main_menu())

@dp.callback_query(F.data == "tools_home")
async def cb_open_tools(cq: CallbackQuery):
    await swap_view(cq, "📚 发车工具合集", tools_home_kb())

@dp.callback_query(F.data == "cooperation_info")
async def cb_open_coop(cq: CallbackQuery):
    await swap_view(cq, "合作须知\n\n规则与常见问题入口如下:", cooperation_info_kb())

@dp.callback_query(F.data == "contact_menu")
async def cb_open_contact(cq: CallbackQuery):
    await swap_view(cq, "客服直达(选择入口)", contact_menu_kb())

@dp.callback_query(F.data == "idx_home")
async def cb_idx_home(cq: CallbackQuery):
    await swap_view(cq, "测卡索引\n请选择类别:", idx_home_menu())

@dp.callback_query(F.data == "big_bank_list")
async def cb_big_bank(cq: CallbackQuery):
    await swap_view(cq, "国家大行列表：", big_bank_menu())

@dp.callback_query(lambda cq: cq.data and cq.data.startswith("bank:"))
async def cb_bank_detail(cq: CallbackQuery):
    _, bank_name = cq.data.split(":", 1)
    await swap_view(cq, f"{bank_name} 相关入口：", bank_detail_menu(bank_name))

@dp.callback_query(lambda cq: cq.data and cq.data.startswith("idx_range:"))
async def cb_idx_range(cq: CallbackQuery):
    range_key = cq.data.split(":", 1)[1]
    letter = "A" if range_key == "AG" else "H"
    await swap_view(cq, f"索引 {range_key} - {letter}", idx_page(range_key, letter))

@dp.callback_query(lambda cq: cq.data and cq.data.startswith("idx:"))
async def cb_idx_letter(cq: CallbackQuery):
    _, range_key, letter = cq.data.split(":")
    await swap_view(cq, f"索引 {range_key} - {letter}", idx_page(range_key, letter))

@dp.callback_query(F.data.startswith("nolink:"))
async def cb_nolink_tip(cq: CallbackQuery):
    name = cq.data.split(":", 1)[1]
    await cq.answer(f"{name} 暂无链接。", show_alert=True)

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cq: CallbackQuery):
    if await ensure_followed(cq.from_user.id):
        await cq.message.answer("已关注，功能已解锁。", reply_markup=main_menu(), disable_web_page_preview=True)
    else:
        await cq.message.answer("还未关注频道，请先点击“去关注频道”。", show_alert=True)

# 广告公共回调
@dp.callback_query(F.data == "ad_contact")
async def cb_ad_contact(cq: CallbackQuery):
    await swap_view(cq, "客服直达(选择入口)", contact_menu_kb())

@dp.callback_query(F.data == "ad_close")
async def cb_ad_close(cq: CallbackQuery):
    try:
        await cq.message.delete()
    except Exception:
        pass
    await cq.answer()

# ========== 主函数 ==========
async def on_startup() -> None:
    init_db()
    commands = [
        BotCommand(command="start", description="打开首页/订阅闸门"),
        BotCommand(command="menu", description="打开首页"),
        BotCommand(command="help", description="查看帮助"),
        BotCommand(command="admgr", description="广告管理"),
    ]
    await bot.set_my_commands(commands)

async def main() -> None:
    await on_startup()
    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")


# ===== helper: 国家大行二级菜单键盘(缺失则自动补) =====
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton as _IKB

def build_bank_detail_kb(bank_name: str) -> InlineKeyboardMarkup:
    detail = BANK_DETAIL.get(bank_name, [])
    rows = []
    for i in range(0, len(detail), 2):
        row = []
        for j in range(2):
            if i + j < len(detail):
                t, u = detail[i + j]
                row.append(_IKB(text=t, url=u))
        if row:
            rows.append(row)
    rows.append([_IKB(text="⬅ 返回首页", callback_data="go_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



@dp.message(Command("clear_adpic"))
async def cmd_clear_adpic(m: Message):
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    set_setting("ad_photo_file_id","")
    await m.reply("✅ 已清空快捷广告图片 file_id。之后 /ad 将只发文本。")


@dp.message(Command("chktgt"))
async def cmd_chktgt(m: Message):
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    parts=m.text.split(maxsplit=1)
    if len(parts)<2: return await m.reply("用法：/chktgt @用户名 或 -100xxxx")
    tgt=parts[1].strip()
    try:
        chat = await bot.get_chat(tgt)
        await m.reply(f"✅ 目标可用: {chat.title or chat.id}\nchat_id=<code>{chat.id}</code>")
    except Exception as e:
        await m.reply(f"❌ 目标不可用: {e}\n请确认机器人已加入并有发帖权限。")

@dp.message(Command("adbtn"))
async def cmd_adbtn(m: Message):
    # 用法：/adbtn 1 新文案   (1=客服 2=关注 3=关闭)
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3 or parts[1] not in {"1","2","3"}:
        return await m.reply("用法：/adbtn 1 新文案   (1=客服 2=关注 3=关闭)")
    set_setting(f"adbtn{parts[1]}_text", parts[2].strip())
    await m.reply("已更新按钮文案。之后发送的新广告将使用新文案。")

@dp.message(Command("adbtn_url"))
async def cmd_adbtn_url(m: Message):
    # 用法：/adbtn_url 1 https://...   或   /adbtn_url 2 https://...
    # 1号设置 URL 的同时，会把 1 号切到 url 模式(直链)
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3 or parts[1] not in {"1","2"}:
        return await m.reply("用法：/adbtn_url 1 https://...   或   /adbtn_url 2 https://...")
    idx, url = parts[1], parts[2].strip()
    set_setting(f"adbtn{idx}_url", url)
    if idx == "1":
        set_setting("adbtn1_type", "url")
    await m.reply("已更新 URL。")

@dp.message(Command("adbtn_menu"))
async def cmd_adbtn_menu(m: Message):
    # 把 1 号按钮切回菜单模式(点击打开客服菜单)
    if not is_owner(m.from_user.id):
        return await m.reply("无权限：仅 OWNER 可执行。")
    set_setting("adbtn1_type", "menu")
    await m.reply("1号按钮已切回菜单模式。")


# ====== 自定义关键词快捷菜单 ======
CUSTOM_QUERY_MENUS = {
    "电销话术": {
        "title": "📞 电销话术模板合集",
        "desc": "建议收藏常用话术，灵活应对客户问题。",
        "buttons": [
            ("📄 文字模板", "https://t.me/c/2025069980/25"),
            ("🎧 话术录音", "https://t.me/c/2025069980/137"),
            ("📋 交单格式", "https://t.me/c/2025069980/134"),
            ("❌ 扣单标准", "https://t.me/c/2025069980/26"),
        ],
    },
    "贷款话术": {
        "title": "💰 贷款话术与引流资料",
        "desc": "包括大纲、话术模板、引流技巧等。",
        "buttons": [
            ("📄 大纲1", "https://t.me/c/2025069980/45"),
            ("📄 大纲2", "https://t.me/c/2025069980/60"),
            ("🧲 引流方式", "https://t.me/c/2025069980/49"),
            ("📚 包装合同", "https://t.me/c/2025069980/61"),
        ],
    },
    "避税话术": {
        "title": "🧾 避税话术合集",
        "desc": "请合法合规使用，仅供学习参考。",
        "buttons": [
            ("📄 兼职避税", "https://t.me/c/2025069980/71"),
            ("📄 工程避税", "https://t.me/c/2025069980/132"),
            ("📄 避税1", "https://t.me/c/2025069980/145"),
            ("📄 避税2", "https://t.me/c/2025069980/87"),
        ],
    },
    "朋友圈文案": {
        "title": "🗣️ 朋友圈文案合集",
        "desc": "素材更新中，建议保存。",
        "buttons": [
            ("📲 文案1-8", "https://t.me/c/2025069980/91"),
            ("📲 文案9-16", "https://t.me/c/2025069980/98"),
            ("📲 文案17-23", "https://t.me/c/2025069980/100"),
        ],
    },
    "测卡教程": {
        "title": "📚 测卡教程 & 公户标准",
        "desc": "全网最全教程合集，请按需查看。",
        "buttons": [
            ("🧰 百宝箱总入口", "https://t.me/BLQnX6H5oBgyZjhl/738"),
            ("🔠 A-G模板", "https://t.me/BLQnX6H5oBgyZjhl/138"),
            ("🔠 H-Z模板", "https://t.me/BLQnX6H5oBgyZjhl/139"),
            ("🏢 公户标准", "https://t.me/BLQnX6H5oBgyZjhl/831"),
        ],
    },
    "结算规则": {
        "title": "💼 卡商结算规则汇总",
        "desc": "适用于发车、供卡、柜台操作。",
        "buttons": [
            ("📋 结算规则", "https://t.me/BLQnX6H5oBgyZjhl/124"),
            ("🚚 车队规则", "https://t.me/BLQnX6H5oBgyZjhl/871"),
            ("📦 供料规则", "https://t.me/BLQnX6H5oBgyZjhl/186"),
        ],
    },
}

@dp.message()
async def handle_custom_queries(m: Message):
    kw = m.text or ""
    kw_lower = kw.lower().strip()

    for key, menu in CUSTOM_QUERY_MENUS.items():
        if key in kw_lower:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=text, url=url)] for text, url in menu["buttons"]
                ] + [[InlineKeyboardButton(text="🏠 返回首页", callback_data="go_home")]]
            )
        await m.answer(f"<b>{menu['title']}</b>\n{menu['desc']}", reply_markup=keyboard, parse_mode="HTML")
        return

    # fallback 提示
    await m.answer("🤖 未识别关键词，请尝试发送：\n电销话术 / 贷款话术 / 朋友圈文案 等")



# ========== 主菜单键盘 ==========
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 电销话术", callback_data="kw_电销话术")],
            [InlineKeyboardButton(text="🗣️ 朋友圈文案", callback_data="kw_朋友圈文案")],
            [InlineKeyboardButton(text="🧾 避税话术", callback_data="kw_避税话术")],
            [InlineKeyboardButton(text="📚 测卡教程", callback_data="kw_测卡教程")],
            [InlineKeyboardButton(text="💼 结算规则", callback_data="kw_结算规则")],
        ]
    )

# ========== /start ==========
@dp.message(Command("start"))
async def cmd_start(m: Message):
    user = m.from_user
    logging.info(f"[START] {user.id} {user.full_name} ({user.username})")
    await m.answer(
        "🤖 欢迎使用关键词菜单机器人！请点击下方按钮选择服务：",
        reply_markup=main_menu_kb()
    )

# ========== /help ==========
@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("发送关键词，如：电销话术、朋友圈文案、贷款话术，即可获取相关资料。")

# ========== /menu ==========
@dp.message(Command("menu"))
async def cmd_menu(m: Message):
    await m.answer("📋 主菜单：", reply_markup=main_menu_kb())

# ========== /推广 ==========
@dp.message(Command("推广"))
async def cmd_promo(m: Message):
    await m.answer("📢 推广素材包：https://t.me/c/2025069980/999")

# ========== 关键词快捷按钮回调 ==========
@dp.callback_query(F.data.startswith("kw_"))
async def callback_keyword_button(cq: CallbackQuery):
    keyword = cq.data.replace("kw_", "")
    fake_message = types.Message(
        message_id=cq.message.message_id,
        date=cq.message.date,
        chat=cq.message.chat,
        text=keyword
    )
    await handle_custom_queries(fake_message)
    await cq.answer()

# ========== 关注频道限制 ==========
async def ensure_followed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(DEFAULT_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramNetworkError:
        return False
    except Exception as e:
        logging.warning(f"Follow check error: {e}")
        return False

def follow_gate_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 关注主频道", url=f"https://t.me/c/{DEFAULT_CHANNEL.replace('-100', '')}")],
        [InlineKeyboardButton(text="✅ 我已关注，继续", callback_data="check_sub")]
    ])

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(cq: CallbackQuery):
    is_subscribed = await ensure_followed(cq.from_user.id)
    if is_subscribed:
        await cq.message.answer("✅ 已检测到你已关注，现在可以使用菜单了：", reply_markup=main_menu_kb())
    else:
        await cq.message.answer("⚠️ 尚未关注频道，请先关注：", reply_markup=follow_gate_kb())

# ========== 启动时设定命令 ==========
@dp.startup()
async def on_startup(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="启动菜单"),
        BotCommand(command="help", description="使用说明"),
        BotCommand(command="menu", description="关键词菜单"),
        BotCommand(command="推广", description="推广素材链接"),
    ])



# ========== 自动推送功能(定时发送菜单或信息到频道) ==========

import asyncio
from aiogram import asyncio as aio_asyncio
from aiogram.enums import ParseMode

async def scheduled_broadcast():
    while True:
        try:
            msg = (
                "📢 <b>每日关键词菜单更新</b>\n"
                "发送以下任一关键词获取资料：\n"
                "- 电销话术\n"
                "- 朋友圈文案\n"
                "- 贷款话术\n"
                "- 避税话术\n"
                "- 测卡教程\n"
                "- 结算规则\n"
                "\n点击菜单按钮或直接发送关键词获取内容 ⤵️"
            )
            await bot.send_message(
                chat_id=DEFAULT_CHANNEL,
                text=msg,
                reply_markup=main_menu_kb(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logging.info("[推送成功] 每日菜单已发送至频道")
        except Exception as e:
            logging.warning(f"[推送失败] {e}")

        await asyncio.sleep(86400)  # 每 24 小时推送一次(秒)

@dp.startup()
async def start_broadcast_loop(bot: Bot):
    aio_asyncio.create_task(scheduled_broadcast())



# ========== 📢 广告系统模块 ==========
from aiogram.types import InputMediaPhoto
from datetime import datetime
import sqlite3

DB_FILE = os.getenv("DB_FILE", "./ad_tracking.db")

# 初始化点击追踪数据库
def init_ad_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ad_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            ad_id TEXT,
            button_label TEXT,
            clicked_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_ad_db()

# 广告发送函数
async def send_ad(chat_id, text, buttons, ad_id="ad_001", photo=None):
    inline_buttons = [
        [InlineKeyboardButton(text=btn["text"], url=btn.get("url"), callback_data=btn.get("callback_data"))]
        for btn in buttons
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    if photo:
        await bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=markup, parse_mode="HTML")
    else:
        await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

    logging.info(f"[广告已发送] {ad_id} 到 {chat_id}")

# 回调点击追踪
@dp.callback_query(F.data.startswith("ad_"))
async def track_ad_click(cq: CallbackQuery):
    user = cq.from_user
    ad_id = cq.data.split("_", 2)[-1]
    label = cq.data  # 可扩展成按钮标识

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO ad_clicks (user_id, username, ad_id, button_label, clicked_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        user.id,
        user.username,
        ad_id,
        label,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    await cq.answer("✅ 点击已记录")
    logging.info(f"[广告点击] user={user.id}, ad={ad_id}, label={label}")

# 广告报表
@dp.message(Command("报表"))
async def ad_report(m: Message):
    args = m.text.split()
    if len(args) < 2:
        await m.answer("❗ 用法：/报表 广告ID")
        return
    ad_id = args[1]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT button_label, COUNT(*) FROM ad_clicks WHERE ad_id=? GROUP BY button_label", (ad_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await m.answer(f"📊 广告 [{ad_id}] 暂无点击数据")
        return
    msg = f"📊 广告 [{ad_id}] 报告：\n"
    total = 0
    for label, count in rows:
        msg += f"- {label}: {count} 次\n"
        total += count
    msg += f"总点击数：{total} 次"
    await m.answer(msg)



# ========== 👥 客服自动转接 ==========
SUPPORT_STAFF_IDS = [123456789, 987654321]  # 替换为你自己的客服 Telegram user_id
last_assigned = 0

async def assign_support():
    global last_assigned
    user_id = SUPPORT_STAFF_IDS[last_assigned % len(SUPPORT_STAFF_IDS)]
    last_assigned += 1
    return user_id

@dp.callback_query(F.data.startswith("ad_contact_"))
async def ad_contact_router(cq: CallbackQuery):
    assigned_id = await assign_support()
    await bot.send_message(
        assigned_id,
        f"📞 有用户请求联系广告客服：@{cq.from_user.username or cq.from_user.full_name}(ID: {cq.from_user.id})"
    )
    await cq.message.answer("👤 已为你分配专属客服，TA将尽快联系你！")
    await cq.answer()

# ========== 📁 广告模板保存与重用 ==========
AD_TEMPLATE_FILE = "ad_templates.json"

def load_templates():
    import json
    if Path(AD_TEMPLATE_FILE).exists():
        return json.loads(Path(AD_TEMPLATE_FILE).read_text(encoding="utf-8"))
    return {}

def save_templates(templates):
    import json
    Path(AD_TEMPLATE_FILE).write_text(json.dumps(templates, indent=2, ensure_ascii=False), encoding="utf-8")

@dp.message(Command("保存广告"))
async def save_ad_template(m: Message):
    args = m.text.split(maxsplit=2)
    if len(args) < 3:
        await m.answer("用法：/保存广告 广告ID 广告文本")
        return

    ad_id, ad_text = args[1], args[2]
    templates = load_templates()
    templates[ad_id] = {"text": ad_text, "buttons": []}
    save_templates(templates)
    await m.answer(f"✅ 广告模板 [{ad_id}] 已保存")

@dp.message(Command("模板列表"))
async def list_ad_templates(m: Message):
    templates = load_templates()
    if not templates:
        await m.answer("📭 暂无已保存模板")
        return
    msg = "📁 当前模板列表：\n"
    for ad_id in templates:
        msg += f"- {ad_id}\n"
    await m.answer(msg)

# ========== 🎯 推送频率限制 ==========
last_sent_times = {}

async def can_send_ad(ad_id, cooldown_seconds=3600):
    now = datetime.utcnow().timestamp()
    last_time = last_sent_times.get(ad_id, 0)
    if now - last_time >= cooldown_seconds:
        last_sent_times[ad_id] = now
        return True
    return False

@dp.message(Command("推送广告"))
async def manual_send_ad(m: Message):
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        await m.answer("用法：/推送广告 广告ID")
        return

    ad_id = args[1]
    if not await can_send_ad(ad_id):
        await m.answer("⏱ 此广告近期已推送，稍后再试")
        return

    templates = load_templates()
    if ad_id not in templates:
        await m.answer("❌ 未找到该广告模板")
        return

    await send_ad(
        chat_id=DEFAULT_CHANNEL,
        text=templates[ad_id]["text"],
        buttons=[
            {"text": "🛒 查看详情", "url": "https://yoururl.com?utm=" + ad_id},
            {"text": "👤 联系客服", "callback_data": f"ad_contact_{ad_id}"}
        ],
        ad_id=ad_id
    )
    await m.answer("✅ 广告已推送")
