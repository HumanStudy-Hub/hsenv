"""Platform IDs (desktop #170): Session.synthetic_text_id and the system_filled argument of Session.step and
GroupSession.step. Administrative values satisfy the page's validation but never enter answers or refusals."""
import unittest

from hsenv.engine import Env, Protocol


def protocol(*, pattern=None, group=False, min_chars=24):
    field = {"id": "registration", "kind": "text", "required": True,
             "prompt": "Please paste your Prolific ID below.", "min_chars": min_chars}
    if pattern:
        field["validate"] = {"pattern": pattern}
    return Protocol({"id": "test", "flow": {"stage": "form"}, "stages": {"form": {"responses": [field]}},
                     "arms": [{"id": "main", **({"group_size": 2} if group else {})}]})


class PlatformIdEngineTests(unittest.TestCase):
    def open(self, study):
        env = Env(study)
        member = env.open(env.design(n=1)[0])
        return member, member.reset()

    def test_engine_step(self):
        member, state = self.open(protocol(pattern="^[a-f0-9]{24}$"))
        field = state["screen"]["responses"][0]["id"]
        self.assertIn(field, member.step({}, system_filled={field: "bad"})["error"])
        self.assertTrue(member.step({}, system_filled={field: "a" * 24})["done"])
        self.assertEqual(member.answers, [])
        self.assertEqual(member.refused[0]["answers"], {})

    def test_synthetic_id_minimum_length(self):
        member, state = self.open(protocol(min_chars=75))
        field = state["screen"]["responses"][0]["id"]
        value = member.synthetic_text_id(field, "AI-participant-x-p1")
        self.assertEqual(len(value), 75)
        self.assertEqual(value, member.synthetic_text_id(field, "AI-participant-x-p1"))   # stable
        self.assertTrue(member.step({}, system_filled={field: value})["done"])

    def test_synthetic_id_pattern(self):
        member, state = self.open(protocol(pattern="^[a-f0-9]{24}$"))
        field = state["screen"]["responses"][0]["id"]
        a = member.synthetic_text_id(field, "AI-participant-x-p1")
        b = member.synthetic_text_id(field, "AI-participant-x-p2")
        self.assertRegex(a, "^[a-f0-9]{24}$")
        self.assertNotEqual(a, b)

    def test_synthetic_id_unsatisfiable(self):
        member, state = self.open(protocol(pattern="^.{3}$"))
        field = state["screen"]["responses"][0]["id"]
        self.assertIsNone(member.synthetic_text_id(field, "AI-participant-x-p1"))

    def test_group_step(self):
        env = Env(protocol(pattern="^[a-f0-9]{24}$", group=True))
        group = env.open(env.design(n=1)[0])
        states = group.reset()
        self.assertEqual(sorted(states), ["p1", "p2"])
        for pid, state in states.items():
            field = state["screen"]["responses"][0]["id"]
            member = next(m for m in group.members if m.pid == pid)
            value = member.synthetic_text_id(field, "AI-participant-x-%s" % pid)
            group.step(pid, {}, system_filled={field: value})
            self.assertEqual(member.answers, [])
        self.assertTrue(all(st.get("done") for st in group.states().values()))


if __name__ == "__main__":
    unittest.main()
