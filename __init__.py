# инициализация плагина
def classFactory(iface):
    from .main_plugin import EcoMonitoringPlugin
    return EcoMonitoringPlugin(iface)