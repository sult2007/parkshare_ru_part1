class RefreshToken:
    @classmethod
    def for_user(cls, user):
        return cls()

    def __str__(self):
        return "stub-token"

    @property
    def access_token(self):
        return "stub-access"
