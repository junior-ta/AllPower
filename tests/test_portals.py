import io
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from allpower import store
from allpower import advice
from allpower.backup import plan
from allpower.scenarios import scenario_output
from allpower.server import Handler


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'portal.sqlite3')
        self.job = store.enqueue(self.path, 'supply-loss')
        record = scenario_output('supply-loss')
        record['backup'] = plan(record)
        store.finish(self.path, self.job, record)
        self.env = patch.dict(os.environ, {'ALLPOWER_TOKEN':'master-test',
                                           'ALLPOWER_HOSPITAL_TOKEN':'hospital-test',
                                           'ALLPOWER_SUPPLIER_TOKEN':'supplier-test',
                                           'GEMINI_API_KEY':'',
                                           'ALLPOWER_ADVICE_PROVIDER':'gemini'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.db_path = self.path
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, token='', data=None):
        url = f'http://127.0.0.1:{self.server.server_port}{path}'
        request = Request(url, data=json.dumps(data).encode() if data is not None else None,
                          headers={'X-AllPower-Token':token,
                                   'Content-Type':'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_acknowledgment_survives_new_connections_and_is_listed_once(self):
        status, response = self.call('/api/advisories/adv-'+self.job+'/acknowledge', 'hospital-test', {})
        self.assertEqual(status, 200)
        stamp = response['acknowledged_at']
        self.assertEqual(self.call('/api/advisories/adv-'+self.job+'/acknowledge','hospital-test',{})[1]['acknowledged_at'], stamp)
        status, latest = self.call('/api/runs/latest','hospital-test')
        self.assertEqual(latest['advisory']['acknowledged_at'], stamp)
        status, history = self.call('/api/hospital/acknowledgments','hospital-test')
        self.assertEqual(status,200)
        self.assertEqual(len(history['acknowledgments']),1)
        self.assertEqual(history['acknowledgments'][0]['run_id'],self.job)

    def test_scope_and_static_pages(self):
        self.assertEqual(self.call('/api/status')[0],401)
        self.assertEqual(self.call('/api/hospital/acknowledgments','supplier-test')[0],401)
        self.assertEqual(self.call('/api/supplier/facilities','hospital-test')[0],401)
        self.assertEqual(self.call('/api/supplier/facilities','supplier-test')[0],200)
        self.assertEqual(self.call('/api/hospital/acknowledgments','master-test')[0],200)
        for page in ('hospital.html','supplier.html','vision-demo.html'):
            with urlopen(f'http://127.0.0.1:{self.server.server_port}/{page}') as response:
                self.assertEqual(response.status,200)

    def test_advice_fallback_is_grounded_and_initial_message_cached(self):
        path='/api/hospital/advice'
        status, first=self.call(path,'hospital-test',{'run_id':self.job,'question':''})
        self.assertEqual(status,200)
        self.assertTrue(first['fallback'])
        self.assertIn('forecast hour',first['answer'])
        status, second=self.call(path,'hospital-test',{'run_id':self.job,'question':''})
        self.assertTrue(second['cached'])
        status, messages=self.call(f'/api/hospital/runs/{self.job}/advice','hospital-test')
        self.assertEqual(len(messages['messages']),1)
        self.assertEqual(self.call(path,'hospital-test',{'run_id':self.job,'question':'What first?'})[0],200)
        self.assertEqual(self.call(path,'supplier-test',{'run_id':self.job,'question':'Hi'})[0],401)
        self.assertEqual(self.call(path,'hospital-test',{'run_id':'0'*36,'question':'Hi'})[0],404)

    def test_gemini_request_uses_server_side_run_summary(self):
        response = {'candidates':[{'content':{'parts':[{'text':'Check the approved backup procedure.'}]}}]}
        seen = {}
        def fake_open(request, timeout):
            seen['request'] = request
            seen['timeout'] = timeout
            return io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ, {'GEMINI_API_KEY':'private-test-key'}), patch('allpower.advice.urlopen', fake_open):
            result = advice.generate(store.get_run(self.path,self.job), 'What first?', [])
        self.assertFalse(result['fallback'])
        self.assertEqual(result['provider'],'gemini-3.5-flash-lite')
        self.assertIn('generateContent',seen['request'].full_url)
        self.assertEqual(seen['timeout'],10)
        body=json.loads(seen['request'].data)
        prompt=body['contents'][0]['parts'][0]['text']
        self.assertIn(self.job,prompt)
        self.assertIn('regional_margin_mw',prompt)
        self.assertNotIn('private-test-key',prompt)


if __name__ == '__main__': unittest.main()
