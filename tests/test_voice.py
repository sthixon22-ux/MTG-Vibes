import base64
import io
import json
import unittest
from unittest.mock import patch
from voice import transcribe


class VoiceTests(unittest.TestCase):
    def test_audio_multipart_uses_server_key_and_returns_transcript(self):
        audio=b'\x1a\x45\xdf\xa3sample-webm'
        with patch('voice.urllib.request.urlopen', return_value=io.BytesIO(b'{"text":"Explain commander tax."}')) as upstream:
            result=transcribe({'mime':'audio/webm;codecs=opus','audio':base64.b64encode(audio).decode()},'test-only')
        self.assertEqual(result, {'text':'Explain commander tax.'})
        request=upstream.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.openai.com/v1/audio/transcriptions')
        self.assertIn(audio,request.data)
        self.assertIn(b'whisper-1',request.data)
        self.assertIn(b'filename="question.webm"',request.data)
        self.assertEqual(request.get_header('Authorization'),'Bearer test-only')

    def test_invalid_oversized_or_empty_audio_never_calls_provider(self):
        with patch('voice.urllib.request.urlopen') as upstream:
            for data in [{'mime':'text/html','audio':'YWJj'}, {'mime':'audio/webm','audio':'bad!'}, {'mime':'audio/mp4','audio':''}, {'mime':'audio/webm','audio':'a'*8000001}]:
                with self.assertRaises(ValueError):transcribe(data,'test-only')
            upstream.assert_not_called()

    def test_empty_transcript_is_not_sent_to_libby(self):
        with patch('voice.urllib.request.urlopen',return_value=io.BytesIO(b'{"text":"   "}')):
            with self.assertRaises(ValueError):transcribe({'mime':'audio/webm','audio':'YWJj'},'test-only')
