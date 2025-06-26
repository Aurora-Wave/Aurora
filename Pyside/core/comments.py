
class EMSComment:
    """
    Represents a physiological comment (annotation) in a recording.
    Includes timing, source channel, raw text, and metadata to assist with
    navigation, editing, and labeling.
    """

    def __init__(self, text, tick_position, channel, comment_id, tick_dt, time_sec, user_defined=False):
        self.text = text                    # Original comment text (raw from LabChart)
        self.tick_position = tick_position  # Index of the sample tick
        self.channel = channel              # Associated channel name or index
        self.comment_id = comment_id        # Unique ID (local to file)
        self.tick_dt = tick_dt              # Tick duration (s)
        self.time = time_sec                # Absolute time (s)
        self.user_defined = user_defined    # Whether this comment was added manually by the user

    def to_dict(self):
        """
        Return the comment as a dictionary, useful for table display or export.
        """
        return {
            "id": self.comment_id,
            "text": self.text,
            "channel": self.channel,
            "time_sec": self.time,
            "user_defined": self.user_defined
        }

    def update(self, text=None, time=None, label=None):
        """
        Update comment text, time (e.g. after user correction).
        """
        if text is not None:
            self.text = text
        if time is not None:
            self.time = time
        if label is not None:
            self.label = label

    def __repr__(self):
        tag = "(user)" if self.user_defined else ""
        return f"EMSComment(id={self.comment_id}, time={self.time:.2f}s, label='{self.label}' {tag}, text='{self.text}')"
