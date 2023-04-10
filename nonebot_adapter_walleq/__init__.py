from .nonebot_adapter_walleq import WalleQ
from nonebot.adapters.onebot.v12 import Adapter as V12Adapter
from nonebot.adapters.onebot.v12 import Bot, StatusUpdateMetaEvent, MetaEvent, BotEvent
from nonebot.adapters.onebot.v12.utils import msgpack_encoder
from nonebot.typing import overrides
from nonebot.drivers import Driver
from nonebot import get_driver
from typing import Any, Optional, Dict, cast, Union, Literal
from nonebot.utils import logger_wrapper, escape_tag
from nonebot import require
import msgpack
import asyncio

bots: Dict[str, Bot] = {}
log = logger_wrapper("Walle-Q")
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

data_dir = store.get_data_dir("walle_q")


async def _call_data(data: bytes):
    driver = get_driver()
    if wq := driver._adapters.get("Walle-Q"):
        if isinstance(wq, Adapter):
            raw_data = msgpack.unpackb(data)
            if event := wq.json_to_event(raw_data, "Walle-Q"):
                if isinstance(event, StatusUpdateMetaEvent):
                    for bot_status in event.status.bots:
                        self_id = bot_status.self.user_id
                        platform = bot_status.self.platform
                        if not bot_status.online:
                            if bot := bots.get(self_id):
                                if bots is not None:
                                    bots.pop(self_id, None)
                                wq.driver._bot_disconnect(bot)
                                log(
                                    "INFO",
                                    f"<y>Bot {escape_tag(self_id)}</y> disconnected",
                                )
                        elif self_id not in bots:
                            bot = Bot(wq, self_id, "Walle-Q", platform)
                            # 先尝试连接，如果失败则不保存连接信息
                            wq.driver._bot_connect(bot)
                            # 正向与反向 WebSocket 连接需要额外保存连接信息
                            if bots is not None:
                                bots[self_id] = bot
                            log(
                                "INFO",
                                f"<y>Bot {escape_tag(self_id)}</y> connected",
                            )
                if isinstance(event, MetaEvent):
                    for bot in bots.values():
                        asyncio.create_task(bot.handle_event(event))
                else:
                    event = cast(BotEvent, event)
                    self_id = event.self.user_id
                    bot = bots.get(self_id)
                    if not bot:
                        bot = Bot(wq, self_id, "Walle-Q", event.self.platform)
                        wq.bot_connect(bot)
                        bots[self_id] = bot
                        # wq.connections[self_id] = websocket
                        log(
                            "INFO",
                            f"<y>Bot {escape_tag(event.self.user_id)}</y> connected",
                        )
                    asyncio.create_task(bot.handle_event(event))


class Adapter(V12Adapter):
    @overrides(V12Adapter)
    def __init__(self, driver: Driver, **kwargs: Any) -> None:
        self.driver = driver
        self._config = Config(**self.config.dict())
        data_path: str = (
            self._config.walle_q_data_path
            if self._config.walle_q_data_path
            else str(data_dir)
        )
        self.inner: WalleQ = WalleQ(
            self._config.walle_q_leveldb,
            self._config.walle_q_sled,
            data_path,
        )
        self.timeout: Optional[float] = driver.config.api_timeout

        async def run(wq: WalleQ, data_path: str):
            await wq.run(data_path, "./log")

        @driver.on_startup
        async def _():
            asyncio.create_task(run(self.inner, data_path))
            await asyncio.sleep(0.5)
            for id, config in self._config.walle_q.items():
                r = LoginResp.parse_obj(
                    await self._call_meta_api(
                        "login",
                        bot_id=id,
                        protocol=config.protocol,
                        password=config.password,
                    )
                )
                if r.qrcode_str:
                    log("INFO", f"登录 bot: {r.bot_id} 中，扫码登录：")
                    print(r.qrcode_str)
                elif r.url:
                    log("INFO", f"登录 bot: {r.bot_id} 中, need captcha url: {r.url}")
                    print(f"input ticket:", end="")
                    ticket = input()
                    print(ticket)
                    await self._call_meta_api(
                        "submit_ticket", bot_id=r.bot_id, ticket=ticket
                    )

    @classmethod
    @overrides(V12Adapter)
    def get_name(cls) -> str:
        return "Walle-Q"

    @overrides(V12Adapter)
    async def _call_api(self, bot: Bot, api: str, **data: Any) -> Any:
        timeout: float = data.get("_timeout", self.timeout)
        seq = self._result_store.get_seq()
        action_data = {
            "action": api,
            "params": data,
            "self": {"platform": bot.platform, "user_id": bot.self_id},
            "echo": str(seq),
        }
        b: Optional[bytes] = msgpack.packb(action_data, default=msgpack_encoder)
        if self.inner:
            self.inner.call_api(b)
        else:
            raise ValueError("walle-q not running")
        try:
            return self._handle_api_result(await self._result_store.fetch(seq, timeout))
        except asyncio.TimeoutError:
            raise TimeoutError(f"Walle-Q call api {api} timeout")

    async def _call_meta_api(self, api: str, **data: Any) -> Any:
        timeout: float = data.get("_timeout", self.timeout)
        seq = self._result_store.get_seq()
        action_data = {
            "action": api,
            "params": data,
            "echo": str(seq),
        }
        b: Optional[bytes] = msgpack.packb(action_data, default=msgpack_encoder)
        if self.inner:
            self.inner.call_api(b)
        else:
            raise ValueError("walle-q not running")
        try:
            return self._handle_api_result(await self._result_store.fetch(seq, timeout))
        except asyncio.TimeoutError:
            raise TimeoutError(f"Walle-Q call api {api} timeout")


from pydantic import BaseModel


class QQConfig(BaseModel):
    password: Optional[str]
    protocol: Optional[int]


class Config(BaseModel):
    walle_q: Dict[str, QQConfig]
    walle_q_leveldb: Optional[bool]
    walle_q_sled: Optional[bool]
    walle_q_data_path: Optional[str]


class LoginResp(BaseModel):
    bot_id: str
    url: Optional[str]
    qrcode: Optional[bytes]
    qrcode_str: Optional[str]
