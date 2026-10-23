from health_signal.auth import User


class AllowAll:
    def install(self, app):  # no login routes needed for the test
        pass

    async def current_user(self, request):
        return User(email="t@test")


class DenyAll:
    def install(self, app):
        pass

    async def current_user(self, request):
        return None
