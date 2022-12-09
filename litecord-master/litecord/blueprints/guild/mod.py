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

from quart import Blueprint, request, current_app as app, jsonify

from litecord.blueprints.auth import token_check
from litecord.blueprints.checks import guild_perm_check

from litecord.schemas import validate, GUILD_PRUNE
from litecord.common.guilds import remove_member

bp = Blueprint("guild_moderation", __name__)


@bp.route("/<int:guild_id>/members/<int:member_id>", methods=["DELETE"])
async def kick_guild_member(guild_id, member_id):
    """Remove a member from a guild."""
    user_id = await token_check()
    await guild_perm_check(user_id, guild_id, "kick_members", member_id)
    await remove_member(guild_id, member_id)
    return "", 204


@bp.route("/<int:guild_id>/bans", methods=["GET"])
async def get_bans(guild_id):
    user_id = await token_check()

    await guild_perm_check(user_id, guild_id, "ban_members")

    bans = await app.db.fetch(
        """
    SELECT user_id, reason
    FROM bans
    WHERE bans.guild_id = $1
    """,
        guild_id,
    )

    res = []

    for ban in bans:
        res.append(
            {
                "reason": ban["reason"],
                "user": await app.storage.get_user(ban["user_id"]),
            }
        )

    return jsonify(res)


@bp.route("/<int:guild_id>/bans/<int:member_id>", methods=["PUT"])
async def create_ban(guild_id, member_id):
    user_id = await token_check()

    await guild_perm_check(user_id, guild_id, "ban_members", member_id)

    j = await request.get_json()

    await app.db.execute(
        """
    INSERT INTO bans (guild_id, user_id, reason)
    VALUES ($1, $2, $3)
    """,
        guild_id,
        member_id,
        j.get("reason", ""),
    )

    await remove_member(guild_id, member_id)

    await app.dispatcher.guild.dispatch(
        guild_id,
        (
            "GUILD_BAN_ADD",
            {"guild_id": str(guild_id), "user": await app.storage.get_user(member_id)},
        ),
    )

    return "", 204


@bp.route("/<int:guild_id>/bans/<int:banned_id>", methods=["DELETE"])
async def remove_ban(guild_id, banned_id):
    user_id = await token_check()

    await guild_perm_check(user_id, guild_id, "ban_members")

    res = await app.db.execute(
        """
    DELETE FROM bans
    WHERE guild_id = $1 AND user_id = $@
    """,
        guild_id,
        banned_id,
    )

    # we don't really need to dispatch GUILD_BAN_REMOVE
    # when no bans were actually removed.
    if res == "DELETE 0":
        return "", 204

    await app.dispatcher.guild.dispatch(
        guild_id,
        (
            "GUILD_BAN_REMOVE",
            {"guild_id": str(guild_id), "user": await app.storage.get_user(banned_id)},
        ),
    )

    return "", 204


async def get_prune(guild_id: int, days: int) -> list:
    """Get all members in a guild that:

    - did not login in ``days`` days.
    - don't have any roles.
    """

    # @everyone role is always counted as a role in the db
    # (its not implicit to every member as one would think)
    # (that is probably the best solution in the future)
    # (but we live with what we got)
    member_ids = await app.db.fetch(
        f"""
    SELECT id
    FROM users
    JOIN members
    ON members.guild_id = $1 AND members.user_id = users.id
    WHERE
        users.last_session < (now() - (interval '{days} days'))
        AND (
            SELECT COUNT(member_roles.role_id)
            FROM member_roles
            WHERE member_roles.user_id = members.user_id
            ) <= 1
    """,
        guild_id,
    )

    return [r["id"] for r in member_ids]


@bp.route("/<int:guild_id>/prune", methods=["GET"])
async def get_guild_prune_count(guild_id):
    user_id = await token_check()

    await guild_perm_check(user_id, guild_id, "kick_members")

    j = validate(dict(request.args), GUILD_PRUNE)
    days = j["days"]
    member_ids = await get_prune(guild_id, days)

    return jsonify({"pruned": len(member_ids)})


async def prune_members(user_id, guild_id, member_ids):
    # calculate permissions against each pruned member, don't prune
    # if permissions don't allow it
    for member_id in member_ids:
        has_permissions = await guild_perm_check(
            user_id, guild_id, "kick_members", member_id, raise_err=False
        )
        if not has_permissions:
            continue

        await remove_member(guild_id, member_id)


@bp.route("/<int:guild_id>/prune", methods=["POST"])
async def begin_guild_prune(guild_id):
    user_id = await token_check()

    await guild_perm_check(user_id, guild_id, "kick_members")

    j = validate(dict(request.args), GUILD_PRUNE)
    days = j["days"]
    member_ids = await get_prune(guild_id, days)

    # TODO move this job to the background scheduler in a way
    # that the test can fetch the job and wait on it before
    # asserting test result state
    await prune_members(user_id, guild_id, member_ids)
    return jsonify({"pruned": len(member_ids)})
