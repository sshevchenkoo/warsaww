import uuid
from unittest.mock import patch, MagicMock

from app.api.routes import search
from app.api.schema import SearchRequest

def test_search_quota_uses_user_id_when_logged_in():
    user_id = str(uuid.uuid4())
    req = SearchRequest(q="test")
    
    mock_request = MagicMock()
    mock_request.session = {"user_id": user_id, "sid": "some-sid"}
    
    with patch("app.api.routes.check_search_quota", return_value=(True, 9)) as mock_check:
        with patch("app.api.routes._require_verified_user", return_value=None):
            with patch("app.api.routes.get_session"):
                with patch("app.api.routes.Settings", require_verified_email_to_search=False):
                    try:
                        search(req, mock_request)
                    except Exception:
                        pass # StreamingResponse or something might fail in test, we just care about the check_search_quota call
                        
    mock_check.assert_called_once_with(user_id)


def test_search_quota_uses_sid_when_logged_out():
    sid = "some-sid"
    req = SearchRequest(q="test")
    
    mock_request = MagicMock()
    mock_request.session = {"sid": sid}
    
    with patch("app.api.routes.check_search_quota", return_value=(True, 9)) as mock_check:
        with patch("app.api.routes._require_verified_user", return_value=None):
            try:
                search(req, mock_request)
            except Exception:
                pass
                
    mock_check.assert_called_once_with(sid)

