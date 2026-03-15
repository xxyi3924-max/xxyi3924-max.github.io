from .options_flow import options_flow
from .insider_tracker import insider_tracker
from .price_action import price_action
from .social_buzz import social_buzz
from .institutional_positioning import institutional_positioning
from .dark_pool import dark_pool

SKILL_MAP = {
    "options_flow_scanner":      lambda args: options_flow(args["ticker"]),
    "social_buzz_scanner":       lambda args: social_buzz(args["ticker"]),
    "insider_tracker":           lambda args: insider_tracker(args["ticker"]),
    "price_action_context":      lambda args: price_action(args["ticker"]),
    "institutional_positioning": lambda args: institutional_positioning(args["ticker"]),
    "dark_pool_activity":        lambda args: dark_pool(args["ticker"]),
}


def execute_skill(tool_name: str, tool_args: dict):
    if tool_name not in SKILL_MAP:
        raise ValueError(f"Unknown tool: {tool_name}")
    return SKILL_MAP[tool_name](tool_args)
