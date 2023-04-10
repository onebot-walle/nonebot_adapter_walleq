# nonebot-adapter-walleq

<img alt="PyPI" src="https://img.shields.io/pypi/v/nonebot-adapter-walleq"> <img alt="GitHub" src="https://img.shields.io/github/license/onebot-walle/nonebot_adapter_walleq">

直接在你的 [Nonebot2](https://github.com/nonebot/nonebot2) 内置 [Walle-Q](https://github.com/onebot-walle/walle-q) ，他甚至不需要通过 Onebot Connect！

由于本适配器直接继承于 Onebot V12 ，所以所有适配 Onebot V12 的插件可以直接适配本适配器！

## 可配置项

- walle_q: Dict 登陆的账号，例子：
  ``` json
  {
    "0": {             //密码登录时必须为 qq 号
      "protocol": 2,   // watch
      "password": null // 留空则使用扫码登录
    }
  }
  ```
- walle_q_leveldb: bool 是否启用 leveldb
- walle_q_sled：bool 是否启用 sled
- walle_q_data_path: str 数据存储路径，默认将使用localstore

## 特别鸣谢

[Nonebot2](https://github.com/nonebot/nonebot2)：跨平台 PYTHON 异步机器人框架

[Walle-Q](https://github.com/onebot-walle/walle-q)：Onebot 12 QQ 协议实现（我谢我自己）