from enum import Enum


class PlayerClasses(Enum):
    """Enum for player classes"""

    warrior: str = "Warrior"
    hunter: str = "Hunter"
    mage: str = "Mage"
    priest: str = "Priest"
    rogue: str = "Rogue"
    druid: str = "Druid"
    paladin: str = "Paladin"
    warlock: str = "Warlock"
    shaman: str = "Shaman"
    monk: str = "Monk"
    demon_hunter: str = "Demon Hunter"
    death_knight: str = "Death Knight"
    evoker: str = "Evoker"


player_specs = {
    "warrior": {"arms", "fury", "protection"},
    "hunter": {"beast_mastery", "marksmanship", "survival"},
    "mage": {"arcane", "fire", "frost"},
    "priest": {"discipline", "holy", "shadow"},
    "rogue": {"assassination", "outlaw", "subtlety"},
    "druid": {"balance", "feral", "guardian", "restoration"},
    "paladin": {"holy", "protection", "retribution"},
    "warlock": {"affliction", "demonology", "destruction"},
    "shaman": {"elemental", "enhancement", "restoration"},
    "monk": {"brewmaster", "mistweaver", "windwalker"},
    "demon_hunter": {"havoc", "vengeance"},
    "death_knight": {"blood", "frost", "unholy"},
    "evoker": {"preservation", "devastation"},
}

spec_roles = {
    "tank": ["protection", "guardian", "brewmaster", "blood"],
    "healer": ["holy", "restoration", "mistweaver", "discipline", "preservation"],
}
