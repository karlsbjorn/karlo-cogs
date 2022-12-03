player_classes = [
    "warrior",
    "hunter",
    "mage",
    "priest",
    "rogue",
    "druid",
    "paladin",
    "warlock",
    "shaman",
    "monk",
    "demon_hunter",
    "death_knight",
    "evoker",
]

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
    "tank": ["protection", "guardian", "brewmaster", "blood", "vengeance"],
    "healer": ["holy", "restoration", "mistweaver", "discipline", "preservation"],
}
