from typing import Dict


class ChatService:
    def __init__(self):
        # user_id -> partner_id
        self.pairs: Dict[int, int] = {}

    def connect_users(self, user1: int, user2: int):
        self.pairs[user1] = user2
        self.pairs[user2] = user1

    def get_partner(self, user_id: int) -> int | None:
        return self.pairs.get(user_id)

    def disconnect(self, user_id: int):
        partner = self.pairs.get(user_id)
        if partner:
            self.pairs.pop(partner, None)
        self.pairs.pop(user_id, None)
