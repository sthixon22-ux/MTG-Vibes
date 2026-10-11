"""Bounded, memory-only audio transcription; credentials stay on the server."""
import base64
import json
import urllib.request
import uuid

MAX_AUDIO = 6_000_000
MIME_EXTENSIONS = {'audio/webm': 'webm', 'audio/mp4': 'm4a', 'audio/wav': 'wav', 'audio/mpeg': 'mp3'}


def transcribe(data, key):
    mime = str(data.get('mime', '')).split(';')[0].lower()
    encoded = data.get('audio')
    if mime not in MIME_EXTENSIONS or not isinstance(encoded, str) or not 0 < len(encoded) <= 8_000_000:
        raise ValueError('Invalid audio recording.')
    audio = base64.b64decode(encoded, validate=True)
    if not 0 < len(audio) <= MAX_AUDIO:
        raise ValueError('Audio recording is too large or empty.')
    boundary = 'mtgvibes-' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nen\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="question.{MIME_EXTENSIONS[mime]}"\r\nContent-Type: {mime}\r\n\r\n').encode() + audio + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request('https://api.openai.com/v1/audio/transcriptions', data=body, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'multipart/form-data; boundary=' + boundary}, method='POST')
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.load(response)
    text = result.get('text', '').strip()
    if not text or len(text) > 4000:
        raise ValueError('No usable speech was detected. Please try a shorter question.')
    return {'text': text}
