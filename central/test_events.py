from . import events

import unittest


@events.event("test1")
def TestEvent1(val: int):
    return {"val1": val}


@events.event("test2")
def TestEvent2(val: int):
    return {"val2": val}


class TestDispatcher(unittest.TestCase):
    def test_dispatch(self):
        class Target1(events.EventTarget):
            def __init__(self):
                self.vals = []

            def accept_event(self, evt):
                return evt.type == "test1"

            def push_event(self, evt):
                self.vals.append(evt.val1)

        class Target2(events.EventTarget):
            def __init__(self):
                self.vals = []

            def accept_event(self, evt):
                return evt.type == "test2"

            def push_event(self, evt):
                self.vals.append(evt.val2)

        class TargetBoth(events.EventTarget):
            def __init__(self):
                self.vals1 = []
                self.vals2 = []

            def accept_event(self, evt):
                return evt.type in {"test1", "test2"}

            def push_event(self, evt):
                if evt.type == "test1":
                    self.vals1.append(evt.val1)
                else:
                    self.vals2.append(evt.val2)

        target1 = Target1()
        target2 = Target2()
        target_both = TargetBoth()

        dispatcher = events.Dispatcher()
        dispatcher.register_target(target1)
        dispatcher.register_target(target2)
        dispatcher.register_target(target_both)

        dispatcher.dispatch("test_dispatch", TestEvent1(1))
        dispatcher.dispatch("test_dispatch", TestEvent2(10))
        dispatcher.dispatch("test_dispatch", TestEvent1(100))
        dispatcher.dispatch("test_dispatch", TestEvent2(1000))

        self.assertSequenceEqual(target1.vals, [1, 100])
        self.assertSequenceEqual(target2.vals, [10, 1000])
        self.assertSequenceEqual(target_both.vals1, [1, 100])
        self.assertSequenceEqual(target_both.vals2, [10, 1000])

    def test_dispatch_error(self):
        class FailsAccept(events.EventTarget):
            def accept_event(self, evt):
                raise RuntimeError("fail")

            def push_event(self, evt):
                pass

        class FailsPush(events.EventTarget):
            def accept_event(self, evt):
                return True

            def push_event(self, evt):
                raise RuntimeError("fail")

        dispatcher = events.Dispatcher()
        dispatcher.register_target(FailsAccept())
        dispatcher.register_target(FailsPush())

        dispatcher.dispatch("test_dispatch_error", TestEvent1(1))
