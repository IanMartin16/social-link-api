from __future__ import annotations

class HealthService:

    @staticmethod
    def check_application():

        return "operational", None

    @staticmethod
    def check_runtime():

        return "operational", None

    @classmethod
    def dependency_checks(cls):

        application_status, application_error = cls.check_application()
        runtime_status, runtime_error = cls.check_runtime()

        overall = "operational"

        if (
            application_status != "operational"
            or runtime_status != "operational"
        ):
            overall = "degraded"

        return {
            "status": overall,
            "checks": {
                "application": {
                    "status": application_status,
                    "error": application_error,
                },
                "runtime": {
                    "status": runtime_status,
                    "error": runtime_error,
                },
            },
        }

    @classmethod
    def is_ready(cls):

        return (
            cls.dependency_checks()["status"]
            == "operational"
        )