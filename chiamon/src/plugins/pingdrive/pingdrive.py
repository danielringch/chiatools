import subprocess, re
from collections import defaultdict
from ...core import Plugin, Alert, Config
from .drive import Drive

class Pingdrive(Plugin):

    def __init__(self, config, scheduler, outputs):
        config_data = Config(config)
        name, _ = config_data.get_value_or_default('pingdrive', 'name')
        super(Pingdrive, self).__init__(name, outputs)
        self.print(f'Plugin pingdrive; name: {name}')

        self.__alerts = {}
        alert_mute_intervall = config_data.get_value_or_default(24, 'alert_mute_interval')[0]
        self.__drive_configs = {}
        self.__drives = {}

        for drive_block in config_data.data['drives']:
            for alias, drive_config in drive_block.items():
                self.__alerts[alias] = Alert(super(Pingdrive, self), alert_mute_intervall)
                drive_config['alias'] = alias
                self.__drive_configs[drive_config['mount_point']] = drive_config
  
        self.__first_summary = True

        scheduler.add_job(f'{name}-check', self.check, '* * * * *')
        scheduler.add_job(f'{name}-rescan' ,self.rescan, config_data.get_value_or_default('0 * * * *', 'rescan_intervall')[0])
        scheduler.add_job(f'{name}-summary', self.summary, config_data.get_value_or_default('0 0 * * *', 'summary_interval')[0])
        scheduler.add_job(f'{name}-startup', self.rescan, None)

    async def check(self):
        messages = []
        for drive in self.__drives.values():
            messages.append(drive.check())
            if drive.online:
                await self.__alerts[drive.alias].reset(f'{drive.alias} is online again')
            else:
                await self.__alerts[drive.alias].send(f'{drive.alias} is offline')
        await self.send(Plugin.Channel.debug, '\n'.join(messages))

    async def summary(self):
        online = 0
        inactive = 0
        offline = 0
        for drive in self.__drives.values():
            if not drive.online:
                offline += 1
            else:
                real_active = drive.active_minutes - drive.pings
                expected_active = drive.expected_active_minutes
                if not self.__first_summary and real_active < expected_active:
                    await self.send(Plugin.Channel.alert, f'{drive.alias} was too inactive: {real_active}/{expected_active} minutes')
                    inactive += 1
                else:
                    online += 1
            drive.reset_statistics()
        await self.send(Plugin.Channel.info, f'Drives (online, inactive, offline):\n{online} | {inactive} | {offline}')
        self.__first_summary = False

    async def rescan(self):
        drives = self.__get_drives();
        for device, mounts in drives.items():
            if device not in self.__drives:
                for mount in mounts:
                    if mount in self.__drive_configs:
                        self.__drives[device] = Drive(device, self.__drive_configs[mount])

    def __get_drives(self):
        lsblk_output = subprocess.run(["lsblk","-o" , "KNAME,MOUNTPOINT"], text=True, stdout=subprocess.PIPE)
        drive_pattern = re.compile("sd\\D+")
        drives = defaultdict(set)
        for line in lsblk_output.stdout.splitlines():
            parts = re.split("[ \\t]+", line)
            if (len(parts) != 2) or len(parts[1]) == 0:
                continue
            device_match = drive_pattern.search(parts[0])
            if not device_match:
                continue
            device = device_match.group(0)
            mountpoint = parts[1]
            drives[device].add(mountpoint)
        return drives
