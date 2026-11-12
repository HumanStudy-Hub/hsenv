"""Structural missing feedback must not become held participant text."""
import unittest
from hsenv import release

class MissingFeedback(unittest.TestCase):
    def test_only_explicit_missing_message_marker_is_structural(self):
        self.closed = b"The secret purple mountain hides a silver lake beneath the stars."
        p = {'stages': {'s': {'responses': [{'validate': {'message': None, 'message_label': 'missing',
            'cite': {'source': 'reference', 'label': 'reported'}}}]}}}
        self.assertEqual(release._slots(p), [])
        p['stages']['s']['responses'][0]['validate']['message_label'] = self.closed.decode()
        self.assertTrue(any(slot[0][-1] == 'message_label' for slot in release._slots(p)))
        p['stages']['s']['responses'][0]['validate'].update(message_label='missing', message=self.closed.decode())
        self.assertTrue(any(slot[0][-1] == 'message' for slot in release._slots(p)))
