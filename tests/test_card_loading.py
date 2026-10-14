import io
import json
import threading
import unittest
import urllib.error
from unittest.mock import patch
import server


class CardLoadingTests(unittest.TestCase):
    def setUp(self):
        server.CACHE.clear()
        server.CACHE_TIMES.clear()
        server.SCRYFALL_UNAVAILABLE_UNTIL = 0

    def test_collection_fills_aliases_and_normalizes_apostrophes(self):
        cards = [{'name': "Mishra's Bauble"}, {'name': 'Slicer, Hired Muscle // Slicer, High-Speed Antagonist', 'card_faces': [{'name': 'Slicer, Hired Muscle'}, {'name': 'Slicer, High-Speed Antagonist'}]}]
        body = {'data': cards}
        with patch('server.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(body).encode())) as upstream:
            server.prime_cards({'cards': [{'name': 'Mishra’s Bauble'}, {'name': 'Slicer, Hired Muscle'}, {'name': 'Mishra’s Bauble'}]})
            self.assertEqual(server.lookup_card(' Mishra’s  Bauble ')['name'], "Mishra's Bauble")
            self.assertEqual(server.lookup_card('Slicer, Hired Muscle')['name'], cards[1]['name'])
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(len(json.loads(upstream.call_args.args[0].data)['identifiers']), 2)

    def test_temporary_rate_limit_retries_without_losing_card(self):
        error = urllib.error.HTTPError('https://api.scryfall.com/cards/named', 429, 'limited', {'Retry-After': '0'}, None)
        with patch('server.urllib.request.urlopen', side_effect=[error, io.BytesIO(json.dumps({'name': 'Victimize'}).encode())]) as upstream, patch('server.time.sleep'):
            card = server.lookup_card('Victimize')
        self.assertEqual(card['name'], 'Victimize')
        self.assertEqual(upstream.call_count, 2)

    def test_cached_cards_are_accessible_during_slow_lookup(self):
        server.cache_card({'name': 'Forest'})
        entered, release, cached_done = threading.Event(), threading.Event(), threading.Event()
        results = []
        def slow(request, **kwargs):
            entered.set()
            release.wait(2)
            return io.BytesIO(json.dumps({'name': 'Victimize'}).encode())
        def read_cached():
            results.append(server.lookup_card('Forest'))
            cached_done.set()
        with patch('server.urllib.request.urlopen', side_effect=slow):
            worker = threading.Thread(target=lambda: server.lookup_card('Victimize'))
            worker.start()
            self.assertTrue(entered.wait(2))
            reader = threading.Thread(target=read_cached)
            reader.start()
            available = cached_done.wait(.5)
            release.set()
            worker.join(2)
            reader.join(2)
        self.assertTrue(available, 'A network request must not hold the cache lock.')
        self.assertEqual(results[0]['name'], 'Forest')

    def test_duplicate_lookup_uses_one_upstream_request(self):
        entered, release = threading.Event(), threading.Event()
        def fetch(request, **kwargs):
            entered.set()
            release.wait(2)
            return io.BytesIO(json.dumps({'name': 'Memnarch'}).encode())
        with patch('server.urllib.request.urlopen', side_effect=fetch) as upstream:
            workers = [threading.Thread(target=lambda: server.lookup_card('Memnarch')) for _ in range(6)]
            for w in workers: w.start()
            self.assertTrue(entered.wait(2))
            release.set()
            for w in workers: w.join(2)
        self.assertEqual(upstream.call_count, 1)

    def test_outage_does_not_repeat_long_requests_for_every_card(self):
        failure = urllib.error.URLError('temporarily down')
        with patch('server.urllib.request.urlopen', side_effect=failure) as upstream, patch('server.time.sleep'):
            with self.assertRaises(urllib.error.URLError): server.lookup_card('Memnarch')
            with self.assertRaises(urllib.error.URLError): server.lookup_card('Victimize')
        self.assertEqual(upstream.call_count, 3)
        server.SCRYFALL_UNAVAILABLE_UNTIL = 0

    def test_real_not_found_does_not_retry_or_block_other_cards(self):
        error = urllib.error.HTTPError('https://api.scryfall.com', 404, 'not found', {}, None)
        with patch('server.urllib.request.urlopen', side_effect=[error, io.BytesIO(json.dumps({'name': 'Memnarch'}).encode())]) as upstream:
            with self.assertRaises(urllib.error.HTTPError): server.lookup_card('Not a card')
            self.assertEqual(server.lookup_card('Memnarch')['name'], 'Memnarch')
        self.assertEqual(upstream.call_count, 2)

    def test_image_download_retries_temporary_cdn_failure(self):
        error = urllib.error.HTTPError('https://cards.scryfall.io/card.jpg', 503, 'unavailable', {}, None)
        with patch('server.urllib.request.urlopen', side_effect=[error, io.BytesIO(b'\xff\xd8image')]) as upstream, patch('server.time.sleep'):
            self.assertEqual(server.download_card_image('https://cards.scryfall.io/card.jpg'), b'\xff\xd8image')
        self.assertEqual(upstream.call_count, 2)
