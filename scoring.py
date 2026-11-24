"""Ten-pin frame scoring, bonus rolls, symbols, and achievements."""


class Scorecard:
    def __init__(self):
        self.frames = [[] for _ in range(10)]
        self.current_frame = 0
        self.game_over = False
        self.last_frame_complete = False
        self.reset_rack_after_roll = False
        self.achievements = {"gobble_gobble": False, "perfect_game": False}
        self.last_event = ""

    @property
    def rolls(self):
        return [pins for frame in self.frames for pins in frame]

    def record_roll(self, pins_down: int) -> str:
        """Record one roll and return a notification event, if one was earned."""
        if self.game_over:
            return ""
        pins_down = max(0, min(10, int(pins_down)))
        self.last_event = ""
        self.last_frame_complete = False
        self.reset_rack_after_roll = False
        frame_index = self.current_frame
        frame = self.frames[frame_index]

        if frame_index < 9:
            if not frame:
                frame.append(pins_down)
                if pins_down == 10:
                    self.last_frame_complete = True
                    self.current_frame += 1
            else:
                pins_down = min(pins_down, 10 - frame[0])
                frame.append(pins_down)
                self.last_frame_complete = True
                self.current_frame += 1
        elif not frame:
            frame.append(pins_down)
            # A tenth-frame strike earns two bonus rolls on fresh racks.
            self.reset_rack_after_roll = pins_down == 10
        elif len(frame) == 1:
            first = frame[0]
            max_pins = 10 if first == 10 else 10 - first
            pins_down = min(pins_down, max_pins)
            frame.append(pins_down)
            if first == 10 or first + pins_down == 10:
                # The tenth frame remains open for its bonus roll.
                self.reset_rack_after_roll = first != 10 or pins_down == 10
            else:
                self.last_frame_complete = True
                self.game_over = True
                self.current_frame = 10
        else:
            first, second = frame[:2]
            max_pins = 10 - second if first == 10 and second < 10 else 10
            pins_down = min(pins_down, max_pins)
            frame.append(pins_down)
            self.last_frame_complete = True
            self.game_over = True
            self.current_frame = 10

        all_rolls = self.rolls
        if len(all_rolls) >= 3 and all(value == 10 for value in all_rolls[-3:]):
            self.achievements["gobble_gobble"] = True
            self.last_event = "TURKEY"
        if self.game_over and self.total_score == 300:
            self.achievements["perfect_game"] = True
            self.last_event = "PERFECT_GAME"
        return self.last_event

    def frame_symbol(self, frame_index: int) -> str:
        """Return compact roll marks for a score-board frame cell."""
        if not 0 <= frame_index < 10:
            return ""
        frame = self.frames[frame_index]
        if not frame:
            return ""
        symbol = lambda pins: "-" if pins == 0 else str(pins)
        if frame_index < 9:
            if frame[0] == 10:
                return "X"
            if len(frame) == 1:
                return symbol(frame[0])
            if sum(frame[:2]) == 10:
                return symbol(frame[0]) + "/"
            return symbol(frame[0]) + symbol(frame[1])

        first = frame[0]
        result = "X" if first == 10 else symbol(first)
        if len(frame) == 1:
            return result
        second = frame[1]
        if first == 10:
            result += "X" if second == 10 else symbol(second)
        else:
            result += "/" if first + second == 10 else symbol(second)
        if len(frame) == 3:
            third = frame[2]
            if first == 10 and second < 10 and second + third == 10:
                result += "/"
            else:
                result += "X" if third == 10 else symbol(third)
        return result

    @property
    def cumulative_scores(self):
        """Cumulative totals by frame; None means a bonus is still pending."""
        scores = [None] * 10
        rolls = self.rolls
        roll_index = 0
        cumulative = 0
        for frame_index in range(9):
            frame = self.frames[frame_index]
            if not frame or roll_index >= len(rolls):
                break
            first = rolls[roll_index]
            if first == 10:
                if roll_index + 2 >= len(rolls):
                    break
                points = 10 + rolls[roll_index + 1] + rolls[roll_index + 2]
                roll_index += 1
            else:
                if roll_index + 1 >= len(rolls):
                    break
                second = rolls[roll_index + 1]
                if first + second == 10:
                    if roll_index + 2 >= len(rolls):
                        break
                    points = 10 + rolls[roll_index + 2]
                else:
                    points = first + second
                roll_index += 2
            cumulative += points
            scores[frame_index] = cumulative

        final_frame = self.frames[9]
        if self.game_over and len(final_frame) >= 2:
            cumulative += sum(final_frame)
            scores[9] = cumulative
        return scores

    @property
    def total_score(self) -> int:
        known_scores = [score for score in self.cumulative_scores if score is not None]
        return known_scores[-1] if known_scores else 0

    def display_total(self) -> str:
        return f"Score: {self.total_score}"
