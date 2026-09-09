"""兼容旧导入路径，配置统一维护在 config.py。"""

from config import ProductionConfig


config = {
    'production': ProductionConfig,
    'default': ProductionConfig,
}
