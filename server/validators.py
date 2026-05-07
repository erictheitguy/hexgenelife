import logging

logger = logging.getLogger("Server.Validator")

class MessageValidator:
    @staticmethod
    def validate_message(message: dict, command_type: str) -> bool:
        """Validates message structure against schema rules."""
        required_fields = {
            "MOVE_MOB": ["mobId", "targetLocation"],
            "REQUEST_WORLD_STATE": ["clientId"],
            "LOOK": ["mobId"],
            "EAT_GRASS": ["mobId"],
            "ATTACK_MOB": ["mobId", "targetId"],
            "EAT_MOB": ["mobId", "targetId"],
            "BREED": ["mobId", "targetId"],
            "REQUEST_BRAIN_FUNCTIONS": [],
        }

        payload = message.get("payload", message.get("data", {}))

        if command_type in required_fields:
            for field in required_fields[command_type]:
                alt_field = "".join(
                    ["_" + c.lower() if c.isupper() else c for c in field]
                ).lstrip("_")
                if field not in payload and alt_field not in payload:
                    logger.warning(f"Validation Error: Missing '{field}' for '{command_type}'.")
                    return False

        # Strict integer coordinates for MOVE_MOB
        if command_type == "MOVE_MOB":
            target_loc = (
                payload.get("targetLocation")
                or payload.get("target_location")
                or payload.get("new_pos")
            )
            if target_loc:
                if not isinstance(target_loc, dict):
                    logger.warning("Validation Error: 'targetLocation' must be an object.")
                    return False
                x = target_loc.get("x")
                y = target_loc.get("y")
                if not isinstance(x, int) or not isinstance(y, int):
                    print(
                        f"Validation Error: Coordinates must be integers. "
                        f"Received x={type(x).__name__}, y={type(y).__name__}"
                    )
                    return False
        return True
