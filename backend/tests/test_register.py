import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from unittest.mock import MagicMock

from app.api.auth import register, RegisterRequest

def test_register_concurrent_integrity_error():
    req = RegisterRequest(name="Test", email="test@example.com", password="password123")
    mock_request = MagicMock()
    mock_request.session = {}
    
    mock_session = MagicMock()
    # query().filter_by().one_or_none() returns None (simulating passing the first check)
    mock_session.query.return_value.filter_by.return_value.one_or_none.return_value = None
    
    # commit raises IntegrityError
    mock_session.commit.side_effect = IntegrityError("mock error", params={}, orig=Exception())
    
    from unittest.mock import patch
    with patch("app.api.auth._rate_limit_auth"):
        with pytest.raises(HTTPException) as exc:
            register(req, mock_request, mock_session)
        
    assert exc.value.status_code == 409
    assert exc.value.detail == "Email already registered"
    mock_session.rollback.assert_called_once()
