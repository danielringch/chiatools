import psutil
from typing import DefaultDict, OrderedDict
from .resourceevaluator import Resourceevaluator
from ...core import Plugin, Alert, Config

class Sysmonitor(Plugin):
    def __init__(self, config, scheduler, outputs):
        config_data = Config(config)
        name, _ = config_data.get_value_or_default('sysmonitor', 'name')
        super(Sysmonitor, self).__init__(name, outputs)
        self.print(f'Plugin sysmonitor; name: {name}')

        mute_interval, _ = config_data.get_value_or_default(24, 'alert_mute_interval')

        self.__evaluators = {}
        self.__alerts = {}
        self.__prefixes = {'load' : 'Load', 'ram' : 'RAM usage', 'swap' : 'Swap usage'}

        self.__add_resource(config_data.data, 'load', mute_interval)
        self.__add_resource(config_data.data, 'ram', mute_interval)
        self.__add_resource(config_data.data, 'swap', mute_interval)

        self.print(f'Monitored resources: {",".join(self.__evaluators.keys())}')

        scheduler.add_job(f'{name}-check' ,self.check, config_data.get_value_or_default('* * * * *', 'interval')[0])

    async def check(self):
        load = await self.__check_resource('load', self.__get_load)
        ram = await self.__check_resource('ram', self.__get_ram_usage)
        swap = await self.__check_resource('swap', self.__get_swap_usage)

        resource_strings = []

        if load is not None:
            resource_strings.append(f'{self.__prefixes["load"]}: {load:.2f}')
        if ram is not None:
            resource_strings.append(f'{self.__prefixes["ram"]}: {ram:.0f} %')
        if swap is not None:
            resource_strings.append(f'{self.__prefixes["swap"]}: {swap:.0f} %')

        if len(resource_strings) == 0:
            await self.send(Plugin.Channel.debug, 'No resources to monitor.')
        else:
            await self.send(Plugin.Channel.debug, ' | '.join(resource_strings))

    def __add_resource(self, config, key, mute_interval):
        if key not in config:
            return
        self.__evaluators[key] = Resourceevaluator(config[key])
        self.__alerts[key] = Alert(super(Sysmonitor, self), mute_interval)

    async def __check_resource(self, key, getter):
        if key not in self.__evaluators:
            return None
        evaluator = self.__evaluators[key]
        percent = getter()
        prefix = self.__prefixes[key]
        evaluator.update(percent)
        if evaluator.treshold_exceeded:
            await self.__alerts[key].send(f'{prefix} is high: {percent:.2f} avg.')
        else:
            await self.__alerts[key].reset(f'{prefix} is under treshold again.')
        return percent


    def __get_ram_usage(self):
        ram = psutil.virtual_memory()
        return (ram.total - ram.available) / ram.total * 100.0

    def __get_swap_usage(self):
        return psutil.swap_memory().percent

    def __get_load(self):
        return psutil.getloadavg()[0]
