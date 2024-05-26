import re


class Utils:
    @staticmethod
    def generate_entity_id(line: str):
        """Generate Entity Id from string."""
        return re.sub(r"[^a-zA-Z0-9]+", "_", line).lower()
