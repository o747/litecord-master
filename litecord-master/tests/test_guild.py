"""

Litecord
Copyright (C) 2018-2021  Luna Mendes and Litecord Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
import secrets
import datetime

import pytest

from litecord.common.guilds import add_member


@pytest.mark.asyncio
async def test_guild_create(test_cli_user):
    """Test the creation of a guild, in three stages:
    - creating it
    - checking the list
    - deleting it
    """
    g_name = secrets.token_hex(5)

    # stage 1: create
    resp = await test_cli_user.post(
        "/api/v6/guilds", json={"name": g_name, "region": None}
    )

    assert resp.status_code == 200
    rjson = await resp.json

    # we won't assert a full guild object.
    assert isinstance(rjson["id"], str)
    assert isinstance(rjson["owner_id"], str)
    assert isinstance(rjson["name"], str)
    assert rjson["name"] == g_name

    created = rjson
    guild_id = created["id"]

    # stage 2: test
    resp = await test_cli_user.get("/api/v6/users/@me/guilds")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, list)

    # it MUST be 1 as we'll delete the guild later on.
    # plus the test user never starts with any guild.
    assert len(rjson) == 1

    for guild in rjson:
        assert isinstance(guild, dict)
        assert isinstance(guild["id"], str)
        assert isinstance(guild["name"], str)
        assert isinstance(guild["owner"], bool)
        assert guild["icon"] is None or isinstance(guild["icon"], str)

    try:
        our_guild = next(filter(lambda guild: guild["id"] == guild_id, rjson))
    except StopIteration:
        raise Exception("created guild not found in user guild list")

    assert our_guild["id"] == created["id"]
    assert our_guild["name"] == created["name"]

    # stage 3: deletion
    resp = await test_cli_user.delete(f"/api/v6/guilds/{guild_id}")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_guild_nickname(test_cli_user):
    guild = await test_cli_user.create_guild()

    NEW_NICKNAME = "my awesome nickname"
    # stage 1: create
    resp = await test_cli_user.patch(
        f"/api/v6/guilds/{guild.id}/members/@me/nick",
        json={"nick": NEW_NICKNAME},
    )

    assert resp.status_code == 200
    assert (await resp.data).decode() == NEW_NICKNAME

    # stage 2: test
    resp = await test_cli_user.get(f"/api/v6/guilds/{guild.id}")

    assert resp.status_code == 200
    fetched_guild = await resp.json

    assert fetched_guild["id"] == str(guild.id)
    assert fetched_guild["members"][0]["nick"] == NEW_NICKNAME


async def test_prune_guild(test_cli_user):
    guild = await test_cli_user.create_guild()
    user = await test_cli_user.create_user()
    async with test_cli_user.app.app_context():
        await add_member(guild.id, user.id)

    # assert setup went well
    added_member_guild = await guild.refetch()
    assert added_member_guild.member_count == 2

    resp = await test_cli_user.get(
        f"/api/v6/guilds/{guild.id}/prune", query_string={"days": 7}
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["pruned"] == 0

    # set joined_at to the beginning of the universe
    await test_cli_user.app.db.execute(
        "UPDATE users SET last_session = $1 WHERE id = $2",
        datetime.datetime(year=2010, month=1, day=1),
        user.id,
    )

    # execute compute prune, must return 1
    resp = await test_cli_user.get(
        f"/api/v6/guilds/{guild.id}/prune", query_string={"days": 7}
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["pruned"] == 1

    # execute prune, member count should go to 1
    resp = await test_cli_user.post(
        f"/api/v6/guilds/{guild.id}/prune",
        query_string={"days": 7},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["pruned"] == 1

    pruned_member_guild = await guild.refetch()
    assert pruned_member_guild.member_count == 1
