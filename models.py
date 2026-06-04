from dataclasses import dataclass

@dataclass
class Partition:
    index: int
    hex: str
    bootable: bool
    type: str
    offset: int
