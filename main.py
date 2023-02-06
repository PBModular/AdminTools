from base.module import BaseModule, ModuleInfo
from base.mod_ext import ModuleExtension
from typing import Type

# Extensions
from .ban import BanExtension
from .mute import MuteExtension


class AdminModule(BaseModule):
    @property
    def module_info(self) -> ModuleInfo:
        return ModuleInfo(
            name="AdminTools",
            author="SanyaPilot",
            version="0.0.1",
            src_url="https://github.com/PBModular/admin_tools_module"
        )

    @property
    def module_extensions(self) -> list[Type[ModuleExtension]]:
        return [
            BanExtension,
            MuteExtension
        ]
