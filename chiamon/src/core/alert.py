from .plugin import Plugin
import datetime

class Alert:
    def __init__(self, plugin, mute_interval, tolerance=0):
        self.__plugin = plugin
        self.__mute_interval = datetime.timedelta(hours=mute_interval) if mute_interval is not None else None
        self.__tolerance = tolerance
        self.__tolerance_remaining = tolerance
        self.__current_mute = None

    async def send(self, message, key=None):
        if self.is_muted(key):
            await self.__plugin.send(Plugin.Channel.debug,
                f'Alert muted until {self.__current_mute[1]}:\n{message}')
            return
        if self.__tolerance_remaining > 0:
            self.__tolerance_remaining -= 1
            await self.__plugin.send(Plugin.Channel.debug, 
                f'Alert tolerated, {self.__tolerance_remaining} time(s) remaining:\n{message}')
            return
        self.mute(key)
        await self.__plugin.send(Plugin.Channel.alert, message) 

    async def reset(self, message=None):
        if self.__tolerance_remaining < self.__tolerance:
            self.__tolerance_remaining = self.__tolerance
            await self.__plugin.send(Plugin.Channel.debug, 
                f'Alert tolerance reset:\n{message}')
        if self.__current_mute is None or self.__current_mute[1] < datetime.datetime.now():
            return;
        self.__current_mute = None
        if message is not None:
            await self.__plugin.send(Plugin.Channel.alert, message) 
        else:
            await self.__plugin.send(Plugin.Channel.debug, f'Alert reset without message')

    def is_muted(self, key=None):
        if self.__current_mute is None:
            return False
        if self.__current_mute[0] != key:
            return False
        now = datetime.datetime.now()
        return self.__current_mute[1] >= now

    def mute(self, key=None):
        if self.__mute_interval is not None:
            now = datetime.datetime.now()
            self.__current_mute = (key, now + self.__mute_interval)
