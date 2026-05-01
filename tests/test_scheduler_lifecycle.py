import asyncio
import importlib
import sys
import types
import unittest
from types import SimpleNamespace


class FakeBackgroundScheduler:
    def __init__(self):
        self.jobs = []
        self.started = False

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append({"func": func, "trigger": trigger, "kwargs": kwargs})

    def start(self):
        self.started = True


class FakeManagedScheduler:
    def __init__(self):
        self.shutdown_calls = []

    def shutdown(self, wait=False):
        self.shutdown_calls.append(wait)


class FakeFastAPI:
    def __init__(self, title: str, lifespan=None):
        self.title = title
        self.routers = []
        self.exception_handlers = []
        self.middlewares = []
        self.lifespan = lifespan
        self.state = SimpleNamespace()

    def include_router(self, router):
        self.routers.append(router)

    def add_exception_handler(self, exception_class_or_status_code, handler):
        self.exception_handlers.append({"exception": exception_class_or_status_code, "handler": handler})

    def middleware(self, middleware_type):
        def decorator(func):
            self.middlewares.append({"type": middleware_type, "handler": func})
            return func

        return decorator


def install_modules(testcase: unittest.TestCase, modules: dict[str, types.ModuleType]):
    originals = {name: sys.modules.get(name) for name in modules}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)
    sys.modules.update(modules)


class SchedulerLifecycleTests(unittest.TestCase):
    def test_start_scheduler_registers_daily_memory_job(self):
        fake_job = object()
        background_module = types.ModuleType("apscheduler.schedulers.background")
        background_module.BackgroundScheduler = FakeBackgroundScheduler

        jobs_module = types.ModuleType("app.scheduler.jobs")
        jobs_module.daily_memory_job = fake_job

        install_modules(
            self,
            {
                "apscheduler.schedulers.background": background_module,
                "app.scheduler.jobs": jobs_module,
            },
        )
        sys.modules.pop("app.scheduler.scheduler", None)

        scheduler_module = importlib.import_module("app.scheduler.scheduler")
        scheduler = scheduler_module.start_scheduler()

        self.assertTrue(scheduler.started)
        self.assertEqual(len(scheduler.jobs), 1)
        self.assertIs(scheduler.jobs[0]["func"], fake_job)
        self.assertEqual(scheduler.jobs[0]["trigger"], "interval")
        self.assertEqual(scheduler.jobs[0]["kwargs"]["hours"], 24)
        self.assertEqual(scheduler.jobs[0]["kwargs"]["id"], "daily_memory_job")
        self.assertTrue(scheduler.jobs[0]["kwargs"]["replace_existing"])

    def test_main_lifespan_manages_scheduler(self):
        scheduler = FakeManagedScheduler()
        init_db_calls = []

        fastapi_module = types.ModuleType("fastapi")
        fastapi_module.FastAPI = FakeFastAPI

        database_module = types.ModuleType("app.db.database")

        def init_db():
            init_db_calls.append("called")

        database_module.init_db = init_db

        scheduler_module = types.ModuleType("app.scheduler.scheduler")
        scheduler_module.start_scheduler = lambda: scheduler

        errors_module = types.ModuleType("app.core.errors")

        def register_error_handlers(app):
            app.add_exception_handler("registered", "handler")

        errors_module.register_error_handlers = register_error_handlers

        request_context_module = types.ModuleType("app.core.request_context")

        def register_request_context_middleware(app):
            @app.middleware("http")
            async def request_context_middleware(request, call_next):
                return await call_next(request)

        request_context_module.register_request_context_middleware = register_request_context_middleware

        route_modules = {}
        for name in [
            "app.api.routes_health",
            "app.api.routes_chat",
            "app.api.routes_memory",
            "app.api.routes_sessions",
            "app.api.routes_agents",
            "app.api.routes_openai_compat",
            "app.api.routes_diagnostics",
            "app.api.routes_tools",
        ]:
            module = types.ModuleType(name)
            module.router = object()
            route_modules[name] = module

        install_modules(
            self,
            {
                "fastapi": fastapi_module,
                "app.db.database": database_module,
                "app.scheduler.scheduler": scheduler_module,
                "app.core.errors": errors_module,
                "app.core.request_context": request_context_module,
                **route_modules,
            },
        )
        sys.modules.pop("app.main", None)

        main_module = importlib.import_module("app.main")

        async def run_lifespan():
            async with main_module.lifespan(main_module.app):
                self.assertEqual(init_db_calls, ["called"])
                self.assertIs(main_module.app.state.scheduler, scheduler)

        asyncio.run(run_lifespan())

        self.assertEqual(scheduler.shutdown_calls, [False])
        self.assertEqual(len(main_module.app.routers), 8)
        self.assertEqual(main_module.app.exception_handlers, [{"exception": "registered", "handler": "handler"}])
        self.assertEqual(len(main_module.app.middlewares), 1)
        self.assertEqual(main_module.app.middlewares[0]["type"], "http")


if __name__ == "__main__":
    unittest.main()
