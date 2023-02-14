from base.module import BaseModule
from base.mod_ext import ModuleExtension
from typing import Type

# Extensions
from .extensions.ban import BanExtension
from .extensions.mute import MuteExtension
from .extensions.purge import PurgeExtension


class AdminModule(BaseModule):
    @property
    def module_extensions(self) -> list[Type[ModuleExtension]]:
        return [
            BanExtension,
            MuteExtension,
            PurgeExtension
        ]
