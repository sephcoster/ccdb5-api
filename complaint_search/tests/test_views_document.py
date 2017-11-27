from django.core.urlresolvers import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from unittest import skip
from elasticsearch import TransportError
import mock
from complaint_search.es_interface import document
from complaint_search.throttling import (
    DocumentAnonRateThrottle,
    _CCDB_UI_URL,
)

class DocumentTests(APITestCase):

    def setUp(self):
        self.orig_document_anon_rate = DocumentAnonRateThrottle.rate
        # Setting rates to something really big so it doesn't affect testing
        DocumentAnonRateThrottle.rate = '2000/min'

    def tearDown(self):
        cache.clear()
        DocumentAnonRateThrottle.rate = self.orig_document_anon_rate

    @mock.patch('complaint_search.es_interface.document')
    def test_document__valid(self, mock_esdocument):
        """
        documenting with an ID
        """
        url = reverse('complaint_search:document', kwargs={"id": "123456"})
        mock_esdocument.return_value = 'OK'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_esdocument.assert_called_once_with("123456")
        self.assertEqual('OK', response.data)


    @mock.patch('complaint_search.es_interface.document')
    def test_document_with_document_anon_rate_throttle(self, mock_esdocument):
        url = reverse('complaint_search:document', kwargs={"id": "123456"})
        mock_esdocument.return_value = 'OK'
        DocumentAnonRateThrottle.rate = self.orig_document_anon_rate
        limit = int(self.orig_document_anon_rate.split('/')[0])
        for i in range(limit):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual('OK', response.data)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIsNotNone(response.data.get('detail'))
        self.assertIn("Request was throttled", response.data.get('detail'))
        self.assertEqual(limit, mock_esdocument.call_count)
        self.assertEqual(5, limit)

    @mock.patch('complaint_search.es_interface.document')
    def test_document_with_document_ui_rate_throttle(self, mock_esdocument):
        url = reverse('complaint_search:document', kwargs={"id": "123456"})
        mock_esdocument.return_value = 'OK'

        DocumentAnonRateThrottle.rate = self.orig_document_anon_rate
        limit = int(self.orig_document_anon_rate.split('/')[0])
        for _ in range(limit):
            response = self.client.get(url, HTTP_REFERER=_CCDB_UI_URL)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual('OK', response.data)

        response = self.client.get(url, HTTP_REFERER=_CCDB_UI_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual('OK', response.data)
        self.assertEqual(limit + 1, mock_esdocument.call_count)
        self.assertEqual(5, limit)

    @mock.patch('complaint_search.es_interface.document')
    def test_document__transport_error_with_status_code(self, mock_esdocument):
        mock_esdocument.side_effect = TransportError(status.HTTP_404_NOT_FOUND, "Error")
        url = reverse('complaint_search:document', kwargs={"id": "123456"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertDictEqual({"error": "Elasticsearch error: Error"}, response.data)

    @mock.patch('complaint_search.es_interface.document')
    def test_document__transport_error_without_status_code(self, mock_esdocument):
        mock_esdocument.side_effect = TransportError('N/A', "Error")
        url = reverse('complaint_search:document', kwargs={"id": "123456"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictEqual({"error": "Elasticsearch error: Error"}, response.data)


