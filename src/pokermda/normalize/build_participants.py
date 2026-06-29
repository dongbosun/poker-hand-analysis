"""Insert participants."""

from __future__ import annotations

from pokermda.model.participant import Participant
from pokermda.utils.hashing import stable_id


def insert_participants(connection, hand_id: str, participants: list[Participant]) -> int:
    inserted = 0
    for participant in participants:
        participant_id = stable_id("participant", hand_id, participant.seat_no, participant.player_name)
        hole_cards = (participant.hole_cards or "").split()
        hole_card_1 = hole_cards[0] if len(hole_cards) >= 1 else None
        hole_card_2 = hole_cards[1] if len(hole_cards) >= 2 else None
        position = participant.position or participant.player_name.replace(" [ME]", "")
        exists = connection.execute(
            "SELECT 1 FROM participants WHERE hand_id = ? AND seat_no = ?",
            [hand_id, participant.seat_no],
        ).fetchone()
        if exists:
            continue
        connection.execute(
            """
            INSERT INTO participants (
                participant_id, hand_id, seat_no, player_name_raw,
                anonymized_player_label, position, is_hero, is_pool,
                starting_stack_bb, net_bb, hole_card_1, hole_card_2,
                hole_combo_1326, hole_class_169,
                player_name, stack, hole_cards, net_result
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                participant_id,
                hand_id,
                participant.seat_no,
                participant.player_name,
                "Hero" if participant.is_hero else f"Villain{participant.seat_no}",
                position,
                participant.is_hero,
                not participant.is_hero,
                participant.stack,
                participant.net_result,
                hole_card_1,
                hole_card_2,
                participant.hole_cards,
                _hole_class_169(hole_card_1, hole_card_2),
                participant.player_name,
                participant.stack,
                participant.hole_cards,
                participant.net_result,
            ],
        )
        inserted += 1
    return inserted


def _hole_class_169(card_1: str | None, card_2: str | None) -> str | None:
    if not card_1 or not card_2:
        return None
    rank_1, suit_1 = card_1[0], card_1[1]
    rank_2, suit_2 = card_2[0], card_2[1]
    order = "AKQJT98765432"
    ranks = sorted([rank_1, rank_2], key=lambda rank: order.index(rank))
    if rank_1 == rank_2:
        return rank_1 + rank_2
    suffix = "s" if suit_1 == suit_2 else "o"
    return "".join(ranks) + suffix
