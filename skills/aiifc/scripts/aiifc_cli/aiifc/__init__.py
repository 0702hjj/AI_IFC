"""aiifc —— IFC 建模 CLI 薄壳（flows 脚本的 agent 可执行入口）。

纪律（同 aidxfv3/aiplan CLI）：薄壳无业务逻辑；lazy import（import 放函数体内）；
JSON in / JSON out；退出码 0 通过 / 1 FAIL / 2 SchemaError。

定位：aiifc 的 flows 脚本（design_builder / build_script_template / dxf_from_design /
consume_upstream）原本是独立 python 脚本——agent 的 execute 白名单按第一个 token 精确匹配
（aiplan/aidxfv3），`python xxx.py` 跑不了。本 CLI 把它们包成 `aiifc <cmd>`（console_scripts），
白名单加 `aiifc` 即可在 agent 里跑（与 aidxfv3/aiplan 形态对齐）。

flows 模块定位：aiifc skill 根下 `references/docs/flows/`（import 路径经 CLI 内部注入）。
"""
