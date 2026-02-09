
import json
import os
import logging
from typing import Set

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_file: str = "data/state.json"):
        self.state_file = state_file
        self.visited_ids: Set[str] = set()
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.visited_ids = set(data.get('visited_ids', []))
                logger.info(f"Loaded {len(self.visited_ids)} visited IDs from state.")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        else:
            logger.info("No existing state found. Starting fresh.")

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'visited_ids': list(self.visited_ids)
                }, f, ensure_ascii=False, indent=2)
            logger.info("State saved.")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def is_visited(self, bid_id: str) -> bool:
        return bid_id in self.visited_ids

    def mark_visited(self, bid_id: str):
        self.visited_ids.add(bid_id)
