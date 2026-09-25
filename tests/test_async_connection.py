import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import URL

from app.check_async import check_connection


@pytest.mark.parametrize("failure", [False, True])
def test_async_query_and_cleanup(failure: bool) -> None:
    engine = Mock()
    engine.dispose = AsyncMock()
    connection = Mock()
    connection.execute = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = 1
    connection.execute.return_value = result
    if failure:
        connection.execute.side_effect = RuntimeError("Simulated query failure")
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    manager.__aexit__.return_value = False
    engine.connect.return_value = manager

    with patch("app.check_async.create_async_engine", return_value=engine):
        if failure:
            with pytest.raises(RuntimeError, match="Simulated query failure"):
                asyncio.run(check_connection(URL.create("postgresql+psycopg")))
        else:
            asyncio.run(check_connection(URL.create("postgresql+psycopg")))
            result.close.assert_called_once()
    connection.execute.assert_awaited_once()
    assert str(connection.execute.await_args.args[0]) == "SELECT 1"
    manager.__aexit__.assert_awaited_once()
    engine.dispose.assert_awaited_once()
