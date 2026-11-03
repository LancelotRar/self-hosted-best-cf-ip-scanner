"""panel —— 项目专属运维面板的后端。

模块分工：
    settings      运行时路径与开关（全部来自环境变量，可注入）
    app           FastAPI 应用工厂
    其余模块按任务逐步加入：db / security / config_store / docker_api / routers ...
"""
