import sys, os
sys.path.insert(0, '.')
from app.services.grok_service import GrokExamService

try:
    svc = GrokExamService()
    print('mock_mode:', svc.mock_mode)
    print('api_key present:', bool(getattr(svc,'api_key',None)))
    print('api_key masked:', (svc.api_key[:4] + '...' + svc.api_key[-4:]) if getattr(svc,'api_key',None) else None)
    print('client:', 'initialized' if getattr(svc,'client',None) else 'None')
except Exception as e:
    print('Exception:', e)
